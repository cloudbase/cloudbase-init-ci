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
# pylint: disable=no-member, unused-argument

import unittest
from argus.backends.tempest import manager
from argus import exceptions

try:
    import unittest.mock as mock
except ImportError:
    import mock


class TestAPIManager(unittest.TestCase):

    @mock.patch('tempest.clients.Manager')
    @mock.patch('tempest.common.waiters')
    @mock.patch('tempest.common.credentials_factory.get_credentials_provider')
    def setUp(self, mock_credentials, mock_waiters, mock_clients):
        self._api_manager = manager.APIManager()

    def test_cleanup_credentials(self):
        mock_isolated_creds = mock.Mock()
        mock_isolated_creds.return_value = True
        self._api_manager.isolated_creds = mock_isolated_creds
        self._api_manager.cleanup_credentials()
        mock_isolated_creds.clear_creds.assert_called_once()

    @mock.patch('argus.backends.tempest.manager.Keypair')
    def test_create_key_pair(self, mock_keypair):
        fake_keypair = {
            "public_key": "fake public key",
            "private_key": "fake private key",
            "name": "fake name"
        }
        mock_keypairs_client = mock.Mock()
        mock_keypairs_client.create_keypair.return_value = {
            'keypair': fake_keypair
        }
        self._api_manager.keypairs_client = mock_keypairs_client
        self._api_manager.create_keypair("fake name")
        mock_keypair.assert_called_once()

    @mock.patch('tempest.common.waiters.wait_for_server_status')
    def test_reboot_instance(self, mock_waiters):
        mock_servers_client = mock.Mock()
        mock_servers_client.reboot_server.return_value = None

        self._api_manager.servers_client = mock.Mock()

        self._api_manager.reboot_instance(instance_id="fake id")
        self._api_manager.servers_client.reboot_server.assert_called_once()
        mock_waiters.assert_called_once()

    @mock.patch('argus.util.create_tempfile')
    @mock.patch('argus.util.decrypt_password')
    def test_instance_password(self, mock_decrypt_password,
                               mock_create_temp_file):
        mock_servers_client = mock.Mock()
        mock_servers_client.show_password.return_value = {
            "password": "fake password"
        }

        self._api_manager.servers_client = mock_servers_client
        mock_decrypt_password.return_value = "fake return"
        mock_keypair = mock.Mock()
        mock_keypair.private_key = "fake private key"
        result = self._api_manager.instance_password(instance_id="fake id",
                                                     keypair=mock_keypair)

        self.assertEqual(result, "fake return")
        (self._api_manager.servers_client.show_password.
         assert_called_once_with("fake id"))
        mock_create_temp_file.assert_called_once_with("fake private key")

    def test__instance_output(self):
        mock_servers_client = mock.Mock()
        mock_servers_client.get_console_output.return_value = {
            "output": "fake output"
        }
        self._api_manager.servers_client = mock_servers_client

        result = self._api_manager._instance_output(instance_id="fake id",
                                                    limit="fake limit")
        self.assertEqual(result, "fake output")

    def test_instance_output(self):
        fake_content = "fake content 1\nfake content 2"
        mock__instance_output = mock.Mock()
        mock__instance_output.return_value = fake_content

        self._api_manager._instance_output = mock__instance_output

        self._api_manager.instance_output(instance_id="fake id", limit=10)

        self.assertEqual(2, mock__instance_output.call_count)

    def test_instance_server(self):
        mock_servers_client = mock.Mock()
        mock_servers_client.show_server.return_value = {
            'server': "fake server"
        }
        self._api_manager.servers_client = mock_servers_client

        result = self._api_manager.instance_server(instance_id="fake id")

        self.assertEqual(result, "fake server")
        (self._api_manager.servers_client.show_server.
         assert_called_once_with("fake id"))

    def test_get_mtu(self):
        mock_network = mock.Mock()
        mock_network.network = {"mtu": "fake mtu"}
        mock_primary_credentials = mock.Mock()
        mock_primary_credentials.return_value = mock_network
        self._api_manager.primary_credentials = mock_primary_credentials

        result = self._api_manager.get_mtu()
        self.assertEqual(result, "fake mtu")

    @mock.patch('argus.backends.tempest.manager.APIManager.'
                'primary_credentials')
    def test_get_mtu_fails(self, mock_primary_credentials):
        mock_primary_credentials.side_effect = exceptions.ArgusError(
            "fake exception")
        with self.assertRaises(exceptions.ArgusError):
            result = self._api_manager.get_mtu()
            self.assertEqual('Could not get the MTU from the '
                             'tempest backend: fake exception', result)
            mock_primary_credentials.assert_called_once()


class TestKeypair(unittest.TestCase):

    def setUp(self):
        self._key_pair = manager.Keypair(name="fake name",
                                         public_key="fake public key",
                                         private_key="fake private key",
                                         manager="fake manager")

    def test_destroy(self):
        self._key_pair._manager = mock.Mock()
        (self._key_pair._manager.keypairs_client.delete_keypair.
         return_value) = True
        self._key_pair.destroy()
        (self._key_pair._manager.keypairs_client.delete_keypair.
         assert_called_once_with("fake name"))
