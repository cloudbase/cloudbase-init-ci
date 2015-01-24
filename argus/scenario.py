# Copyright 2014 Cloudbase Solutions Srl
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import abc
import base64
import os
import unittest

import six
from tempest import clients
from tempest.common import credentials
from tempest.common import service_client
from tempest.common.utils import data_utils
from tempest.services import network

from argus import exceptions
from argus import util

CONF = util.get_config()
LOG = util.get_logger()

# tempest sets its own excepthook, which will log the error
# using the tempest logger. Unfortunately, we are not using
# the tempest logger, so any uncaught error goes into nothingness.
# The code which sets the excepthook is here:
# https://github.com/openstack/tempest/blob/master/tempest/openstack/common/log.py#L420
# That's why we mock the logging.setup call to something which
# won't affect us. This is another ugly hack, but unfixable
# otherwise.
from tempest.openstack.common import log
log.setup = lambda *args, **kwargs: None


# TODO(cpopa): this is really a horrible hack!
# But it solves the following problem, which can't
# be solved easily otherwise:
#    *  manager.ScenarioTest creates its clients in resource_setup
#    * in order to create them, it needs credentials
#      through a CredentialProvider
#    * the credential provider, if the network resource is enabled, will
#       look up in the list of known certs and will return them
#    * if the credential provider can't find those creds at first,
#      it retrieves them by creating the network and the subnet
#    * the only problem is that the parameters to these functions aren't
#       customizable at this point
#    * and create_subnet doesn't receive the dns_nameservers option,
#      which results in no internet connection inside the instance.
#    * that's what the following function does, it patches create_subnet
#      so that it is passing all the time the dns_nameservers
#    * this could be fixed by manually creating the network, subnet
#      and store the credentials before calling resource_setup
#      for manager.ScenarioTest, but that requires a lot of
#      code duplication.

def _create_subnet(self, **kwargs):
    resource_name = 'subnet'
    kwargs['dns_nameservers'] = CONF.argus.dns_nameservers
    plural = self.pluralize(resource_name)
    uri = self.get_uri(plural)
    post_data = self.serialize({resource_name: kwargs})
    resp, body = self.post(uri, post_data)
    body = self.deserialize_single(body)
    self.expected_success(201, resp.status)
    return service_client.ResponseBody(resp, body)

network.json.network_client.NetworkClientJSON.create_subnet = _create_subnet


@six.add_metaclass(abc.ABCMeta)
class BaseArgusScenario(object):
    """A scenario represents a complex testing environment

    It is composed by a recipee for preparing an instance,
    userdata and metadata which are injected in the instance,
    an image which will be prepared, and test case, which
    validates what happened in the instance.

    To run the scenario, it is sufficient to call :meth:`run`.

    The parameter `result` is either an instance of
    `unittest.TestResult` or `unittest.TextTestResult` or anything
    that can work as a test result for the unittest framework.
    If nothing is given, it will default to `unittest.TestResult`.
    """

    def __init__(self, test_class, recipee=None,
                 userdata=None, metadata=None,
                 image=None, result=None):
        self._recipee = recipee
        self._userdata = userdata
        self._metadata = metadata
        self._test_class = test_class
        # Internal created objects
        self._server = None
        self._keypair = None
        self._security_group = None
        self._security_groups_rules = []
        self._subnets = []
        self._routers = []
        self._floating_ip = None
        self._result = result or unittest.TestResult()
        self._image = image

    def _prepare_run(self):
        # pylint: disable=attribute-defined-outside-init
        self._isolated_creds = credentials.get_isolated_credentials(
            self.__class__.__name__, network_resources={})
        self._manager = clients.Manager(credentials=self._credentials())
        self._admin_manager = clients.Manager(self._admin_credentials())

        # Clients (in alphabetical order)
        self._flavors_client = self._manager.flavors_client
        self._floating_ips_client = self._manager.floating_ips_client
        # Glance image client v1
        self._image_client = self._manager.image_client
        # Compute image client
        self._images_client = self._manager.images_client
        self._keypairs_client = self._manager.keypairs_client
        self._networks_client = self._admin_manager.networks_client
        # Nova security groups client
        self._security_groups_client = self._manager.security_groups_client
        self._servers_client = self._manager.servers_client
        self._volumes_client = self._manager.volumes_client
        self._snapshots_client = self._manager.snapshots_client
        self._interface_client = self._manager.interfaces_client
        # Neutron network client
        self._network_client = self._manager.network_client
        # Heat client
        self._orchestration_client = self._manager.orchestration_client

    def _credentials(self):
        return self._isolated_creds.get_primary_creds()

    def _admin_credentials(self):
        try:
            return self._isolated_creds.get_admin_creds()
        except NotImplementedError:
            raise exceptions.ArgusError(
                'Admin Credentials are not available')

    def _create_server(self, wait_until='ACTIVE', **kwargs):
        _, server = self._servers_client.create_server(
            data_utils.rand_name(self.__class__.__name__ + "-instance"),
            self._image.image_ref,
            self._image.flavor_ref,
            **kwargs)
        self._servers_client.wait_for_server_status(server['id'], wait_until)
        return server

    def _create_keypair(self):
        _, keypair = self._keypairs_client.create_keypair(
            self.__class__.__name__ + "-key")
        with open(CONF.argus.path_to_private_key, 'w') as stream:
            stream.write(keypair['private_key'])
        return keypair

    def _assign_floating_ip(self):
        _, floating_ip = self._floating_ips_client.create_floating_ip()

        self._floating_ips_client.associate_floating_ip_to_server(
            floating_ip['ip'], self._server['id'])
        return floating_ip

    def _add_security_group_exceptions(self, secgroup_id):
        _client = self._security_groups_client
        rulesets = [
            {
                # http RDP
                'ip_proto': 'tcp',
                'from_port': 3389,
                'to_port': 3389,
                'cidr': '0.0.0.0/0',
            },
            {
                # http winrm
                'ip_proto': 'tcp',
                'from_port': 5985,
                'to_port': 5985,
                'cidr': '0.0.0.0/0',
            },
            {
                # https winrm
                'ip_proto': 'tcp',
                'from_port': 5986,
                'to_port': 5986,
                'cidr': '0.0.0.0/0',
            },
            {
                # ssh
                'ip_proto': 'tcp',
                'from_port': 22,
                'to_port': 22,
                'cidr': '0.0.0.0/0',
            },
            {
                # ping
                'ip_proto': 'icmp',
                'from_port': -1,
                'to_port': -1,
                'cidr': '0.0.0.0/0',
            },
        ]
        for ruleset in rulesets:
            _, sg_rule = _client.create_security_group_rule(secgroup_id,
                                                            **ruleset)
            yield sg_rule

    def _create_security_groups(self):
        sg_name = data_utils.rand_name(self.__class__.__name__)
        sg_desc = sg_name + " description"
        _, secgroup = self._security_groups_client.create_security_group(
            sg_name, sg_desc)

        # Add rules to the security group
        for rule in self._add_security_group_exceptions(secgroup['id']):
            self._security_groups_rules.append(rule['id'])
        self._servers_client.add_security_group(self._server['id'],
                                                secgroup['name'])
        return secgroup

    def _setup(self):
        # pylint: disable=attribute-defined-outside-init
        LOG.info("Creating server.")
        self._keypair = self._create_keypair()
        self._server = self._create_server(
            wait_until='ACTIVE',
            key_name=self._keypair['name'],
            disk_config='AUTO',
            user_data=base64.encodestring(self._userdata),
            meta=self._metadata)
        self._floating_ip = self._assign_floating_ip()
        self._security_group = self._create_security_groups()
        self._prepare_instance()

    def _cleanup(self):
        LOG.info("Cleaning up.")

        if self._security_groups_rules:
            for rule in self._security_groups_rules:
                self._security_groups_client.delete_security_group_rule(rule)

        if self._security_group:
            self._servers_client.remove_security_group(
                self._server['id'], self._security_group['name'])

        if self._server:
            self._servers_client.delete_server(self._server['id'])
            self._servers_client.wait_for_server_termination(
                self._server['id'])

        if self._floating_ip:
            self._floating_ips_client.delete_floating_ip(
                self._floating_ip['id'])

        if self._keypair:
            self._keypairs_client.delete_keypair(self._keypair['name'])
            os.remove(CONF.argus.path_to_private_key)

        self._isolated_creds.clear_isolated_creds()

    def run(self):
        """Run the tests from the underlying test class.

        This will start a new instance and prepare it using the recipee.
        It will return a list of test results.
        """

        self._prepare_run()

        try:
            self._setup()
            LOG.info("Running tests.")
            testloader = unittest.TestLoader()
            testnames = testloader.getTestCaseNames(self._test_class)
            suite = unittest.TestSuite()
            for name in testnames:
                suite.addTest(self._test_class(name,
                                               manager=self,
                                               image=self._image))
            return suite.run(self._result)
        finally:
            self._cleanup()

    def _prepare_instance(self):
        if self._recipee is None:
            raise exceptions.ArgusError('recipee must be set')

        LOG.info("Preparing instance.")
        # pylint: disable=not-callable
        self._recipee(
            instance_id=self._server['id'],
            api_manager=self._manager,
            remote_client=self.remote_client,
            image=self._image).prepare()

    def instance_password(self):
        """Get the password posted by the instance."""
        _, encoded_password = self._servers_client.get_password(
            self._server['id'])
        return util.decrypt_password(
            private_key=CONF.argus.path_to_private_key,
            password=encoded_password['password'])

    def instance_output(self, limit):
        """Get the console output, sent from the instance."""
        return self._servers_client.get_console_output(self._server['id'],
                                                       limit)

    def instance_server(self):
        """Get the instance server object."""
        return self._servers_client.get_server(self._server['id'])

    def public_key(self):
        return self._keypair['public_key']

    def private_key(self):
        return self._keypair['private_key']

    def get_image_ref(self):
        return self._images_client.get_image(self._image.image_ref)

    @abc.abstractmethod
    def get_remote_client(self, username=None, password=None, **kwargs):
        """Get a remote client to the underlying instance.

        This is different than :attr:`remote_client`, because that
        will always return a client with predefined credentials,
        while this method allows for a fine-grained control
        over this aspect.
        `password` can be omitted if authentication by
        SSH key is used.
        The **kwargs parameter can be used for additional options
        (currently none).
        """

    @abc.abstractproperty
    def remote_client(self):
        """An astract property which should return the default client."""


class BaseWindowsScenario(BaseArgusScenario):
    """Base class for Windows-based scenarios."""

    def get_remote_client(self, username=None, password=None,
                          protocol='http', **kwargs):
        if username is None:
            username = self._image.default_ci_username
        if password is None:
            password = self._image.default_ci_password
        return util.WinRemoteClient(self._floating_ip['ip'],
                                    username,
                                    password,
                                    transport_protocol=protocol)

    remote_client = util.cached_property(get_remote_client, 'remote_client')


class BaseArgusTest(unittest.TestCase):
    """Test class which offers support for parametrization of the manager."""

    introspection_class = None

    def __init__(self, methodName='runTest', manager=None, image=None):
        super(BaseArgusTest, self).__init__(methodName)
        self.manager = manager
        self.image = image

    # Export a couple of APIs from the underlying manager.

    @property
    def server(self):
        # Protected access is good here.
        # pylint: disable=protected-access
        return self.manager._server

    @property
    def remote_client(self):
        return self.manager.remote_client

    @property
    def run_command_verbose(self):
        return self.manager.remote_client.run_command_verbose

    @util.cached_property
    def introspection(self):
        if not self.introspection_class:
            raise exceptions.ArgusError(
                'introspection_class must be set')

        # pylint: disable=not-callable
        return self.introspection_class(self.remote_client,
                                        self.server['id'],
                                        image=self.image)
