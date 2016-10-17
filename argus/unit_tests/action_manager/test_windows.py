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

# TODO(dtoncu): Refactoring this module in order to avoid pylint disables.

# pylint: disable=no-value-for-parameter, too-many-lines, protected-access
# pylint: disable=too-many-public-methods

import unittest

try:
    import unittest.mock as mock
except ImportError:
    import mock

import requests

from six.moves import urllib_parse as urlparse

from argus.action_manager import windows as action_manager
from argus import config as argus_config
from argus import exceptions
from argus.introspection.cloud import windows as introspection
from argus.unit_tests import test_utils
from argus import util


CONFIG = argus_config.CONFIG


class WindowsActionManagerTest(unittest.TestCase):
    """Tests for windows action manager class."""

    def setUp(self):
        self._client = mock.MagicMock()
        self._os_type = mock.sentinel.os_type

        self._action_manager = action_manager.WindowsActionManager(
            client=self._client, os_type=self._os_type)

    def _test_wait_boot_completion_function(self, run_command_exc=None):
        if run_command_exc:
            self._client.run_command_until_condition = mock.Mock(
                side_effect=run_command_exc)
            with self.assertRaises(run_command_exc):
                action_manager.wait_boot_completion(
                    self._client, test_utils.USERNAME)
        else:
            self._client.run_command_until_condition = mock.Mock()
            self.assertIsNone(
                action_manager.wait_boot_completion(
                    self._client, test_utils.USERNAME))

    def test_wait_boot_completion_function_successful(self):
        self._test_wait_boot_completion_function()

    def test_wait_boot_completion_function_fail(self):
        self._test_wait_boot_completion_function(
            run_command_exc=exceptions.ArgusTimeoutError)

    def test_download_successful(self):
        self._action_manager.download(test_utils.URI, test_utils.LOCATION)

        cmd = ('(New-Object System.Net.WebClient).DownloadFile('
               '"{uri}","{location}")'.format(uri=test_utils.URI,
                                              location=test_utils.LOCATION))

        self._client.run_command_with_retry.assert_called_with(
            cmd, count=util.RETRY_COUNT, delay=util.RETRY_DELAY,
            command_type=util.POWERSHELL)

    def test_download_exception(self):
        (self._client.run_command_with_retry
         .side_effect) = exceptions.ArgusTimeoutError

        with self.assertRaises(exceptions.ArgusTimeoutError):
            self._action_manager.download(test_utils.URI, test_utils.LOCATION)

    @test_utils.ConfPatcher('resources', test_utils.BASE_RESOURCE, 'argus')
    @mock.patch('argus.action_manager.windows.WindowsActionManager.download')
    def _test_download_resource(self, mock_download, expected_uri, exc=None):
        if exc:
            mock_download.side_effect = exc
            with self.assertRaises(exceptions.ArgusTimeoutError):
                self._action_manager.download_resource(
                    test_utils.RESOURCE_LOCATION, test_utils.LOCATION)
            return

        self._action_manager.download_resource(
            test_utils.RESOURCE_LOCATION, test_utils.LOCATION)
        mock_download.assert_called_once_with(
            expected_uri, test_utils.LOCATION)

    def test_download_resource_exception(self):
        self._test_download_resource(
            expected_uri=None,
            exc=exceptions.ArgusTimeoutError)

    def test_download_resource_base_resource_endswith_slash(self):
        self._test_download_resource(
            expected_uri=urlparse.urljoin(
                test_utils.BASE_RESOURCE, test_utils.RESOURCE_LOCATION))

    @test_utils.ConfPatcher('resources', test_utils.BASE_RESOURCE[:-1],
                            'argus')
    @mock.patch('argus.action_manager.windows.WindowsActionManager.download')
    def test_download_resource_base_resource_not_endswith_slash(
            self, mock_download):
        expected_uri = urlparse.urljoin(
            test_utils.BASE_RESOURCE, test_utils.RESOURCE_LOCATION)

        self._action_manager.download_resource(
            test_utils.RESOURCE_LOCATION, test_utils.LOCATION)
        mock_download.assert_called_once_with(
            expected_uri, test_utils.LOCATION)

    @mock.patch('argus.action_manager.windows.WindowsActionManager'
                '.download_resource')
    def _test_execute_resource_script(self, mock_download_resource,
                                      script_type, run_command_exc=None,
                                      download_exc=None):
        if download_exc:
            mock_download_resource.side_effect = download_exc
            with self.assertRaises(download_exc):
                self._action_manager._execute_resource_script(
                    test_utils.PATH, test_utils.PATH_TYPE, script_type)
            return

        self._client.run_command_with_retry = mock.Mock()

        if run_command_exc:
            self._client.run_command_with_retry.side_effect = run_command_exc
            with self.assertRaises(run_command_exc):
                self._action_manager._execute_resource_script(
                    test_utils.PATH, test_utils.PATH_TYPE, script_type)
            return

        instance_location = r"C:\{}".format(
            test_utils.RESOURCE_LOCATION.split('/')[-1])
        cmd = '"{}" {}'.format(instance_location, test_utils.PARAMETERS)

        self._action_manager._execute_resource_script(
            test_utils.RESOURCE_LOCATION, test_utils.PARAMETERS, script_type)

        if script_type == util.BAT_SCRIPT:
            script_type = util.CMD

        mock_download_resource.assert_called_once_with(
            test_utils.RESOURCE_LOCATION, instance_location)
        self._client.run_command_with_retry.assert_called_once_with(
            cmd, count=util.RETRY_COUNT,
            delay=util.RETRY_DELAY, command_type=script_type)

    def test_execute_resource_script_bat_script(self):
        self._test_execute_resource_script(script_type=util.BAT_SCRIPT)

    def test_execute_resource_script_powershell_script(self):
        self._test_execute_resource_script(
            script_type=util.POWERSHELL_SCRIPT_BYPASS)

    def test_execute_resource_script_run_command_exception(self):
        self._test_execute_resource_script(
            script_type=util.BAT_SCRIPT,
            run_command_exc=exceptions.ArgusTimeoutError)

    def test_execute_resource_script_download_resource_exception(self):
        self._test_execute_resource_script(
            script_type=util.POWERSHELL_SCRIPT_BYPASS,
            download_exc=exceptions.ArgusTimeoutError)

    @mock.patch('argus.action_manager.windows.WindowsActionManager'
                '._execute_resource_script')
    def _test_execute_res_script(self, mock_execute_script, test_method,
                                 script_type, exc=None):

        if exc:
            mock_execute_script.side_effect = exc
            with self.assertRaises(exc):
                test_method(
                    test_utils.RESOURCE_LOCATION, test_utils.PARAMETERS)
            return

        test_method(test_utils.RESOURCE_LOCATION, test_utils.PARAMETERS)
        mock_execute_script.assert_called_once_with(
            resource_location=test_utils.RESOURCE_LOCATION,
            parameters=test_utils.PARAMETERS,
            script_type=script_type)

    def test_execute_powershell_resource_script_successful(self):
        test_method = self._action_manager.execute_powershell_resource_script
        self._test_execute_res_script(
            test_method=test_method, script_type=util.POWERSHELL_SCRIPT_BYPASS)

    def test_execute_powershell_resource_script_exception(self):
        test_method = self._action_manager.execute_powershell_resource_script
        self._test_execute_res_script(
            test_method=test_method, script_type=util.POWERSHELL_SCRIPT_BYPASS,
            exc=exceptions.ArgusTimeoutError)

    @mock.patch('argus.action_manager.windows.WindowsActionManager'
                '.download_resource')
    def _test_get_installation_script(self, mock_download_resource, exc=None):

        if exc:
            mock_download_resource.side_effect = exc
            with self.assertRaises(exc):
                self._action_manager.get_installation_script()
            return

        self._action_manager.get_installation_script()
        mock_download_resource.assert_called_once_with(
            test_utils.CBINIT_RESOURCE_LOCATION, test_utils.CBINIT_LOCATION)

    def test_get_installation_script_successful(self):
        self._test_get_installation_script()

    def test_get_installation_script_exception(self):
        self._test_get_installation_script(exc=exceptions.ArgusTimeoutError)

    @mock.patch('argus.action_manager.windows.WindowsActionManager'
                '.wait_boot_completion')
    @mock.patch('argus.action_manager.windows.WindowsActionManager'
                '.download_resource')
    def _test_sysprep(self, mock_download_resource, mock_wait_boot_completion,
                      download_exc=None, run_exc=None, wait_exc=None):
        cmd = r"C:\{}".format(
            test_utils.SYSPREP_RESOURCE_LOCATION.split('/')[-1])

        self._client.run_remote_cmd = mock.Mock()

        if download_exc:
            mock_download_resource.side_effect = download_exc
            with self.assertRaises(download_exc):
                self._action_manager.sysprep()
            self._client.run_remote_cmd.assert_not_called()
            return

        if wait_exc:
            mock_wait_boot_completion.side_effect = wait_exc
            with self.assertRaises(wait_exc):
                self._action_manager.sysprep()
            return

        if run_exc:
            self._client.run_remote_cmd.side_effect = run_exc
            with test_utils.LogSnatcher('argus.action_manager.windows.Windows'
                                        'ActionManager.sysprep') as snatcher:
                self.assertIsNone(self._action_manager.sysprep())
            self.assertEqual(snatcher.output[-2:],
                             ['Currently rebooting...',
                              'Wait for the machine to finish rebooting ...'])
        else:
            self.assertIsNone(self._action_manager.sysprep())

        mock_download_resource.assert_called_once_with(
            test_utils.SYSPREP_RESOURCE_LOCATION, cmd)
        mock_wait_boot_completion.assert_called_once_with()

    def test_sysprep_successful(self):
        self._test_sysprep()

    def test_sysprep_download_resource_fail(self):
        self._test_sysprep(download_exc=exceptions.ArgusTimeoutError)

    def test_sysprep_wait_boot_completion_fail(self):
        self._test_sysprep(wait_exc=exceptions.ArgusTimeoutError)

    def test_sysprep_run_remote_cmd_exc(self):
        self._test_sysprep(run_exc=requests.Timeout)

    @mock.patch('argus.action_manager.windows.WindowsActionManager.'
                'exists')
    def test_git_clone_exists(self, mock_exists):
        mock_exists.return_value = True
        self.assertRaises(exceptions.ArgusCLIError,
                          self._action_manager.git_clone,
                          test_utils.URL, test_utils.LOCATION)

    @mock.patch('argus.action_manager.windows.WindowsActionManager.'
                'exists')
    def test_git_clone_could_not_clone(self, mock_exists):
        mock_exists.return_value = False
        res = self._action_manager.git_clone(test_utils.URL,
                                             test_utils.LOCATION,
                                             count=0)
        self.assertFalse(res)

    @mock.patch('argus.action_manager.windows.WindowsActionManager.'
                'exists')
    def test_git_clone_successful(self, mock_exists):
        mock_exists.return_value = False
        self._client.run_command = mock.Mock()
        res = self._action_manager.git_clone(test_utils.URL,
                                             test_utils.LOCATION)
        self.assertTrue(res)

    @mock.patch('time.sleep')
    @mock.patch('argus.action_manager.windows.WindowsActionManager.'
                'rmdir')
    @mock.patch('argus.action_manager.windows.WindowsActionManager.'
                'is_dir')
    @mock.patch('argus.action_manager.windows.WindowsActionManager.'
                'exists')
    def test_git_clone_exception(self, mock_exists, mock_is_dir,
                                 mock_rmdir, mock_time):
        mock_exists.side_effect = [False, True, True]
        mock_is_dir.return_value = True
        mock_rmdir.side_effect = None
        mock_time.return_value = True
        self._client.run_command.side_effect = exceptions.ArgusError
        res = self._action_manager.git_clone(test_utils.URL,
                                             test_utils.LOCATION,
                                             count=2)
        self.assertFalse(res)

    def _test_wait_cbinit_service(self, run_command_exc=None):
        if run_command_exc:
            self._client.run_command_until_condition = mock.Mock(
                side_effect=run_command_exc)
            with self.assertRaises(run_command_exc):
                self._action_manager.wait_cbinit_service()
        else:
            self._client.run_command_until_condition = mock.Mock()
            self.assertIsNone(self._action_manager.wait_cbinit_service())

    def test_wait_cbinit_service_successful(self):
        self._test_wait_cbinit_service()

    def test_wait_cbinit_service_fail(self):
        self._test_wait_cbinit_service(
            run_command_exc=exceptions.ArgusTimeoutError)

    def _test_check_cbinit_service(self, run_command_exc=None):
        if run_command_exc:
            self._client.run_command_until_condition = mock.Mock(
                side_effect=run_command_exc)
            with self.assertRaises(run_command_exc):
                self._action_manager.check_cbinit_service(
                    test_utils.SEARCHED_PATHS)
        else:
            self._client.run_command_until_condition = mock.Mock()
            self.assertIsNone(
                self._action_manager.check_cbinit_service(
                    test_utils.SEARCHED_PATHS))

    def test_check_cbinit_service_successful(self):
        self._test_check_cbinit_service()

    def test_check_cbinit_service_fail(self):
        self._test_check_cbinit_service(
            run_command_exc=exceptions.ArgusTimeoutError)

    def test_check_cbinit_service_fail_clierror(self):
        self._client.run_command_until_condition = mock.Mock(
            side_effect=[None, exceptions.ArgusCLIError, None])

        with self.assertRaises(exceptions.ArgusCLIError):
            self._action_manager.check_cbinit_service(
                test_utils.SEARCHED_PATHS)
        self.assertEqual(
            self._client.run_command_until_condition.call_count, 2)

    @test_utils.ConfPatcher('image_username', test_utils.USERNAME, 'openstack')
    @mock.patch('argus.action_manager.windows.wait_boot_completion')
    def _test_wait_boot_completion(self, mock_wait_boot_completion, exc=None):
        if exc:
            mock_wait_boot_completion.side_effect = exc
            with self.assertRaises(exc):
                self._action_manager.wait_boot_completion()
            return

        self._action_manager.wait_boot_completion()
        mock_wait_boot_completion.assert_called_once_with(
            self._client, test_utils.USERNAME)

    def test_wait_boot_completion_successful(self):
        self._test_wait_boot_completion()

    def test_wait_boot_completion_fail(self):
        self._test_wait_boot_completion(exc=exceptions.ArgusCLIError)

    def test_specific_prepare(self):
        with test_utils.LogSnatcher('argus.action_manager.windows'
                                    '.WindowsActionManager'
                                    '.specific_prepare') as snatcher:
            self.assertIsNone(self._action_manager.specific_prepare())
            self.assertEqual(snatcher.output,
                             ["Prepare something specific"
                              " for OS Type {}".format(self._os_type)])

    @mock.patch('argus.action_manager.windows.WindowsActionManager'
                '.exists')
    @mock.patch('argus.action_manager.windows.WindowsActionManager'
                '.is_file')
    def _test_remove(self, mock_is_file, mock_exists,
                     is_file=True, exists=True,
                     is_file_exc=None, exists_exc=None, run_exc=None):
        cmd = "Remove-Item -Force -Path '{path}'".format(path=test_utils.PATH)

        mock_exists.return_value = exists
        mock_is_file.return_value = is_file

        if not exists or not is_file:
            with self.assertRaises(exceptions.ArgusCLIError):
                self._action_manager.remove(test_utils.PATH)
            return

        if exists_exc:
            mock_exists.side_effect = exists_exc
            with self.assertRaises(exists_exc):
                self._action_manager.remove(test_utils.PATH)
            return

        if is_file_exc:
            mock_exists.side_effect = is_file_exc
            with self.assertRaises(is_file_exc):
                self._action_manager.remove(test_utils.PATH)
            return

        if run_exc:
            self._client.run_command_with_retry.side_effect = run_exc
            with self.assertRaises(run_exc):
                self._action_manager.remove(test_utils.PATH)
            return

        self._action_manager.remove(test_utils.PATH)
        self._client.run_command_with_retry.assert_called_once_with(
            cmd, command_type=util.POWERSHELL)

    def test_remove_successful(self):
        self._test_remove()

    def test_remove_not_exists(self):
        self._test_remove(exists=False)

    def test_remove_is_not_file(self):
        self._test_remove(is_file=False)

    def test_remove_exists_exception(self):
        self._test_remove(exists_exc=exceptions.ArgusTimeoutError)

    def test_remove_is_file_exception(self):
        self._test_remove(is_file_exc=exceptions.ArgusTimeoutError)

    def test_remove_run_command_exception(self):
        self._test_remove(run_exc=exceptions.ArgusTimeoutError)

    @mock.patch('argus.action_manager.windows.WindowsActionManager'
                '.exists')
    @mock.patch('argus.action_manager.windows.WindowsActionManager'
                '.is_dir')
    def _test_rmdir(self, mock_is_dir, mock_exists,
                    is_dir=True, exists=True,
                    is_dir_exc=None, exists_exc=None, run_exc=None):
        cmd = "Remove-Item -Force -Recurse -Path '{path}'".format(
            path=test_utils.PATH)

        mock_exists.return_value = exists
        mock_is_dir.return_value = is_dir

        if not exists or not is_dir:
            with self.assertRaises(exceptions.ArgusCLIError):
                self._action_manager.rmdir(test_utils.PATH)
            return

        if exists_exc:
            mock_exists.side_effect = exists_exc
            with self.assertRaises(exists_exc):
                self._action_manager.rmdir(test_utils.PATH)
            return

        if is_dir_exc:
            mock_exists.side_effect = is_dir_exc
            with self.assertRaises(is_dir_exc):
                self._action_manager.rmdir(test_utils.PATH)
            return

        if run_exc:
            self._client.run_command_with_retry.side_effect = run_exc
            with self.assertRaises(run_exc):
                self._action_manager.rmdir(test_utils.PATH)
            return

        self._action_manager.rmdir(test_utils.PATH)
        self._client.run_command_with_retry.assert_called_once_with(
            cmd, command_type=util.POWERSHELL)

    def test_rmdir_successful(self):
        self._test_rmdir()

    def test_rmdir_not_exists(self):
        self._test_rmdir(exists=False)

    def test_rmdir_is_not_file(self):
        self._test_rmdir(is_dir=False)

    def test_rmdir_exists_exception(self):
        self._test_rmdir(exists_exc=exceptions.ArgusTimeoutError)

    def test_rmdir_is_dir_exception(self):
        self._test_rmdir(is_dir_exc=exceptions.ArgusTimeoutError)

    def test_rmdir_run_command_exception(self):
        self._test_rmdir(run_exc=exceptions.ArgusTimeoutError)

    def _test__exists(self, fail=False, run_command_exc=None):
        cmd = 'Test-Path -PathType {} -Path "{}"'.format(
            test_utils.PATH_TYPE, test_utils.PATH)

        if run_command_exc:
            self._client.run_command_with_retry = mock.Mock(
                side_effect=run_command_exc)
            with self.assertRaises(run_command_exc):
                self._action_manager._exists(
                    test_utils.PATH, test_utils.PATH_TYPE)
            return

        if fail:
            self._client.run_command_with_retry.return_value = (
                "False", "fake-stderr", 0)
            self.assertFalse(self._action_manager._exists(
                test_utils.PATH, test_utils.PATH_TYPE))
        else:
            self._client.run_command_with_retry.return_value = (
                "True", "fake-stderr", 0)
            self.assertTrue(self._action_manager._exists(
                test_utils.PATH, test_utils.PATH_TYPE))

        self._client.run_command_with_retry.assert_called_once_with(
            cmd=cmd, command_type=util.POWERSHELL)

    def test__exists_successful(self):
        self._test__exists()

    def test__exists_fail(self):
        self._test__exists(fail=True)

    def test__exists_fail_exception(self):
        self._test__exists(run_command_exc=exceptions.ArgusTimeoutError)

    @mock.patch('argus.action_manager.windows.WindowsActionManager'
                '._exists')
    def _test_exists(self, mock_exists, fail=False, exc=None):
        if exc:
            mock_exists.side_effect = exc
            with self.assertRaises(exc):
                self._action_manager.exists(test_utils.PATH)
            return

        if fail:
            mock_exists.return_value = False
            self.assertFalse(self._action_manager.exists(test_utils.PATH))
        else:
            mock_exists.return_value = True
            self.assertTrue(self._action_manager.exists(test_utils.PATH))

        mock_exists.assert_called_once_with(
            test_utils.PATH, self._action_manager.PATH_ANY)

    def test_exists_successful(self):
        self._test_exists()

    def test_exists_fail(self):
        self._test_exists(fail=True)

    def test_exists_fail_exception(self):
        self._test_exists(exc=exceptions.ArgusTimeoutError)

    @mock.patch('argus.action_manager.windows.WindowsActionManager'
                '._exists')
    def _test_is_file(self, mock_exists, fail=False, exc=None):
        if exc:
            mock_exists.side_effect = exc
            with self.assertRaises(exc):
                self._action_manager.is_file(test_utils.PATH)
            return

        if fail:
            mock_exists.return_value = False
            self.assertFalse(self._action_manager.is_file(test_utils.PATH))
        else:
            mock_exists.return_value = True
            self.assertTrue(self._action_manager.is_file(test_utils.PATH))

        mock_exists.assert_called_once_with(
            test_utils.PATH, self._action_manager.PATH_LEAF)

    def test_is_file_successful(self):
        self._test_is_file()

    def test_is_file_fail(self):
        self._test_is_file(fail=True)

    def test_is_file_fail_exception(self):
        self._test_is_file(exc=exceptions.ArgusTimeoutError)

    @mock.patch('argus.action_manager.windows.WindowsActionManager'
                '._exists')
    def _test_is_dir(self, mock_exists, fail=False, exc=None):
        if exc:
            mock_exists.side_effect = exc
            with self.assertRaises(exc):
                self._action_manager.is_dir(test_utils.PATH)
            return

        if fail:
            mock_exists.return_value = False
            self.assertFalse(self._action_manager.is_dir(test_utils.PATH))
        else:
            mock_exists.return_value = True
            self.assertTrue(self._action_manager.is_dir(test_utils.PATH))

        mock_exists.assert_called_once_with(
            test_utils.PATH, self._action_manager.PATH_CONTAINER)

    def test_is_dir_successful(self):
        self._test_is_dir()

    def test_is_dir_fail(self):
        self._test_is_dir(fail=True)

    def test_is_dir_fail_exception(self):
        self._test_is_dir(exc=exceptions.ArgusTimeoutError)

    def _test_new_item(self, run_command_exc=None):
        cmd = "New-Item -Path '{}' -Type {} -Force".format(
            test_utils.PATH, test_utils.ITEM_TYPE)

        if run_command_exc:
            self._client.run_command_with_retry = mock.Mock(
                side_effect=run_command_exc)
            with self.assertRaises(run_command_exc):
                self._action_manager._new_item(
                    test_utils.PATH, test_utils.ITEM_TYPE)
        else:
            self._client.run_command_with_retry = mock.Mock()
            self.assertIsNone(
                self._action_manager._new_item(
                    test_utils.PATH, test_utils.ITEM_TYPE))
            self._client.run_command_with_retry.assert_called_once_with(
                cmd=cmd, command_type=util.POWERSHELL)

    def test_new_item_successful(self):
        self._test_new_item()

    def test_new_item_fail(self):
        self._test_new_item(run_command_exc=exceptions.ArgusTimeoutError)

    @mock.patch('argus.action_manager.windows.WindowsActionManager'
                '.exists')
    @mock.patch('argus.action_manager.windows.WindowsActionManager'
                '._new_item')
    def _test_mkdir(self, mock_new_item, mock_exists, exists=False,
                    exists_exc=None, new_item_exc=None):
        if exists_exc:
            mock_exists.side_effect = exists_exc
            with self.assertRaises(exists_exc):
                self._action_manager.mkdir(test_utils.PATH)
            return

        mock_exists.return_value = exists

        if exists:
            with self.assertRaises(exceptions.ArgusCLIError):
                self._action_manager.mkdir(test_utils.PATH)
            return

        if new_item_exc:
            mock_new_item.side_effect = new_item_exc
            with self.assertRaises(new_item_exc):
                self._action_manager.mkdir(test_utils.PATH)
            return

        self.assertIsNone(self._action_manager.mkdir(test_utils.PATH))

    def test_mkdir_successful(self):
        self._test_mkdir()

    def test_mkdir_exists_fail(self):
        self._test_mkdir(exists=True)

    def test_mkdir_exists_fail_exception(self):
        self._test_mkdir(exists_exc=exceptions.ArgusTimeoutError)

    def test_mkdir_new_item_fail_exception(self):
        self._test_mkdir(new_item_exc=exceptions.ArgusTimeoutError)

    @mock.patch('argus.action_manager.windows.WindowsActionManager'
                '.is_file')
    @mock.patch('argus.action_manager.windows.WindowsActionManager'
                '.is_dir')
    @mock.patch('argus.action_manager.windows.WindowsActionManager'
                '._new_item')
    def _test_mkfile(self, mock_new_item, mock_is_dir, mock_is_file,
                     is_file=False, is_dir=False, is_file_exc=None,
                     is_dir_exc=None, new_item_exc=None, run_command_exc=None):
        self._client.run_command_with_retry = mock.Mock()

        mock_is_file.return_value = is_file
        mock_is_dir.return_value = is_dir

        if is_file and not run_command_exc:
            log = ("File '{}' already exists. LastWriteTime and"
                   " LastAccessTime will be updated.".format(test_utils.PATH))

            with test_utils.LogSnatcher('argus.action_manager.windows.Windows'
                                        'ActionManager.mkfile') as snatcher:
                self.assertIsNone(self._action_manager.mkfile(test_utils.PATH))
            self.assertEqual(snatcher.output, [log])
            self._client.run_command_with_retry.assert_called_once_with(
                "echo $null >> '{}'".format(test_utils.PATH),
                command_type=util.POWERSHELL)
            return

        if is_file_exc:
            mock_is_file.side_effect = is_file_exc
            with self.assertRaises(is_file_exc):
                self._action_manager.mkfile(test_utils.PATH)
            return

        if is_file and run_command_exc:
            self._client.run_command_with_retry.side_effect = run_command_exc
            with self.assertRaises(run_command_exc):
                self._action_manager.mkfile(test_utils.PATH)
            return

        if not is_file and is_dir:
            with self.assertRaises(exceptions.ArgusCLIError):
                self._action_manager.mkfile(test_utils.PATH)
            return

        if not is_file and is_dir_exc:
            mock_is_dir.side_effect = is_dir_exc
            with self.assertRaises(is_dir_exc):
                self._action_manager.mkfile(test_utils.PATH)
            return

        if not is_file and not is_dir and new_item_exc:
            mock_new_item.side_effect = new_item_exc
            with self.assertRaises(new_item_exc):
                self._action_manager.mkfile(test_utils.PATH)
            return

        self._action_manager.mkfile(test_utils.PATH)
        mock_new_item.assert_called_once_with(
            test_utils.PATH, self._action_manager._FILE)

    def test_mkfile_new_item_successful(self):
        self._test_mkfile()

    def test_mkfile_new_item_exception(self):
        self._test_mkfile(new_item_exc=exceptions.ArgusTimeoutError)

    def test_mkfile_is_file_successful(self):
        self._test_mkfile(is_file=True)

    def test_mkfile_is_file_exception(self):
        self._test_mkfile(is_file_exc=exceptions.ArgusTimeoutError)

    def test_mkfile_run_command_exception(self):
        self._test_mkfile(
            is_file=True, run_command_exc=exceptions.ArgusTimeoutError)

    def test_mkfile_is_dir_successful(self):
        self._test_mkfile(is_dir=True)

    def test_mkfile_is_dir_exception(self):
        self._test_mkfile(is_dir_exc=exceptions.ArgusTimeoutError)

    @mock.patch('argus.action_manager.windows.WindowsActionManager'
                '.is_dir')
    @mock.patch('argus.action_manager.windows.WindowsActionManager'
                '.mkfile')
    def _test_touch(self, mock_mkfile, mock_is_dir, is_dir=False,
                    is_dir_exc=None, run_command_exc=None, mkfile_exc=None):
        mock_is_dir.return_value = is_dir

        if is_dir:
            self._client.run_command_with_retry = mock.Mock()

            if run_command_exc:
                (self._client.run_command_with_retry.
                 side_effect) = run_command_exc
                with self.assertRaises(run_command_exc):
                    self._action_manager.touch(test_utils.PATH)
                return

            cmd = ("$datetime = get-date;"
                   "$dir = Get-Item '{}';"
                   "$dir.LastWriteTime = $datetime;"
                   "$dir.LastAccessTime = $datetime;").format(test_utils.PATH)

            self.assertIsNone(self._action_manager.touch(test_utils.PATH))
            self._client.run_command_with_retry.assert_called_once_with(
                cmd, command_type=util.POWERSHELL)
            return

        if is_dir_exc:
            mock_is_dir.side_effect = is_dir_exc
            with self.assertRaises(is_dir_exc):
                self._action_manager.touch(test_utils.PATH)
            return

        if mkfile_exc:
            mock_mkfile.side_effect = mkfile_exc
            with self.assertRaises(mkfile_exc):
                self._action_manager.touch(test_utils.PATH)
            return

        self.assertIsNone(self._action_manager.touch(test_utils.PATH))

    def test_touch_successful(self):
        self._test_touch()

    def test_touch_mkfile_exception(self):
        self._test_touch(mkfile_exc=exceptions.ArgusTimeoutError)

    def test_touch_run_command_exception(self):
        self._test_touch(
            is_dir=True, run_command_exc=exceptions.ArgusTimeoutError)

    def test_touch_is_dir_successful(self):
        self._test_touch(is_dir=True)

    def test_touch_is_dir__exception(self):
        self._test_touch(is_dir_exc=exceptions.ArgusTimeoutError)

    def _test_execute(self, exc=None):
        if exc:
            self._client.run_command_with_retry = mock.Mock(side_effect=exc)
            with self.assertRaises(exc):
                self._action_manager._execute(
                    test_utils.CMD, count=util.RETRY_COUNT,
                    delay=util.RETRY_DELAY, command_type=util.CMD)
        else:
            mock_cmd_retry = mock.Mock()
            mock_cmd_retry.return_value = (test_utils.STDOUT,
                                           test_utils.STDERR,
                                           test_utils.EXIT_CODE)
            self._client.run_command_with_retry = mock_cmd_retry
            self.assertEqual(self._action_manager._execute(
                test_utils.CMD, count=util.RETRY_COUNT, delay=util.RETRY_DELAY,
                command_type=util.CMD), test_utils.STDOUT)
            self._client.run_command_with_retry.assert_called_once_with(
                test_utils.CMD, count=util.RETRY_COUNT,
                delay=util.RETRY_DELAY, command_type=util.CMD)

    def test_execute(self):
        self._test_execute()

    def test_execute_argus_timeout_error(self):
        self._test_execute(exceptions.ArgusTimeoutError)

    def test_execute_argus_error(self):
        self._test_execute(exceptions.ArgusError)

    def _test_check_cbinit_installation(self, get_python_dir_exc=None,
                                        run_remote_cmd_exc=None):
        if get_python_dir_exc:
            introspection.get_python_dir = mock.Mock(
                side_effect=get_python_dir_exc)
            self.assertFalse(self._action_manager.check_cbinit_installation())
            return

        cmd = r'& "{}\python.exe" -c "import cloudbaseinit"'.format(
            test_utils.PYTHON_DIR)
        introspection.get_python_dir = mock.Mock(
            return_value=test_utils.PYTHON_DIR)
        if run_remote_cmd_exc:
            self._client.run_remote_cmd = mock.Mock(
                side_effect=run_remote_cmd_exc)
            self.assertFalse(self._action_manager.check_cbinit_installation())
            self._client.run_remote_cmd.assert_called_once_with(
                cmd=cmd, command_type=util.POWERSHELL)
            return

        self._client.run_remote_cmd = mock.Mock()
        self.assertTrue(self._action_manager.check_cbinit_installation())

    def test_check_cbinit_installation(self):
        self._test_check_cbinit_installation()

    def test_check_cbinit_installation_get_python_dir_exc(self):
        self._test_check_cbinit_installation(
            get_python_dir_exc=exceptions.ArgusError)

    def test_check_cbinit_installation_run_remote_cmd_exc(self):
        self._test_check_cbinit_installation(
            run_remote_cmd_exc=exceptions.ArgusError)

    @mock.patch('argus.action_manager.windows.WindowsActionManager.rmdir')
    def _test_cbinit_cleanup(self, mock_rmdir, get_cbinit_dir_exc=None,
                             rmdir_exc=None):
        if get_cbinit_dir_exc:
            introspection.get_cbinit_dir = mock.Mock(
                side_effect=get_cbinit_dir_exc)
            self.assertFalse(self._action_manager.cbinit_cleanup())
            return

        introspection.get_cbinit_dir = mock.Mock(
            return_value=test_utils.CBINIT_DIR)
        if rmdir_exc:
            mock_rmdir.side_effect = rmdir_exc
            self.assertFalse(self._action_manager.cbinit_cleanup())
            return

        self.assertTrue(self._action_manager.cbinit_cleanup())

    def test_cbinit_cleanup(self):
        self._test_cbinit_cleanup()

    def test_cbinit_cleanup_get_cbinit_dir_exc(self):
        self._test_cbinit_cleanup(get_cbinit_dir_exc=exceptions.ArgusError)

    def test_cbinit_cleanup_rmdir_exc(self):
        self._test_cbinit_cleanup(rmdir_exc=exceptions.ArgusError)

    @mock.patch('argus.action_manager.windows.WindowsActionManager'
                '.cbinit_cleanup')
    @mock.patch('argus.action_manager.windows.WindowsActionManager'
                '.check_cbinit_installation')
    @mock.patch('argus.action_manager.windows.WindowsActionManager'
                '._deploy_using_scheduled_task')
    @mock.patch('argus.action_manager.windows.WindowsActionManager'
                '._run_installation_script')
    def test_install_cbinit_run_installation_script(
            self, mock_run, mock_deploy, mock_check, mock_cleanup):
        mock_check.side_effect = [True]

        self.assertTrue(self._action_manager.install_cbinit())

        self.assertEqual(mock_run.call_count, 1)
        mock_deploy.assert_not_called()
        mock_cleanup.assert_not_called()

    @mock.patch('argus.action_manager.windows.WindowsActionManager'
                '.cbinit_cleanup')
    @mock.patch('argus.action_manager.windows.WindowsActionManager'
                '.check_cbinit_installation')
    @mock.patch('argus.action_manager.windows.WindowsActionManager'
                '._deploy_using_scheduled_task')
    @mock.patch('argus.action_manager.windows.WindowsActionManager'
                '._run_installation_script')
    def test_install_cbinit_deploy_using_scheduled_task(
            self, mock_run, mock_deploy, mock_check, mock_cleanup):
        mock_check.side_effect = [False, True]

        self.assertTrue(self._action_manager.install_cbinit())

        self.assertEqual(mock_run.call_count, 1)
        self.assertEqual(mock_deploy.call_count, 1)
        self.assertEqual(mock_cleanup.call_count, 1)

    @mock.patch('argus.action_manager.windows.WindowsActionManager'
                '.cbinit_cleanup')
    @mock.patch('argus.action_manager.windows.WindowsActionManager'
                '.check_cbinit_installation')
    @mock.patch('argus.action_manager.windows.WindowsActionManager'
                '._deploy_using_scheduled_task')
    @mock.patch('argus.action_manager.windows.WindowsActionManager'
                '._run_installation_script')
    def test_install_cbinit_run_installation_script_exc(
            self, mock_run, mock_deploy, mock_check, mock_cleanup):
        mock_check.side_effect = [False, True]
        mock_deploy.side_effect = exceptions.ArgusTimeoutError

        self.assertTrue(self._action_manager.install_cbinit())

        self.assertEqual(mock_run.call_count, 2)
        self.assertEqual(mock_deploy.call_count, 1)
        self.assertEqual(mock_cleanup.call_count, 2)

    @mock.patch('argus.action_manager.windows.WindowsActionManager'
                '.cbinit_cleanup')
    @mock.patch('argus.action_manager.windows.WindowsActionManager'
                '.check_cbinit_installation')
    @mock.patch('argus.action_manager.windows.WindowsActionManager'
                '._deploy_using_scheduled_task')
    @mock.patch('argus.action_manager.windows.WindowsActionManager'
                '._run_installation_script')
    def test_install_cbinit_at_last_try(
            self, mock_run, mock_deploy, mock_check, mock_cleanup):
        mock_check.side_effect = [True]

        run_fails = [
            exceptions.ArgusTimeoutError for _ in range(util.RETRY_COUNT)]
        deploy_fails = [
            exceptions.ArgusTimeoutError for _ in range(util.RETRY_COUNT - 1)]
        deploy_fails.append(None)

        mock_run.side_effect = run_fails
        mock_deploy.side_effect = deploy_fails

        self.assertTrue(self._action_manager.install_cbinit())

        self.assertEqual(mock_run.call_count, util.RETRY_COUNT)
        self.assertEqual(mock_deploy.call_count, util.RETRY_COUNT)
        self.assertEqual(mock_cleanup.call_count, util.RETRY_COUNT * 2 - 1)

    @mock.patch('argus.action_manager.windows.WindowsActionManager'
                '.cbinit_cleanup')
    @mock.patch('argus.action_manager.windows.WindowsActionManager'
                '.check_cbinit_installation')
    @mock.patch('argus.action_manager.windows.WindowsActionManager'
                '._deploy_using_scheduled_task')
    @mock.patch('argus.action_manager.windows.WindowsActionManager'
                '._run_installation_script')
    def test_install_cbinit_timeout_fail(
            self, mock_run, mock_deploy, mock_check, mock_cleanup):
        mock_check.side_effect = [False for _ in range(2 * util.RETRY_COUNT)]

        self.assertFalse(self._action_manager.install_cbinit())

        self.assertEqual(mock_run.call_count, util.RETRY_COUNT)
        self.assertEqual(mock_deploy.call_count, util.RETRY_COUNT)
        self.assertEqual(mock_cleanup.call_count, 2 * util.RETRY_COUNT)

    @mock.patch('argus.action_manager.windows.WindowsActionManager'
                '.execute_powershell_resource_script')
    def _test_run_installation_script(self, mock_execute_script, exc=None):
        if exc:
            mock_execute_script.side_effect = exc
            with self.assertRaises(exc):
                self._action_manager._run_installation_script(
                    test_utils.INSTALLER)
        else:
            self._action_manager._run_installation_script(test_utils.INSTALLER)
            mock_execute_script.assert_called_once_with(
                resource_location='windows/installCBinit.ps1',
                parameters='-installer {}'.format(test_utils.INSTALLER))

    def test_run_installation_script(self):
        self._test_run_installation_script()

    def test_run_installation_script_argus_timeout_error(self):
        self._test_run_installation_script(exc=exceptions.ArgusTimeoutError)

    def test_run_installation_script_argus_error(self):
        self._test_run_installation_script(exc=exceptions.ArgusError)

    @mock.patch('argus.action_manager.windows.WindowsActionManager'
                '.execute_powershell_resource_script')
    def _test_deploy_using_scheduled_task(self, mock_execute_script, exc=None):
        if exc:
            mock_execute_script.side_effect = exc
            with self.assertRaises(exc):
                self._action_manager._deploy_using_scheduled_task(
                    test_utils.INSTALLER)
        else:
            self._action_manager._deploy_using_scheduled_task(
                test_utils.INSTALLER)
            mock_execute_script.assert_called_once_with(
                'windows/schedule_installer.ps1',
                '{}'.format(test_utils.INSTALLER))

    def test_deploy_using_scheduled_task(self):
        self._test_deploy_using_scheduled_task()

    def test_deploy_using_scheduled_task_argus_timeout_error(self):
        self._test_deploy_using_scheduled_task(
            exc=exceptions.ArgusTimeoutError)

    def test_deploy_using_scheduled_task_argus_error(self):
        self._test_deploy_using_scheduled_task(exc=exceptions.ArgusError)

    def test_prepare_config(self):
        with test_utils.LogSnatcher('argus.action_manager.windows'
                                    '.WindowsActionManager'
                                    '.prepare_config') as snatcher:
            self.assertIsNone(self._action_manager.prepare_config(
                mock.Mock(), mock.Mock()))
            self.assertEqual(snatcher.output,
                             ["Config Cloudbase-Init"
                              " for {}".format(self._os_type)])
