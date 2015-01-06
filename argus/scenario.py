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

import six
from tempest.common import rest_client
from tempest.common.utils import data_utils
from tempest.scenario import manager
from tempest.services.network import network_client_base

from argus import config
from argus import exceptions
from argus import prepare
from argus import util

CONF = util.get_config()


# TODO(cpopa): this is really a horrible hack!
# But it solves the following problem, which can't
# be solved easily otherwise:
#    *  manager.ScenarioTest creates its clients in resource_setup
#    * in order to create them, it needs credentials through a CredentialProvider
#    * the credential provider, if the network resource is enabled, will look up
#      in the list of known certs and will return them
#    * if the credential provider can't find those creds at first, it retrieves
#      them by creating the network and the subnet
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
    self.rest_client.expected_success(201, resp.status)
    return rest_client.ResponseBody(resp, body)

network_client_base.NetworkClientBase.create_subnet = _create_subnet



@six.add_metaclass(abc.ABCMeta)
class BaseArgusScenario(manager.ScenarioTest):
    instance_preparer = None

    @classmethod
    def create_test_server(cls, wait_until='ACTIVE', **kwargs):
        _, server = cls.servers_client.create_server(
            data_utils.rand_name(cls.__name__ + "-instance"),
            CONF.argus.image_ref,
            CONF.argus.flavor_ref,
            **kwargs)
        cls.servers_client.wait_for_server_status(
            server['id'], wait_until)
        return server

    @classmethod
    def create_keypair(cls):
        _, cls.keypair = cls.keypairs_client.create_keypair(
            cls.__name__ + "-key")
        with open(CONF.argus.path_to_private_key, 'w') as stream:
            stream.write(cls.keypair['private_key'])

    @classmethod
    def _assign_floating_ip(cls):
        # Obtain a floating IP
        _, cls.floating_ip = cls.floating_ips_client.create_floating_ip()

        cls.floating_ips_client.associate_floating_ip_to_server(
            cls.floating_ip['ip'], cls.server['id'])

    @classmethod
    def _add_security_group_exceptions(cls, secgroup_id):
        # TODO(cpopa): this is almost a verbatim copy of
        # _create_loginable_secgroup_rule. Unfortunately, we can't provide
        # custom rules otherwise.
        _client = cls.security_groups_client
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

    @classmethod
    def _create_security_groups(cls):
        sg_name = data_utils.rand_name(cls.__class__.__name__)
        sg_desc = sg_name + " description"
        _, secgroup = cls.security_groups_client.create_security_group(
            sg_name, sg_desc)

        # Add rules to the security group
        for rule in cls._add_security_group_exceptions(secgroup['id']):
            cls.security_groups_rules.append(rule['id'])
        cls.servers_client.add_security_group(cls.server['id'],
                                              secgroup['name'])
        cls.security_group = secgroup

    # Instance creation and termination.

    @classmethod
    def resource_setup(cls):
        super(BaseArgusScenario, cls).resource_setup()

        cls.server = None
        cls.security_groups = []
        cls.security_groups_rules = []
        cls.subnets = []
        cls.routers = []
        cls.floating_ips = {}
        metadata = {'network_config': str({'content_path':
                                           'random_value_test_random'})}
        encoded_data = base64.encodestring(
            util.get_resource('multipart_metadata'))

        try:
            cls.create_keypair()
            cls.server = cls.create_test_server(
                wait_until='ACTIVE',
                key_name=cls.keypair['name'],
                disk_config='AUTO',
                user_data=encoded_data,
                meta=metadata)
            cls._assign_floating_ip()
            cls._create_security_groups()
        except:
            cls.resource_cleanup()
            raise

    @classmethod
    def resource_cleanup(cls):
        super(BaseArgusScenario, cls).resource_cleanup()
        if cls.security_groups_rules:
            for rule in cls.security_groups_rules:
                cls.security_groups_client.delete_security_group_rule(rule)

        if cls.security_groups:
            cls.servers_client.remove_security_group(
                cls.server['id'], cls.security_group['name'])

        if cls.server:
            cls.servers_client.delete_server(cls.server['id'])
            cls.servers_client.wait_for_server_termination(cls.server['id'])

        if cls.floating_ips:
            cls.floating_ips_client.delete_floating_ip(cls.floating_ip['id'])

        if cls.keypair:
            cls.keypairs_client.delete_keypair(cls.keypair['name'])
            os.remove(CONF.argus.path_to_private_key)

    def setUp(self):
        super(BaseArgusScenario, self).setUp()
        # It should be guaranteed that it's called only once,
        # so a second call is a no-op.
        self.prepare_instance()

    def password(self):
        _, encoded_password = self.servers_client.get_password(
            self.server['id'])
        return util.decrypt_password(
            private_key=CONF.argus.path_to_private_key,
            password=encoded_password['password'])

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

    @property
    def run_command_verbose(self):
        return self.remote_client.run_command_verbose

    @util.run_once
    def prepare_instance(self):
        if self.instance_preparer is None:
            raise exceptions.CloudbaseCIError('instance_preparer must be set')
        # pylint: disable=not-callable
        self.instance_preparer(
            self.server['id'],
            self.servers_client,
            self.remote_client).prepare()


    def get_image_ref(self):
        return self.images_client.get_image(CONF.argus.image_ref)

    def instance_server(self):
        return self.servers_client.get_server(self.server['id'])


class BaseWindowsScenario(BaseArgusScenario):
    """Base class for Windows-based tests."""
    instance_preparer = prepare.WindowsInstancePreparer

    def get_remote_client(self, username=None, password=None,
                          protocol='http', **kwargs):
        if username is None:
            username = CONF.argus.default_ci_username
        if password is None:
            password = CONF.argus.default_ci_password
        return util.WinRemoteClient(self.floating_ip['ip'],
                                    username,
                                    password,
                                    transport_protocol=protocol)

    remote_client = util.cached_property(get_remote_client)
