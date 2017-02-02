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

# pylint: disable=no-value-for-parameter, too-many-lines, protected-access
# pylint: disable=too-many-public-methods, arguments-differ, unused-argument

import unittest
from argus.backends.tempest import cloud
from argus import config as argus_config
from argus import exceptions
from argus import util

try:
    import unittest.mock as mock
except ImportError:
    import mock

with util.restore_excepthook():
    from tempest.common import dynamic_creds

CONFIG = argus_config.CONFIG


class TestNetworkWindowsBackend(unittest.TestCase):

    @mock.patch('argus.backends.tempest.manager.APIManager')
    def setUp(self, _):
        args = {
            "name": mock.sentinel,
            "userdata": "fake userdata",
            "metadata": mock.sentinel,
            "availability_zone": mock.sentinel
        }
        self._network_windows_backend = cloud.NetworkWindowsBackend(**args)

    def test_get_isolated_network(self):
        mock_network = mock.Mock()
        mock_network.network = "fake network"
        mock_manager = mock.Mock()
        mock_manager.primary_credentials.return_value = mock_network
        self._network_windows_backend._manager = mock_manager

        result = self._network_windows_backend._get_isolated_network()

        self.assertEqual("fake network", result)
        (self._network_windows_backend._manager.
         primary_credentials.assert_called_once())

    def test_get_networks(self):
        mock_networks_client = mock.Mock()
        mock_networks_client.list_networks.return_value = {
            "networks": [
                {
                    "id": "1",
                    "router:external": None,
                },
                {
                    "id": "2",
                    "router:external": "fake router"
                },
                {
                    "id": "3",
                    "router:external": None
                }
            ]
        }
        (self._network_windows_backend._manager.
         networks_client) = mock_networks_client
        (self._network_windows_backend.
         _get_isolated_network) = mock.Mock(return_value={'id': '3'})

        expected_result = [
            {
                'uuid': "3"
            },
            {
                'uuid': "1"
            }
        ]

        result = self._network_windows_backend._get_networks()

        self.assertListEqual(result, expected_result)
        (self._network_windows_backend._manager.networks_client.
         list_networks.assert_called_once())
        (self._network_windows_backend._get_isolated_network.
         assert_called_once())

    def test_get_no_networks(self):
        (self._network_windows_backend._manager.networks_client.
         list_networks) = mock.Mock(return_value={})
        with self.assertRaises(exceptions.ArgusError):
            result = self._network_windows_backend._get_networks()
            self.assertEqual(result, "Networks not found.")

    @mock.patch('argus.config.CONFIG.argus')
    @mock.patch('argus.util.rand_name')
    @mock.patch('argus.util.next_ip')
    @mock.patch('argus.util.get_namedtuple')
    def test_create_private_network(self, mock_get_namedtuple, mock_next_ip,
                                    mock_rand_name, mock_config):
        mock_tenant_id = mock.Mock()
        mock_tenant_id.tenant_id = "fake tenant id"
        mock_primary_credentials = mock.Mock()
        mock_primary_credentials.return_value = mock_tenant_id

        mock_isolated_creds = mock.Mock()
        (mock_isolated_creds._create_network_resources.
         return_value) = ("fake net resource", ) * 4
        mock_isolated_creds._creds = {}

        mock_fake_net_creds = mock.Mock()
        mock_fake_net_creds.subnet = {"id": "fake subnet id"}
        mock_fake_net_creds.network = {"id": "fake network id"}

        mock_get_namedtuple.return_value = mock_fake_net_creds

        mock_subnet_client = mock.Mock()
        mock_config.argus.dns_nameservers = "fake nameservers"
        (mock_subnet_client.show_subnet.return_value) = {
            "subnet": {
                "allocation_pools": {
                    "start": "fake start"
                }
            }
        }

        mock_rand_name.return_value = "fake-name-"

        (self._network_windows_backend.
         primary_credentials) = mock_primary_credentials
        (self._network_windows_backend._manager.
         isolated_creds) = mock_isolated_creds

        self._network_windows_backend._create_private_network()

        (self._network_windows_backend._manager.primary_credentials.
         assert_called_once())
        (self._network_windows_backend._manager.isolated_creds.
         _create_network_resources.assert_called_once())
        mock_get_namedtuple.assert_called_once()
        (self.assertEqual(self._network_windows_backend._manager.
                          subnets_client.update_subnet.call_count, 2))
        (self._network_windows_backend._manager.subnets_client.
         show_subnet.assert_called_once())
        mock_next_ip.assert_called_once()
        mock_rand_name.assert_called_once()
        (self._network_windows_backend._manager.subnets_client.
         create_subnet.assert_called_once())

    def test_setup_instance_no_instance(self):
        self._network_windows_backend._manager.isolated_creds = None
        with self.assertRaises(exceptions.ArgusError):
            result = self._network_windows_backend.setup_instance()
            self.assertEqual(result, "Network resources are not available.")

    @mock.patch('argus.backends.tempest.tempest_backend.'
                'BaseWindowsTempestBackend.setup_instance')
    def test_setup_instance(self, mock_super_setup_instance):
        (self._network_windows_backend._manager.
         isolated_creds) = mock.Mock()
        (self._network_windows_backend._manager.
         isolated_creds) = mock.Mock(
             spec=dynamic_creds.DynamicCredentialProvider)
        self._network_windows_backend._create_private_network = mock.Mock()
        (self._network_windows_backend.
         _get_networks) = mock.Mock(return_value="fake networks")

        self._network_windows_backend.setup_instance()

        (self._network_windows_backend._create_private_network.
         assert_called_once())
        (self._network_windows_backend.
         _get_networks.assert_called_once())
        mock_super_setup_instance.assert_called_once()

    def test_find_ip_address(self):
        fake_port = {
            "fixed_ips": [
                {
                    "subnet_id": "1",
                    "ip_address": "1.1.1.1"
                },
                {
                    "subnet_id": "2",
                    "ip_address": "2.2.2.2"
                },
                {
                    "subnet_id": "3",
                    "ip_address": "3.3.3.3"
                }
            ]
        }

        result = self._network_windows_backend._find_ip_address(fake_port, "2")
        self.assertEqual(result, "2.2.2.2")

    def test_find_ip_address_no_subnet_id(self):
        fake_port = {
            "fixed_ips": [
                {
                    "subnet_id": "1",
                    "ip_address": "1.1.1.1"
                },
                {
                    "subnet_id": "2",
                    "ip_address": "2.2.2.2"
                },
                {
                    "subnet_id": "3",
                    "ip_address": "3.3.3.3"
                }
            ]
        }

        result = self._network_windows_backend._find_ip_address(fake_port, "4")
        self.assertEqual(result, None)

    @mock.patch('argus.util.cidr2netmask')
    def _test_get_network_interfaces(self, mock_cidr2netmask, ip_address=None):
        mock_ports_client = mock.Mock()
        mock_ports_client.list_ports.return_value = {
            "ports": [
                {
                    "device_owner": ["fake owner 1", "fake owner 2"],
                },
                {
                    "device_owner": ["compute"],
                    "mac_address": "fake mac"
                },
                {
                    "device_owner": ["fake owner 1", "fake owner 2"]
                },
                {
                    "device_owner": ["fake owner", "compute"],
                    "mac_address": "fake mac"
                }
            ]
        }
        subnet = {
            "ip_version": 6,
            "enable_dhcp": "fake enable dhcp",
            "dns_nameservers": "fake dns nameservers",
            "gateway_ip": "fake gateway ip",
            "cidr": "fake/cidr"
        }
        mock_networks_client = mock.Mock()
        mock_networks_client.show_network.return_value = {
            "network": {
                "subnets": [subnet]
            }
        }
        mock_subnet_clients = mock.Mock()
        mock_subnet_clients.show_subnet.return_value = {
            "subnet": subnet
        }

        mock_find_ip_address = mock.Mock()
        if ip_address is None:
            expected_ip_address_count = 4
            mock_find_ip_address.return_value = None
        else:
            mock_find_ip_address.return_value = "1.2.3.4"
            expected_ip_address_count = 2

        self._network_windows_backend._manager.ports_client = mock_ports_client
        (self._network_windows_backend._manager.
         networks_client) = mock_networks_client
        (self._network_windows_backend._manager.
         subnets_client) = mock_subnet_clients
        self._network_windows_backend._find_ip_address = mock_find_ip_address

        expected_result = {
            'netmask6': 'cidr',
            'netmask': None,
            'dns6': 'fake dns nameservers',
            'gateway6': 'fake gateway ip',
            'dns': None,
            'address': None,
            'dhcp': 'fake enable dhcp',
            'gateway': None,
            'address6': None,
            'mac': None
        }
        if ip_address is not None:
            expected_result['address6'] = ip_address
            expected_result['mac'] = 'FAKE MAC'

        self._network_windows_backend._networks = [
            {
                'uuid': 'fake uuid 1'
            },
            {
                'uuid': 'fake uuid 2'
            }
        ]
        result = self._network_windows_backend.get_network_interfaces()
        self.assertDictEqual(result[0], expected_result)

        self.assertEqual(self._network_windows_backend._find_ip_address.
                         call_count, expected_ip_address_count)
        self.assertEqual(self._network_windows_backend._manager.
                         networks_client.show_network.call_count, 2)

    def test_get_network_interfaces(self):
        self._test_get_network_interfaces(ip_address="1.2.3.4")

    def test_get_network_interfaces_no_ip(self):
        self._test_get_network_interfaces(ip_address=None)


class TestRescueWindowsBackend(unittest.TestCase):

    @mock.patch('argus.backends.tempest.manager.APIManager')
    def setUp(self, _):
        args = {
            "name": mock.sentinel,
            "userdata": "fake userdata",
            "metadata": mock.sentinel,
            "availability_zone": mock.sentinel
        }
        self._rescuse_windows_backend = cloud.RescueWindowsBackend(**args)

    @mock.patch('argus.backends.tempest.tempest_backend.'
                'BaseWindowsTempestBackend.internal_instance_id')
    @mock.patch('tempest.common.waiters.wait_for_server_status')
    def test_rescue_server(self, mock_waiters, mock_internal_instance_id):
        self._rescuse_windows_backend._manager.servers_client = mock.Mock()
        mock_internal_instance_id.return_value = "fake id"

        self._rescuse_windows_backend.rescue_server()

        (self._rescuse_windows_backend._manager.servers_client.rescue_server.
         assert_called_once_with("fake id",
                                 adminPass=CONFIG.openstack.image_password))
        mock_waiters.assert_called_once_with(
            self._rescuse_windows_backend._manager.servers_client,
            "fake id", 'RESCUE')
        self.assertEqual(mock_internal_instance_id.call_count, 2)

    @mock.patch('argus.backends.tempest.tempest_backend.'
                'BaseWindowsTempestBackend.internal_instance_id')
    @mock.patch('tempest.common.waiters.wait_for_server_status')
    def test_unrescue_server(self, mock_waiters, mock_internal_instance_id):
        self._rescuse_windows_backend._manager.servers_client = mock.Mock()
        mock_internal_instance_id.return_value = "fake id"

        self._rescuse_windows_backend.unrescue_server()

        (self._rescuse_windows_backend._manager.servers_client.unrescue_server.
         assert_called_once_with("fake id"))
        mock_waiters.assert_called_once_with(
            self._rescuse_windows_backend._manager.servers_client,
            "fake id", 'ACTIVE')
        self.assertEqual(mock_internal_instance_id.call_count, 2)
