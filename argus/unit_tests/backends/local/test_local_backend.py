# Copyright 2017 Cloudbase Solutions Srl
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

import unittest
from argus.backends.local import local_backend
from argus import util
from argus.unit_tests import test_utils

try:
    import unittest.mock as mock
except ImportError:
    import mock

LOG = util.get_logger()


class TestLocalBackend(unittest.TestCase):

    @test_utils.ConfPatcher('ip', 'fake ip', group='local')
    @test_utils.ConfPatcher('username', 'fake username', group='local')
    @test_utils.ConfPatcher('password', 'fake password', group='local')
    @mock.patch('argus.config')
    def setUp(self, CONFIG):
        self._local_backend = local_backend.LocalBackend()

    @mock.patch('argus.client.windows.WinRemoteClient.__init__')
    def test_get_remote_client(self, mock_remote_client, **kwargs):
            mock_remote_client.return_value = None
            self._local_backend.get_remote_client(protocol="fake protocol")
            mock_remote_client.assert_called_once_with(
                'fake ip', 'fake username', 'fake password',
                transport_protocol='fake protocol')
