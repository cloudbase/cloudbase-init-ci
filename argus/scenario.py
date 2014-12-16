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
from tempest.openstack.common import log as logging
from tempest.scenario import manager
from tempest.scenario import utils as test_utils

from argus import config
from argus import prepare
from argus import util

LOG = logging.getLogger("cbinit")

CONF = config.CONF
TEMPEST_CONF = config.TEMPEST_CONF


@six.add_metaclass(abc.ABCMeta)
class BaseArgusScenario(manager.ScenarioTest):

    # Various classmethod utilities used in setUpClass and tearDownClass

    @classmethod
    def _wait_until(cls, server, wait_until):
        try:
            cls.servers_client.wait_for_server_status(
                server['id'], wait_until)
        except Exception:
            LOG.exception("Error occurred while waiting for server %s", server)

    @classmethod
    def create_test_server(cls, wait_until='ACTIVE', **kwargs):
        """Wrapper utility that returns a test server."""
        # TODO(cpopa): add image_ref so it can be run for different images
        name = data_utils.rand_name(cls.__name__ + "-instance")
        flavor = TEMPEST_CONF.compute.flavor_ref
        image_id = TEMPEST_CONF.compute.image_ref

        _, server = cls.servers_client.create_server(
            name, image_id, flavor, **kwargs)

        cls._wait_until(server, wait_until)
        cls.server = server

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

    # Instance creation and termination.

    @classmethod
    def setUpClass(cls):
        super(BaseArgusScenario, cls).setUpClass()

        cls.server = None
        cls.security_groups = []
        cls.subnets = []
        cls.routers = []
        cls.floating_ips = {}

        cls.create_keypair()
        metadata = {'network_config': str({'content_path':
                                           'random_value_test_random'})}

        encoded_data = base64.encodestring(
            util.get_resource('multipart_metadata'))

        cls.create_test_server(wait_until='ACTIVE',
                               key_name=cls.keypair['name'],
                               disk_config='AUTO',
                               user_data=encoded_data,
                               meta=metadata)
        cls._assign_floating_ip()

    @classmethod
    def tearDownClass(cls):
        cls.servers_client.delete_server(cls.server['id'])
        cls.servers_client.wait_for_server_termination(cls.server['id'])
        cls.floating_ips_client.delete_floating_ip(cls.floating_ip['id'])
        cls.keypairs_client.delete_keypair(cls.keypair['name'])

        os.remove(TEMPEST_CONF.compute.path_to_private_key)

        super(BaseArgusScenario, cls).tearDownClass()

    # Test preparations.

    def setUp(self):
        super(BaseArgusScenario, self).setUp()

        # Setup image and flavor the test instance
        # Support both configured and injected values
        if not hasattr(self, 'image_ref'):
            self.image_ref = TEMPEST_CONF.compute.image_ref
        if not hasattr(self, 'flavor_ref'):
            self.flavor_ref = TEMPEST_CONF.compute.flavor_ref
        self.image_utils = test_utils.ImageUtils()

        if not self.image_utils.is_flavor_enough(self.flavor_ref,
                                                 self.image_ref):
            raise self.skipException(
                '{image} does not fit in {flavor}'.format(
                    image=self.image_ref, flavor=self.flavor_ref
                )
            )

        self.change_security_group(self.server['id'])
        self.prepare_instance()

    def tearDown(self):
        try:
            self.servers_client.remove_security_group(
                self.server['id'], self.security_group['name'])
        except Exception:
            LOG.exception("Failed removing security group.")
        super(BaseArgusScenario, self).tearDown()

    # Utilities used by setUp.

    def _add_security_group_exceptions(self, secgroup):
        """Override this to add custom security group exceptions."""

    def _create_security_group(self):
        security_group = super(BaseArgusScenario, self)._create_security_group()
        self._add_security_group_exceptions(security_group['id'])
        return security_group

    def change_security_group(self, server_id):
        self.security_group = self._create_security_group()
        self.servers_client.add_security_group(server_id,
                                               self.security_group['name'])

    def password(self):
        _, encoded_password = self.servers_client.get_password(
            self.server['id'])
        return util.decrypt_password(
            private_key=TEMPEST_CONF.compute.path_to_private_key,
            password=encoded_password['password'])

    @abc.abstractmethod
    def prepare_instance(self):
        """Generic function for preparing an instance before doing tests."""

    @abc.abstractmethod
    @property
    def remote_client(self):
        """Get a client to the underlying instance."""

    @property
    def run_command_verbose(self):
        return self.remote_client.run_command_verbose

    def get_image_ref(self):
        return self.images_client.get_image(TEMPEST_CONF.compute.image_ref)

    def instance_server(self):
        return self.servers_client.get_server(self.server['id'])


class BaseWindowsScenario(BaseArgusScenario):
    """Base class for Windows-based tests."""

    def _add_security_group_exceptions(self, secgroup_id):
        # TODO(cpopa): this is almost a verbatim copy of
        # _create_loginable_secgroup_rule. Unfortunately, we can't provide
        # custom rules otherwise.
        _client = self.security_groups_client
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
        ]
        for ruleset in rulesets:
            _, sg_rule = _client.create_security_group_rule(secgroup_id,
                                                            **ruleset)
            self.addCleanup(self.delete_wrapper,
                            _client.delete_security_group_rule,
                            sg_rule['id'])

    @util.run_once
    def _prepare_instance_for_test(self):
        prepare.WindowsInstancePreparer(
            self.server['id'],
            self.servers_client,
            self.remote_client).prepare()

    def prepare_instance(self):
        # Since we create the server in setUpClass, it would have
        # been nice to create  the security groups there, too,
        # in order to build them only once.
        # Unfortunately, we don't have access there to
        # methods required to do this.
        self.change_security_group(self.server['id'])
        self._prepare_instance_for_test()

    def get_remote_client(self, *args, **kwargs):
        return util.WinRemoteClient(
            self.floating_ip['ip'],
            CONF.argus.default_ci_username,
            CONF.argus.default_ci_password)

    remote_client = util.cached_property(get_remote_client)
