# Copyright 2016 Cloudbase Solutions Srl
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

# pylint: disable=no-value-for-parameter, protected-access, arguments-differ
# pylint: disable= unused-argument, no-member, attribute-defined-outside-init

import copy
import unittest
from argus.backends.tempest import tempest_backend
from argus.unit_tests import test_utils
from argus import util


try:
    import unittest.mock as mock
except ImportError:
    import mock


LOG = util.get_logger()


class FakeBaseTempestBackend(tempest_backend.BaseTempestBackend):

    def __init__(self, name, userdata, metadata, availability_zone):
        super(FakeBaseTempestBackend, self).__init__(
            name, userdata, metadata, availability_zone)

    def get_remote_client(self, **kwargs):
        return "fake get_remote_client"

    def remote_client(self):
        return "fake_remote_client"


class TestBaseTempestBackend(unittest.TestCase):

    @mock.patch('argus.config.CONFIG.argus')
    @mock.patch('argus.backends.tempest.manager.APIManager')
    def setUp(self, mock_api_manager, mock_config):
        mock_config.openstack.image_ref = "fake image ref"
        mock_config.openstack.flavor_ref = "fake flavor ref"
        name = mock.sentinel
        userdata = "fake userdata"
        metadata = mock.sentinel
        availability_zone = mock.sentinel
        self._base_tempest_backend = FakeBaseTempestBackend(
            name, userdata, metadata, availability_zone)

    @mock.patch('argus.config.CONFIG.argus')
    def test__configure_networking(self, mock_config):
        mock_network = mock.Mock()
        mock_network.subnet = {"id": "fake id"}
        mock_primary_credentials = mock.Mock()
        mock_primary_credentials.return_value = mock_network
        (self._base_tempest_backend._manager.
         primary_credentials) = mock_primary_credentials

        mock_subnets_client = mock.Mock()
        mock_subnets_client.update_subnet.return_value = None
        (self._base_tempest_backend.
         _manager.subnets_client) = mock_subnets_client

        mock_argus = mock.Mock()
        mock_argus.dns_nameservers.return_value = "fake dns nameservers"
        mock_config.argus = mock_argus

        self._base_tempest_backend._configure_networking()

        (self._base_tempest_backend._manager.subnets_client.
         update_subnet.assert_called_once())
        (self._base_tempest_backend._manager.subnets_client.
         update_subnet.assert_called_once())

    @mock.patch('argus.util.rand_name', return_value="fake-server")
    @mock.patch('tempest.common.waiters.wait_for_server_status')
    def _test_create_server(self, mock_waiters, mock_util,
                            kwargs, wait_until=None):
        fake_server = {
            'server': {
                'id': "fake server id"
            }
        }
        stripped_kwargs = copy.deepcopy(kwargs)
        for key, value in list(stripped_kwargs.items()):
            if not value:
                del stripped_kwargs[key]

        (self._base_tempest_backend._manager.servers_client.
         create_server) = mock.Mock(return_value=fake_server)
        self._base_tempest_backend.image_ref = "fake image ref"
        self._base_tempest_backend.flavor_ref = "fake flavor ref"
        self._base_tempest_backend._name = "fake name"

        if wait_until is not None:
            result = (self._base_tempest_backend
                      ._create_server(wait_until, kwargs))
        else:
            result = self._base_tempest_backend._create_server(**kwargs)

        self.assertEqual(result, {"id": "fake server id"})
        (self._base_tempest_backend._manager.servers_client.create_server.
         assert_called_once_with(name="fake-server-instance",
                                 imageRef="fake image ref",
                                 flavorRef="fake flavor ref",
                                 **stripped_kwargs))
        if wait_until is not None:
            mock_waiters.assert_called_once_with(
                self._base_tempest_backend._manager.servers_client,
                "fake server id", wait_until)
        else:
            mock_waiters.assert_called_once_with(
                self._base_tempest_backend._manager.servers_client,
                "fake server id", 'ACTIVE')

    def test_create_server(self):
        kwargs = {
            "arg 1": "value 1",
            "arg 2": "value 2",
            "arg 3": None,
            "arg 4": "value 4"
        }
        self._test_create_server(kwargs=kwargs)

    def test__assign_floating_ip(self):
        mock_create_floating_ip = mock.Mock()
        mock_create_floating_ip.return_value = {
            "floating_ip": {
                "ip": "fake ip"
            }
        }

        mock_floating_ips_client = mock.Mock()
        mock_floating_ips_client.create_floating_ip = mock_create_floating_ip
        (mock_floating_ips_client.associate_floating_ip_to_server
         .return_value) = None

        mock_internal_instance_id = mock.Mock()
        mock_internal_instance_id.return_value = "fake id"

        (self._base_tempest_backend._manager.
         floating_ips_client) = mock_floating_ips_client
        (self._base_tempest_backend.
         internal_instance_id) = mock_internal_instance_id

        result = self._base_tempest_backend._assign_floating_ip()
        self.assertEqual(result, {"ip": "fake ip"})
        (self._base_tempest_backend._manager.floating_ips_client.
         associate_floating_ip_to_server.assert_called_once_with(
             "fake ip", "fake id"))

    def test_get_mtu(self):
        mock_get_mtu = mock.Mock()
        mock_get_mtu.return_value = "fake mtu"

        self._base_tempest_backend._manager.get_mtu = mock_get_mtu
        result = self._base_tempest_backend.get_mtu()
        self.assertEqual(result, "fake mtu")
        self._base_tempest_backend._manager.get_mtu.assert_called_once()

    def test__add_security_group_exceptions(self):
        mock_security_group_rules_client = mock.Mock()
        (mock_security_group_rules_client.create_security_group_rule
         .return_value) = {"security_group_rule": "fake sg_rule"}
        (self._base_tempest_backend._manager
         .security_group_rules_client) = mock_security_group_rules_client

        result = (self._base_tempest_backend.
                  _add_security_group_exceptions("fake secgroup_id"))
        for item in result:
            self.assertEqual(item, "fake sg_rule")

    def test__create_security_groups(self):
        fake_security_group = {
            "security_group": {
                "id": [
                    {"id": 1},
                    {"id": 2},
                    {"id": 3},
                    {"id": 4},
                    {"id": 5}
                ],
                "name": "fake name"
            }
        }

        mock_security_groups_client = mock.Mock()
        (mock_security_groups_client.create_security_group
         .return_value) = fake_security_group
        (self._base_tempest_backend._manager
         .security_groups_client) = mock_security_groups_client
        self._base_tempest_backend._security_groups_rules = []

        self._base_tempest_backend._add_security_group_exceptions = mock.Mock(
            return_value=fake_security_group["security_group"]["id"])

        self._base_tempest_backend._manager.servers_client = mock.Mock()
        self._base_tempest_backend.internal_instance_id = mock.Mock(
            return_value="fake ip")

        result = self._base_tempest_backend._create_security_groups()

        self.assertEqual(result, fake_security_group["security_group"])
        (self._base_tempest_backend._manager.security_groups_client.
         create_security_group.assert_called_once())
        self._base_tempest_backend.internal_instance_id.assert_called_once()
        (self._base_tempest_backend._manager.servers_client.add_security_group
         .assert_called_once())
        self.assertEqual(self._base_tempest_backend._security_groups_rules,
                         [1, 2, 3, 4, 5])

    @mock.patch('tempest.common.waiters.wait_for_server_termination')
    def _test_cleanup(self, mock_waiters, security_groups_rules=None,
                      security_group=None, server=None, floating_ip=None,
                      keypair=None):
        expected_logging = ["Cleaning up..."]

        if security_groups_rules is not None:
            (self._base_tempest_backend.
             _security_groups_rules) = security_groups_rules
            (self._base_tempest_backend._manager.security_group_rules_client.
             delete_security_group_rule) = mock.Mock()

        if security_group is not None:
            (self._base_tempest_backend._manager.servers_client
             .remove_security_group) = mock.Mock()
            self._base_tempest_backend.internal_instance_id = mock.Mock(
                return_value="fake id")
            self._base_tempest_backend._security_group = security_group

        if server is not None:
            mock_servers_client = mock.Mock()
            mock_servers_client.delete_server = mock.Mock()
            (self._base_tempest_backend._manager.
             servers_client) = mock_servers_client
            self._base_tempest_backend.internal_instance_id = mock.Mock(
                return_value="fake id")
            self._base_tempest_backend._server = server

        if floating_ip is not None:
            (self._base_tempest_backend._manager.floating_ips_client.
             delete_floating_ip) = mock.Mock()
            self._base_tempest_backend._floating_ip = floating_ip

        if keypair is not None:
            self._base_tempest_backend._keypair = keypair

        self._base_tempest_backend._manager.cleanup_credentials = mock.Mock()

        with test_utils.LogSnatcher('argus.backends.tempest.'
                                    'tempest_backend') as snatcher:
            self._base_tempest_backend.cleanup()

        if security_groups_rules is not None:
            (self.assertEqual(
                self._base_tempest_backend._manager.
                security_group_rules_client.delete_security_group_rule.
                call_count,
                len(security_groups_rules)))

        if security_group is not None:
            (self._base_tempest_backend._manager.servers_client.
             remove_security_group.assert_called_once_with(
                 server_id="fake id",
                 name=security_group['name']))
            (self._base_tempest_backend.internal_instance_id.
             assert_called_once())

        if server is not None:
            (self._base_tempest_backend._manager.servers_client.delete_server
             .assert_called_once_with("fake id"))
            (mock_waiters.assert_called_once_with(
                self._base_tempest_backend._manager.servers_client,
                "fake id"))
            self.assertEqual(
                self._base_tempest_backend.internal_instance_id.call_count, 2)
        if floating_ip is not None:
            (self._base_tempest_backend._manager.floating_ips_client.
             delete_floating_ip.assert_called_once_with(floating_ip['id']))

        if keypair is not None:
            self._base_tempest_backend._keypair.destroy.assert_called_once()

        (self._base_tempest_backend._manager.cleanup_credentials.
         assert_called_once())
        self.assertEqual(expected_logging, snatcher.output)

    def test_cleanup_security_groups_rules(self):
        fake_rules = ["rule 1", "rule 2", "rule 3", "rule 4"]
        self._test_cleanup(security_groups_rules=fake_rules)

    def test_cleanup_security_group(self):
        self._test_cleanup(security_group={'name': "fake name"})

    def test_cleanup_server(self):
        self._test_cleanup(server="fake server")

    def test_cleanup_floating_ip(self):
        self._test_cleanup(floating_ip={"id": "fake floating ip id"})

    def test_cleanup_keypair(self):
        self._test_cleanup(keypair=mock.Mock())

    def test_cleanup_credentials(self):
        self._test_cleanup()

    def test_instance_setup_create_server(self):
        expected_logging = ["Creating server..."]
        self._base_tempest_backend._configure_networking = mock.Mock()
        self._base_tempest_backend._manager.create_keypair = mock.Mock()
        self._base_tempest_backend._create_server = mock.Mock(
            return_value="fake server")
        self._base_tempest_backend._assign_floating_ip = mock.Mock()
        self._base_tempest_backend._create_security_groups = mock.Mock()
        self._base_tempest_backend._availability_zone = mock.Mock()
        self._base_tempest_backend.__get_id_tenant_network = mock.Mock()

        with test_utils.LogSnatcher('argus.backends.base') as snatcher:
            self._base_tempest_backend.setup_instance()

        self.assertEqual(expected_logging, snatcher.output)
        self._base_tempest_backend._configure_networking.assert_called_once()
        self._base_tempest_backend._manager.create_keypair.assert_called_once()
        self._base_tempest_backend._create_server.assert_called_once()
        self._base_tempest_backend._assign_floating_ip.assert_called_once()
        self._base_tempest_backend._create_security_groups.assert_called_once()

    def test_reboot_instance(self):
        self._base_tempest_backend._manager.reboot_instance = mock.Mock(
            return_value="fake reboot")
        self._base_tempest_backend.internal_instance_id = mock.Mock(
            return_value="fake id")

        result = self._base_tempest_backend.reboot_instance()
        self.assertEqual(result, "fake reboot")
        (self._base_tempest_backend._manager.reboot_instance.
         assert_called_once_with("fake id"))

    def test_instance_password(self):
        self._base_tempest_backend._manager.instance_password = mock.Mock(
            return_value="fake password")
        self._base_tempest_backend.internal_instance_id = mock.Mock(
            return_value="fake id")
        self._base_tempest_backend._keypair = "fake keypair"

        result = self._base_tempest_backend.instance_password()
        self.assertEqual(result, "fake password")
        self._base_tempest_backend.internal_instance_id.assert_called_once()

    def test_internal_instance_id(self):
        self._base_tempest_backend._server = {"id": "fake server"}
        result = self._base_tempest_backend.internal_instance_id()
        self.assertEqual(result, "fake server")

    def test_instance_output(self):
        self._base_tempest_backend._manager.instance_output = mock.Mock(
            return_value="fake output")
        self._base_tempest_backend.internal_instance_id = mock.Mock(
            return_value="fake id")

        result = self._base_tempest_backend.instance_output(limit=10)
        self.assertEqual(result, "fake output")
        self._base_tempest_backend.internal_instance_id.assert_called_once()
        self._base_tempest_backend._manager.test_instance_output("fake id", 10)

    def test_instance_server(self):
        self._base_tempest_backend._manager.instance_server = mock.Mock(
            return_value="fake instance server")
        self._base_tempest_backend.internal_instance_id = mock.Mock(
            return_value="fake instance id")

        result = self._base_tempest_backend.instance_server()
        self.assertEqual(result, "fake instance server")
        self._base_tempest_backend.internal_instance_id.assert_called_once()

    def test_public_key(self):
        mock_keypair = mock.Mock()
        mock_keypair.public_key = "fake public key"
        self._base_tempest_backend._keypair = mock_keypair
        result = self._base_tempest_backend.public_key()
        self.assertEqual(result, "fake public key")

    def test_private_key(self):
        mock_keypair = mock.Mock()
        mock_keypair.private_key = "fake private key"
        self._base_tempest_backend._keypair = mock_keypair
        result = self._base_tempest_backend.private_key()
        self.assertEqual(result, "fake private key")

    def test_get_image_by_ref(self):
        (self._base_tempest_backend._manager.compute_images_client.
         show_image) = mock.Mock(return_value={"image": "fake image"})
        self._base_tempest_backend._conf = mock.Mock()
        result = self._base_tempest_backend.get_image_by_ref()
        self.assertEqual(result, "fake image")

    def test_floating_ip(self):
        self._base_tempest_backend._floating_ip = {"ip": "fake ip"}
        result = self._base_tempest_backend.floating_ip()
        self.assertEqual(result, "fake ip")


class TestBaseWindowsTempestBackend(unittest.TestCase):

    @mock.patch('argus.config.CONFIG.argus')
    @mock.patch('argus.backends.tempest.manager.APIManager')
    def setUp(self, mock_api_manager, mock_config):
        mock_config.openstack.image_ref = "fake image ref"
        mock_config.openstack.flavor_ref = "fake flavor ref"
        name = mock.sentinel
        userdata = "fake userdata"
        metadata = mock.sentinel
        availability_zone = mock.sentinel
        self._base = tempest_backend.BaseWindowsTempestBackend(
            name, userdata, metadata, availability_zone)

    @mock.patch('argus.config.CONFIG.argus')
    @mock.patch('argus.backends.base.CloudBackend._get_log_template')
    def test_get_log_template(self, mock_get_log, mock_config):
        mock_get_log.return_value = "fake call"
        mock_config.build = "fake build"
        mock_config.arch = "fake arch"

        expected_result = "{}-{}-{}".format(mock_config.build,
                                            mock_config.arch,
                                            mock_get_log.return_value)
        result = self._base._get_log_template("fake suffix")

        self.assertEqual(result, expected_result)
