# Copyright 2014 Cloudbase-init
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
from tempest.common.utils import data_utils
from tempest.scenario import manager

from argus import config
from argus import exceptions
from argus import prepare
from argus import util

CONF = config.CONF
TEMPEST_CONF = config.TEMPEST_CONF


@six.add_metaclass(abc.ABCMeta)
class BaseArgusScenario(manager.ScenarioTest):
    instance_preparer = None

    @classmethod
    def create_test_server(cls, wait_until='ACTIVE', **kwargs):
        _, server = cls.servers_client.create_server(
            data_utils.rand_name(cls.__name__ + "-instance"),
            TEMPEST_CONF.compute.image_ref,
            TEMPEST_CONF.compute.flavor_ref,
            **kwargs)
        cls.servers_client.wait_for_server_status(
            server['id'], wait_until)
        return server

    @classmethod
    def create_keypair(cls):
        _, cls.keypair = cls.keypairs_client.create_keypair(
            cls.__name__ + "-key")
        with open(TEMPEST_CONF.compute.path_to_private_key, 'w') as stream:
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
    def setUpClass(cls):
        super(BaseArgusScenario, cls).setUpClass()

        cls.server = None
        cls.security_groups = []
        cls.security_groups_rules = []
        cls.subnets = []
        cls.routers = []
        cls.floating_ips = {}

        cls.create_keypair()
        metadata = {'network_config': str({'content_path':
                                           'random_value_test_random'})}

        encoded_data = base64.encodestring(
            util.get_resource('multipart_metadata'))

        cls.server = cls.create_test_server(
            wait_until='ACTIVE',
            key_name=cls.keypair['name'],
            disk_config='AUTO',
            user_data=encoded_data,
            meta=metadata)
        cls._assign_floating_ip()
        cls._create_security_groups()


    @classmethod
    def tearDownClass(cls):
        for rule in cls.security_groups_rules:
            cls.security_groups_client.delete_security_group_rule(rule['id'])
        cls.servers_client.remove_security_group(
            cls.server['id'], cls.security_group['name'])

        cls.servers_client.delete_server(cls.server['id'])
        cls.servers_client.wait_for_server_termination(cls.server['id'])
        cls.floating_ips_client.delete_floating_ip(cls.floating_ip['id'])
        cls.keypairs_client.delete_keypair(cls.keypair['name'])
        os.remove(TEMPEST_CONF.compute.path_to_private_key)

        super(BaseArgusScenario, cls).tearDownClass()

    def setUp(self):
        super(BaseArgusScenario, self).setUp()
        # It should be guaranteed that it's called only once,
        # so a second call is a no-op.
        self.prepare_instance()

    def password(self):
        _, encoded_password = self.servers_client.get_password(
            self.server['id'])
        return util.decrypt_password(
            private_key=TEMPEST_CONF.compute.path_to_private_key,
            password=encoded_password['password'])

    @abc.abstractmethod
    def get_remote_client(self, username=None, password=None):
        """Get a remote client to the underlying instance.

        This is different than :attr:`remote_client`, because that
        will always return a client with predefined credentials,
        while this method allows for a fine-grained control
        over this aspect.
        `password` can be omitted if authentication by
        SSH key is used.
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
        return self.images_client.get_image(TEMPEST_CONF.compute.image_ref)

    def instance_server(self):
        return self.servers_client.get_server(self.server['id'])


class BaseWindowsScenario(BaseArgusScenario):
    """Base class for Windows-based tests."""
    instance_preparer = prepare.WindowsInstancePreparer

    def get_remote_client(self, username=None, password=None):
        if username is None:
            username = CONF.argus.default_ci_username
        if password is None:
            password = CONF.argus.default_ci_password
        return util.WinRemoteClient(self.floating_ip['ip'],
                                    username,
                                    password)
    remote_client = util.cached_property(get_remote_client)
