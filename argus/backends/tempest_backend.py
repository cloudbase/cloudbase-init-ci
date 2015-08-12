# Copyright 2015 Cloudbase Solutions Srl
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
import os
import unittest

import six

from argus import util
from argus.backends import base as base_backend

with util.restore_excepthook():
    from tempest import clients
    from tempest.common import credentials
    from tempest.common import waiters


CONF = util.get_config()
LOG = util.get_logger()

# Starting size as number of lines and tolerance.
OUTPUT_SIZE = 128
OUTPUT_EPSILON = int(OUTPUT_SIZE / 10)
OUTPUT_STATUS_OK = [200]


@six.add_metaclass(abc.ABCMeta)
class BaseTempestScenario(base_backend.BaseBackend):
    """Base class for scenarios that use the tempest backend"""

    def __init__(self):
        self._userdata = None
        self._server = None
        self._keypair = None
        self._security_group = None
        self._security_groups_rules = []
        self._subnets = []
        self._routers = []
        self._floating_ip = None
        self._networks = None    # list with UUIDs for future attached NICs

    def _prepare_run(self):
        # pylint: disable=attribute-defined-outside-init
        self._isolated_creds = credentials.get_isolated_credentials(
            self.__class__.__name__, network_resources={})
        self._manager = clients.Manager(credentials=self._credentials())

        # Clients (in alphabetical order)
        self._flavors_client = self._manager.flavors_client
        self._floating_ips_client = self._manager.floating_ips_client

        # Glance image client v1
        self._image_client = self._manager.image_client

        # Compute image client
        self._images_client = self._manager.images_client
        self._keypairs_client = self._manager.keypairs_client

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

    def _configure_networking(self):
        subnet_id = self._credentials().subnet["id"]
        self._network_client.update_subnet(
            subnet_id,
            dns_nameservers=CONF.argus.dns_nameservers)

    def _create_server(self, wait_until='ACTIVE', **kwargs):
        server = self._servers_client.create_server(
            util.rand_name(self.__class__.__name__) + "-instance",
            self._image.image_ref,
            self._image.flavor_ref,
            **kwargs)
        waiters.wait_for_server_status(
            self._servers_client, server['id'], wait_until)
        return server

    def _create_keypair(self):
        keypair = self._keypairs_client.create_keypair(
            self.__class__.__name__ + "-key")
        with open(CONF.argus.path_to_private_key, 'w') as stream:
            stream.write(keypair['private_key'])
        return keypair

    def _assign_floating_ip(self):
        floating_ip = self._floating_ips_client.create_floating_ip()

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
            sg_rule = _client.create_security_group_rule(secgroup_id,
                                                         **ruleset)
            yield sg_rule

    def _create_security_groups(self):
        sg_name = util.rand_name(self.__class__.__name__)
        sg_desc = sg_name + " description"
        secgroup = self._security_groups_client.create_security_group(
            sg_name, sg_desc)

        # Add rules to the security group.
        for rule in self._add_security_group_exceptions(secgroup['id']):
            self._security_groups_rules.append(rule['id'])
        self._servers_client.add_security_group(self._server['id'],
                                                secgroup['name'])
        return secgroup

    def _setup(self):
        # pylint: disable=attribute-defined-outside-init
        LOG.info("Creating server...")

        self._configure_networking()
        self._keypair = self._create_keypair()
        self._server = self._create_server(
            wait_until='ACTIVE',
            key_name=self._keypair['name'],
            disk_config='AUTO',
            user_data=self._userdata,
            meta=self._metadata,
            networks=self._networks)
        self._floating_ip = self._assign_floating_ip()
        self._security_group = self._create_security_groups()

    @staticmethod
    def _get_log_template(suffix):
        template = "{}{}.log".format("{}", "-" + suffix if suffix else "")
        return template

    def test_names(self):
        """Return an iterator of pairs between test classes and test names

        This should return all the test names from the underlying
        test classes, preceded by the test class they belong to.
        """
        testloader = unittest.TestLoader()
        for test_class in self._test_classes:
            testnames = testloader.getTestCaseNames(test_class)
            for name in testnames:
                yield test_class, name

    def save_instance_output(self, suffix=None):
        """Retrieve and save all data written through the COM port.

        If a `suffix` is provided, then the log name is preceded by it.
        """
        if not self._output_directory:
            return

        template = self._get_log_template(suffix)
        path = os.path.join(self._output_directory,
                            template.format(self._server["id"]))
        content = self.instance_output()
        if not content.strip():
            LOG.warn("Empty console output; nothing to save.")
            return

        LOG.info("Saving instance console output to: %s", path)
        with open(path, "wb") as stream:
            stream.write(content)

    def cleanup(self):
        LOG.info("Cleaning up...")

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

    def setup_instance(self):
        try:
            self._prepare_run()
            self._setup()
            self.save_instance_output()
        finally:
            self.cleanup()

    def reboot_instance(self):
        self._servers_client.reboot(server_id=self._server['id'],
                                    reboot_type='soft')
        waiters.wait_for_server_status(
            self._servers_client, self._server['id'], 'ACTIVE')

    def userdata(self):
        """Get the userdata which will be injected."""
        return self._userdata

    def server(self):
        """Get the server created by this scenario.

        If the server wasn't created, this could be None.
        """
        return self._server

    def instance_password(self):
        """Get the password posted by the instance."""
        encoded_password = self._servers_client.get_password(
            self._server['id'])
        return util.decrypt_password(
            private_key=CONF.argus.path_to_private_key,
            password=encoded_password['password'])

    def _instance_output(self, limit):
        ret = self._servers_client.get_console_output(self._server['id'],
                                                      limit)
        return ret.response, ret.data

    def instance_output(self, limit=OUTPUT_SIZE):
        """Get the console output, sent from the instance."""
        while True:
            resp, content = self._instance_output(limit)
            if resp.status not in OUTPUT_STATUS_OK:
                LOG.error("Couldn't get console output <%d>.", resp.status)
                return

            if len(content.splitlines()) >= (limit - OUTPUT_EPSILON):
                limit *= 2
            else:
                break
        return content

    def instance_server(self):
        """Get the instance server object."""
        return self._servers_client.show_server(self._server['id'])

    def public_key(self):
        return self._keypair['public_key']

    def private_key(self):
        return self._keypair['private_key']

    def get_image_by_ref(self):
        return self._images_client.show_image(self._image.image_ref)

    def get_metadata(self):
        return self._metadata

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


class BaseWindowsScenario(BaseTempestScenario):
    """Base class for Windows-based scenarios."""

    def __init__(self, *args, **kwargs):
        super(BaseWindowsScenario, self).__init__(*args, **kwargs)
        # Installer details.
        self.build = None
        self.arch = None

    def _get_log_template(self, suffix):
        template = super(BaseWindowsScenario, self)._get_log_template(suffix)
        if self.build and self.arch:
            # Prepend the log with the installer information (cloud).
            template = "{}-{}-{}".format(self.build, self.arch, template)
        return template

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
