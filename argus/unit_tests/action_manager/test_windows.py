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

import unittest

try:
    import unittest.mock as mock
except ImportError:
    import mock

from argus.action_manager import windows
from argus import exceptions


class TestWindowsActionManager(unittest.TestCase):

    def setUp(self):
        mock_client = mock.Mock()
        mock_config = mock.Mock()
        mock_os = mock.Mock()
        self.action_manager = windows.WindowsActionManager(mock_client,
                                                           mock_config,
                                                           mock_os)

    @mock.patch('argus.action_manager.windows.WindowsActionManager.'
                'exists')
    def test_git_clone_exists(self, mock_exists):
        mock_exists.return_value = True
        self.assertRaises(exceptions.ArgusCLIError,
                          self.action_manager.git_clone,
                          'fake_url', 'fake_location')

    @mock.patch('argus.action_manager.windows.WindowsActionManager.'
                'exists')
    def test_git_clone_could_not_clone(self, mock_exists):
        mock_exists.return_value = False
        res = self.action_manager.git_clone('fake_url', 'location', count=0)
        self.assertFalse(res)

    @mock.patch('argus.action_manager.windows.WindowsActionManager.'
                'exists')
    def test_git_clone_successful(self, mock_exists):
        mock_exists.return_value = False
        self.action_manager._client.run_command.return_value = True
        res = self.action_manager.git_clone('fake_url', 'location')
        self.assertTrue(res)

    @mock.patch('time.sleep')
    @mock.patch('argus.action_manager.windows.WindowsActionManager.'
                'rmdir')
    @mock.patch('argus.action_manager.windows.WindowsActionManager.'
                'is_dir')
    @mock.patch('argus.action_manager.windows.WindowsActionManager.'
                'exists')
    def test_git_clone_exception(self, mock_exists, mock_is_dir,
                                 mock_rmdir, mock_sleep):
        mock_exists.side_effect = [False, True, True]
        mock_is_dir.return_value = True
        mock_sleep.return_value = None
        mock_rmdir.return_value = None
        (self.action_manager._client.run_command.
         side_effect) = exceptions.ArgusError
        res = self.action_manager.git_clone('fake_url', 'location', count=2)
        self.assertFalse(res)
