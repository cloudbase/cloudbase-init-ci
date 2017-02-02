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

# pylint: disable=no-value-for-parameter, protected-access

import unittest
from argus import config as argus_config
from argus.backends import windows as windows_backend

try:
    import unittest.mock
except ImportError:
    import mock


CONFIG = argus_config.CONFIG


class TestWindowsBackendMixin(unittest.TestCase):

    def setUp(self):
        self._windows_backend_mixin = windows_backend.WindowsBackendMixin()

    @mock.patch('argus.client.windows.WinRemoteClient.__init__')
    def _test_get_remote_client(self, mock_win_remote_client,
                                username=None, password=None):
        expected_username, expected_password = username, password
        if username is None:
            expected_username = CONFIG.openstack.image_username
        if password is None:
            expected_password = CONFIG.openstack.image_password

        self._windows_backend_mixin.floating_ip = mock.Mock()
        self._windows_backend_mixin.floating_ip.return_value = "fake ip"
        mock_win_remote_client.return_value = None
        self._windows_backend_mixin.get_remote_client(username=username,
                                                      password=password,
                                                      protocol="fake protocol")
        mock_win_remote_client.assert_called_once_with(
            "fake ip", expected_username, expected_password,
            transport_protocol="fake protocol")

    def test_get_remote_client_with_username_password(self):
        self._test_get_remote_client(username="fake username",
                                     password="fake password")

    def test_get_remote_client_with_username(self):
        self._test_get_remote_client(username="fake username",
                                     password=None)

    def test_get_remote_client_with_password(self):
        self._test_get_remote_client(username=None,
                                     password="fake password")

    def test_get_remote_client_no_username_password(self):
        self._test_get_remote_client(username=None,
                                     password=None)
