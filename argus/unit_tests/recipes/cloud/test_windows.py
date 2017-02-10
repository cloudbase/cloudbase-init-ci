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

# pylint: disable=no-value-for-parameter, protected-access, unused-argument
# pylint: disable=no-member

import ntpath
import unittest
from argus import config as argus_config
from argus import exceptions
from argus.recipes.cloud import windows
from argus.unit_tests import test_utils
from argus import util

try:
    import unittest.mock as mock
except ImportError:
    import mock

CONFIG = argus_config.CONFIG
LOG = util.get_logger()


class TestCloudbaseinitRecipe(unittest.TestCase):
    def setUp(self):
        self._recipe = windows.CloudbaseinitRecipe(mock.Mock())

    def test_wait_for_boot_completion(self):
        expected_logging = [
            "Waiting for first boot completion..."
        ]
        with test_utils.LogSnatcher('argus.recipes.cloud.'
                                    'windows') as snatcher:
            self._recipe.wait_for_boot_completion()
        (self._recipe._backend.remote_client.manager.
         wait_boot_completion.assert_called_once_with())
        self.assertEqual(expected_logging, snatcher.output)

    @mock.patch('argus.introspection.cloud.windows.parse_netsh_output')
    def _test_set_mtu(self, mock_parse_netsh, exception=False):
        times = 5
        cmd = 'netsh interface ipv4 show subinterfaces level=verbose'
        mock_subinterface = mock.Mock()
        mock_subinterface.name = "fake name"
        mock_parse_netsh.return_value = [mock_subinterface] * times
        expected_logging = [
            "Setting the MTU for %r" % mock_subinterface.name
        ] * times
        side_effect_list = [None] * times
        if exception:
            side_effect_list[2] = exceptions.ArgusTimeoutError
            side_effect_list[4] = exceptions.ArgusTimeoutError
            expected_logging.insert(3, 'Setting MTU failed with '
                                    'ArgusTimeoutError().')
            expected_logging.insert(6, 'Setting MTU failed with '
                                    'ArgusTimeoutError().')

        (self._recipe._backend.remote_client.run_command_with_retry.
         side_effect) = side_effect_list
        with test_utils.LogSnatcher('argus.recipes.cloud.'
                                    'windows') as snatcher:
            self._recipe.set_mtu()
        self.assertEqual(snatcher.output, expected_logging)
        (self._recipe._backend.remote_client.run_command_verbose.
         assert_called_once_with(cmd, command_type=util.CMD))
        self.assertEqual(self._recipe._backend.remote_client.
                         run_command_with_retry.call_count, times)

    def test_set_mtu(self):
        self._test_set_mtu()

    def test_set_mtu_fails(self):
        self._test_set_mtu(exception=True)

    def test_execution_prologue(self):
        expected_logging = [
            "Retrieve common module for proper script execution."
        ]
        with test_utils.LogSnatcher('argus.recipes.cloud.'
                                    'windows') as snatcher:
            self._recipe.execution_prologue()
        (self._recipe._backend.remote_client.manager.specific_prepare.
         assert_called_once_with())
        resource_location = "windows/common.psm1"
        (self._recipe._backend.remote_client.manager.download_resource.
         assert_called_once_with(resource_location=resource_location,
                                 location=r'C:\common.psm1'))
        self.assertEqual(expected_logging, snatcher.output)

    def test_get_installation_script(self):
        self._recipe.get_installation_script()
        (self._recipe._backend.remote_client.manager.get_installation_script.
         assert_called_once_with())

    @mock.patch('argus.recipes.cloud.windows.CloudbaseinitRecipe.'
                '_grab_cbinit_installation_log')
    @mock.patch('argus.introspection.cloud.windows.get_cbinit_dir')
    def _test_install_cbinit(self, mock_get_cbinit_dir, mock_install_log,
                             exception=False):
        expected_logging = [
            "Cloudbase-Init is already installed, skipping installation."
        ]
        self._recipe._execute = mock.sentinel
        if exception:
            expected_logging = []
            mock_get_cbinit_dir.side_effect = exceptions.ArgusError

        with test_utils.LogSnatcher('argus.recipes.cloud.'
                                    'windows') as snatcher:
            self._recipe.install_cbinit()
        mock_get_cbinit_dir.assert_called_once_with(self._recipe._execute)
        self.assertEqual(expected_logging, snatcher.output)
        if exception:
            (self._recipe._backend.remote_client.manager.install_cbinit.
             assert_called_once_with())
            mock_install_log.assert_called_once_with()

    def test_install_cbinit(self):
        self._test_install_cbinit()

    def test_install_cbinit_already_installed(self):
        self._test_install_cbinit(exception=True)

    @mock.patch('argus.recipes.cloud.windows.os')
    @mock.patch('argus.recipes.cloud.windows.zipfile.ZipFile')
    def test_extract_files_from_archive(self, mock_zipfile, mock_os):
        source_path = mock.sentinel
        destination_path = mock.sentinel
        self._recipe.extract_files_from_archive(source_path, destination_path)
        mock_zipfile.assert_called_once_with(source_path, "r")
        mock_zipfile.extractall(destination_path)
        mock_os.remove.assert_called_once_with(source_path)

    @mock.patch('argus.recipes.cloud.windows.CloudbaseinitRecipe.'
                'extract_files_from_archive')
    @mock.patch('argus.recipes.cloud.windows.CloudbaseinitRecipe.'
                '_grab_cbinit_installation_log')
    @mock.patch('argus.recipes.cloud.windows.base64.standard_b64decode')
    def _test_transfer_encoded_file_b64(self, mock_base64_decode,
                                        mock_cbinit_install_log,
                                        mock_extract_archive, archive=False):
        file_source = mock.sentinel
        destination_path = mock.sentinel
        encoded_content = [mock.sentinel]
        file_64_decoded = mock.sentinel
        (self._recipe._backend.remote_client.manager.
         encode_file_to_base64_str.return_value) = encoded_content
        mock_base64_decode.return_value = file_64_decoded

        with mock.patch('argus.recipes.cloud.windows.open') as mock_open:
            self._recipe.transfer_encoded_file_b64(
                file_source, destination_path, archive)

        (self._recipe._backend.remote_client.manager.
         encode_file_to_base64_str.assert_called_once_with(
             file_path=file_source))
        mock_base64_decode.assert_called_once_with(encoded_content[0])
        mock_open.assert_called_once_with(destination_path, 'wb')
        mock_open.write(file_64_decoded)
        if archive is True:
            mock_extract_archive.assert_called_once_with(
                destination_path, CONFIG.argus.output_directory)

    def test_transfer_encoded_file_b64(self):
        self._test_transfer_encoded_file_b64()

    def test_transfer_encoded_file_b64_archive(self):
        self._test_transfer_encoded_file_b64(archive=True)

    @mock.patch('argus.log.get_log_extra_item')
    @mock.patch('argus.recipes.cloud.windows.CloudbaseinitRecipe.'
                'transfer_encoded_file_b64')
    @mock.patch('argus.recipes.cloud.windows.os.path.join')
    def _test_grab_cbinit_installation_log(self, mock_join, mock_transfer_file,
                                           mock_get_extra_item,
                                           output_directory=True):
        expected_logging = [
            "Obtaining the installation logs."
        ]
        CONFIG.argus.output_directory = output_directory
        if output_directory is False:
            expected_logging.append("The output directory wasn't given, "
                                    "the log will not be grabbed.")
        else:
            installation_log = r"C:\installation.log"
            self._recipe._backend.instance_server.return_value = {
                'id': mock.sentinel
            }
            mock_get_extra_item.return_value = "fake-scenario-log"
            renamed_log = (r"C:\{0}-installation-{1}.log".format(
                mock_get_extra_item.return_value,
                self._recipe._backend.instance_server.return_value['id']))
            zip_source = r"C:\installation.zip"
            log_template = "installation-{}.zip".format(
                self._recipe._backend.instance_server.return_value['id'])
            mock_join.return_value = mock.sentinel

        with test_utils.LogSnatcher('argus.recipes.cloud.windows') as snatcher:
            self._recipe._grab_cbinit_installation_log()
        self.assertEqual(expected_logging, snatcher.output)
        if output_directory:
            (self._recipe._backend.remote_client.manager.copy_file.
             assert_called_once_with(installation_log, renamed_log))
            (self._recipe._backend.remote_client.manager.archive_file(
                file_path=renamed_log, destination_path=zip_source))
            mock_join.assert_called_once_with(CONFIG.argus.output_directory,
                                              log_template)
            mock_transfer_file.assert_called_once_with(
                zip_source, mock_join.return_value, archive=True)

    def test_grab_cbinit_installation_log_no_output_directory(self):
        self._test_grab_cbinit_installation_log(output_directory=False)

    def test_grab_cbinit_installation_logy(self):
        self._test_grab_cbinit_installation_log()

    @mock.patch('argus.introspection.cloud.windows.get_cbinit_dir')
    @mock.patch('argus.recipes.cloud.windows.CloudbaseinitRecipe.'
                '_execute')
    def _test_replace_install(self, mock_execute, mock_get_cbinit_dir,
                              link="fake link"):
        CONFIG.argus.patch_install = link
        expected_logging = []
        if link:
            expected_logging = [
                "Replacing Cloudbase-Init's files with %s" %
                CONFIG.argus.patch_install,
                "Download and extract installation bundle.",
                "Replace old files with the new ones."
            ]
        with test_utils.LogSnatcher('argus.recipes.cloud.windows') as snatcher:
            self._recipe.replace_install()
        self.assertEqual(expected_logging, snatcher.output)
        if link:
            execute_count = 2
            if link.startswith("\\\\"):
                execute_count = 3
            else:
                location = r'C:\install.zip'
                (self._recipe._backend.remote_client.manager.download.
                 assert_called_once_with(uri=link, location=location))
            self.assertEqual(mock_execute.call_count, execute_count)
            mock_get_cbinit_dir.assert_called_once_with(mock_execute)
            resource_location = "windows/updateCbinit.ps1"
            (self._recipe._backend.remote_client.manager.
             execute_powershell_resource_script.assert_called_once_with(
                 resource_location=resource_location))

    def test_replace_install_no_link(self):
        self._test_replace_install(link=None)

    def test_replace_install(self):
        self._test_replace_install()

    def test_replace_install_network(self):
        self._test_replace_install(link="\\\\fake link")

    @mock.patch('argus.recipes.cloud.windows.ntpath.join')
    @mock.patch('argus.recipes.cloud.windows.CloudbaseinitRecipe.'
                '_execute')
    @mock.patch('argus.introspection.cloud.windows.get_python_dir')
    def _test_replace_code(self, mock_get_python_dir, mock_execute,
                           mock_join, git_command=True, exception=False):
        CONFIG.argus.git_command = git_command
        expected_logging = []
        if git_command:
            expected_logging = [
                "Replacing Cloudbase-Init's code with %s" %
                CONFIG.argus.git_command,
                "Getting Cloudbase-Init location...",
                "Recursively removing Cloudbase-Init..."
            ]
            python_dir = mock_get_python_dir.return_value
            mock_join.return_value = "fake join"
            if exception:
                (self._recipe._backend.remote_client.manager.
                 git_clone.return_value) = None
            else:
                expected_logging.append("Applying cli patch...")
                expected_logging.append("Replacing code...")
        if exception:
            with self.assertRaises(exceptions.ArgusError) as ex:
                with test_utils.LogSnatcher('argus.recipes.cloud.'
                                            'windows') as snatcher:
                    self._recipe.replace_code()
        else:
            with test_utils.LogSnatcher('argus.recipes.cloud.'
                                        'windows') as snatcher:
                self._recipe.replace_code()
        self.assertEqual(expected_logging, snatcher.output)
        if git_command:
            mock_get_python_dir.assert_called_once_with(mock_execute)
            (self._recipe._backend.remote_client.manager.git_clone.
             assert_called_once_with(
                 repo_url=windows._CBINIT_REPO,
                 location=windows._CBINIT_TARGET_LOCATION))
            if exception:
                self.assertEqual('Code repository could not '
                                 'be cloned.', ex.exception.message)
                mock_join.assert_called_once_with(
                    python_dir, "Lib", "site-packages", "cloudbaseinit")
                self.assertEqual(mock_execute.call_count, 1)
            else:
                self.assertEqual(mock_execute.call_count, 4)
                self.assertEqual(mock_join.call_count, 2)

    def test_replace_code_no_git(self):
        self._test_replace_code(git_command=None)

    def test_replace_code_exception(self):
        self._test_replace_code(exception=True)

    def test_replace_code(self):
        self._test_replace_code()

    @mock.patch('argus.introspection.cloud.windows.get_python_dir')
    def test_pre_sysprep(self, mock_get_python_dir):
        mock_get_python_dir.return_value = "fake path"
        cbinit = ntpath.join(mock_get_python_dir.return_value, 'Lib',
                             'site-packages', 'cloudbaseinit')
        resource_location = "windows/patch_shell.ps1"
        params = r' "{}"'.format(cbinit)
        self._recipe.pre_sysprep()
        (self._recipe._backend.remote_client.manager.
         execute_powershell_resource_script.assert_called_once_with(
             resource_location=resource_location, parameters=params))

    def test_sysprep(self):
        expected_logging = [
            "Running sysprep..."
        ]
        with test_utils.LogSnatcher('argus.recipes.cloud.windows') as snatcher:
            self._recipe.sysprep()
        self.assertEqual(expected_logging, snatcher.output)
        (self._recipe._backend.remote_client.manager.
         sysprep.assert_called_once_with())

    def test_wait_cbinit_finalization(self):
        paths = [
            r"C:\cloudbaseinit_unattended",
            r"C:\cloudbaseinit_normal"]

        expected_logging = [
            "Check the heartbeat patch ...",
            "Wait for the Cloudbase-Init service to stop ..."
        ]
        with test_utils.LogSnatcher('argus.recipes.cloud.windows') as snatcher:
            self._recipe.wait_cbinit_finalization()
        self.assertEqual(expected_logging, snatcher.output)
        (self._recipe._backend.remote_client.manager.check_cbinit_service.
         assert_called_once_with(searched_paths=paths))
        (self._recipe._backend.remote_client.manager.wait_cbinit_service.
         assert_called_once_with())

    @mock.patch('argus.recipes.cloud.windows.CloudbaseinitRecipe.'
                '_make_dir_if_needed')
    @mock.patch('argus.config_generator.windows.cb_init.UnattendCBInitConfig')
    @mock.patch('argus.config_generator.windows.cb_init.CBInitConfig')
    def test_prepare_cbinit_config(self, mock_cbinitconfig, mock_unattend,
                                   mock_make_dir):
        mock_cbinit_conf = mock.Mock()
        mock_cbinit_conf.return_value = mock.Mock()
        mock_cbinitconfig.return_value = mock_cbinit_conf
        mock_unattend.return_value = mock.sentinel
        service_type = mock.sentinel
        self._recipe.prepare_cbinit_config(service_type)
        mock_cbinitconfig.assert_called_once_with(
            client=self._recipe._backend.remote_client)
        mock_unattend.assert_called_once_with(
            client=self._recipe._backend.remote_client)
        mock_cbinit_conf.set_service_type.assert_called_once_with(service_type)
        scripts_path = "C:\\Scripts"
        mock_make_dir.assert_called_once_with(scripts_path)
        self.assertEqual(mock_cbinit_conf.set_conf_value.call_count, 4)
        self._recipe._backend.remote_client.manager.prepare_config(
            mock_cbinit_conf, mock_unattend)

    def _test_make_dir_if_needed(self, is_dir=False):
        (self._recipe._backend.remote_client.manager.
         is_dir.return_value) = is_dir
        path = "fake_path"
        cmd = 'mkdir "{}"'.format(path)
        self._recipe._make_dir_if_needed(path)
        if not is_dir:
            (self._recipe._backend.remote_client.run_remote_cmd.
             assert_called_once_with(cmd, util.POWERSHELL))
        else:
            self.assertEqual(
                0,
                (self._recipe._backend.remote_client.
                 run_remote_cmd.call_count))

    def test_make_dir_if_needed(self):
        self._test_make_dir_if_needed()

    def test_make_dir_if_needed_no_create(self):
        self._test_make_dir_if_needed(is_dir=True)

    @mock.patch('argus.recipes.cloud.windows.CloudbaseinitRecipe.'
                '_make_dir_if_needed')
    @mock.patch('argus.introspection.cloud.windows.get_cbinit_dir')
    def test_inject_cbinit_config(self, mock_get_cbinit_dir, mock_make_dir):
        mock_get_cbinit_dir.return_value = "fake dir"
        self._recipe._cbinit_conf = mock.Mock()
        self._recipe._cbinit_unattend_conf = mock.Mock()
        conf_dir = ntpath.join(mock_get_cbinit_dir.return_value, "conf")
        cbinit_dir = mock_get_cbinit_dir.return_value
        needed_directories = [
            ntpath.join(cbinit_dir, "log"),
            conf_dir,
        ]
        self._recipe.inject_cbinit_config()
        self.assertEqual(mock_make_dir.call_count, len(needed_directories))
        (self._recipe._cbinit_conf.apply_config.
         assert_called_once_with(conf_dir))
        (self._recipe._cbinit_unattend_conf.apply_config.
         assert_called_once_with(conf_dir))

    @mock.patch('argus.recipes.cloud.windows.CloudbaseinitRecipe.'
                'transfer_encoded_file_b64')
    @mock.patch('argus.introspection.cloud.windows.get_cbinit_dir')
    def _test_get_cb_init_files(self, mock_get_dir, mock_encode_file,
                                output_directory="fake_output_directory"):
        CONFIG.argus.output_directory = output_directory
        fake_location = "fake_logs"
        cb_fake_files = []
        expected_logging = [
            "Obtaining Cloudbase-Init files from %s" % fake_location]
        if not output_directory:
            expected_logging.append("The output directory wasn't given, "
                                    "the files will not be grabbed.")
        else:
            self._recipe._backend.instance_server.return_value = {
                'id': "fake_id"
            }
            mock_get_dir.return_value = "fake_dir"
            cb_fake_files = [
                "cloudbase-init.log",
                "cloudbase-init-unattend.log"
            ]
        with test_utils.LogSnatcher('argus.recipes.cloud.windows') as snatcher:
            self._recipe.get_cb_init_files(fake_location, cb_fake_files)
        self.assertEqual(snatcher.output, expected_logging)
        if output_directory:
            self._recipe._backend.instance_server.assert_called_once_with()
            mock_get_dir.assert_called_once_with(self._recipe._execute)
            self.assertEqual(
                len(cb_fake_files),
                (self._recipe._backend.remote_client.
                 manager.copy_file.call_count))
            self.assertEqual(mock_encode_file.call_count, len(cb_fake_files))

    def test_get_cb_init_files_no_directory(self):
        self._test_get_cb_init_files(output_directory=False)

    def test_get_cb_init_files(self):
        self._test_get_cb_init_files()


class TestCloudbaseinitScriptRecipe(unittest.TestCase):
    def setUp(self):
        self._recipe = windows.CloudbaseinitScriptRecipe(mock.Mock())

    @mock.patch('argus.recipes.cloud.windows.CloudbaseinitRecipe.'
                'pre_sysprep')
    def test_pre_sysprep(self, mock_pre_sysprep):
        expected_logging = ["Doing last step before sysprepping."]
        resource_location = "windows/test_exe.exe"
        location = r"C:\Scripts\test_exe.exe"
        with test_utils.LogSnatcher('argus.recipes.cloud.windows') as snatcher:
            self._recipe.pre_sysprep()
        self.assertEqual(expected_logging, snatcher.output)
        self._recipe._backend.remote_client.manager.download_resource(
            resource_location=resource_location, location=location)
        mock_pre_sysprep.assert_called_once_with()


class TestCloudbaseinitCreateUserRecipe(unittest.TestCase):
    def setUp(self):
        self._recipe = windows.CloudbaseinitCreateUserRecipe(mock.Mock())

    @mock.patch('argus.recipes.cloud.windows.CloudbaseinitRecipe.'
                'pre_sysprep')
    def test_pre_sysprep(self, mock_pre_sysprep):
        CONFIG.cloudbaseinit.created_user = "fake_user"
        expected_logging = [
            "Creating the user %s..." % CONFIG.cloudbaseinit.created_user
        ]
        resource_location = "windows/create_user.ps1"
        params = r" -user {}".format(CONFIG.cloudbaseinit.created_user)
        with test_utils.LogSnatcher('argus.recipes.cloud.windows') as snatcher:
            self._recipe.pre_sysprep()
        self.assertEqual(expected_logging, snatcher.output)
        (self._recipe._backend.remote_client.manager.
         execute_powershell_resource_script.assert_called_once_with(
             resource_location=resource_location, parameters=params))
        mock_pre_sysprep.assert_called_once_with()


class TestBaseNextLogonRecipe(unittest.TestCase):
    def setUp(self):
        self._recipe = windows.BaseNextLogonRecipe(mock.Mock())

    @mock.patch('argus.recipes.cloud.windows.CloudbaseinitRecipe.'
                'prepare_cbinit_config')
    def test_prepare_cbinit_config(self, mock_prepare_cbinit_config):
        service_type = mock.sentinel
        self._recipe._cbinit_conf = mock.Mock()
        self._recipe.prepare_cbinit_config(service_type)
        mock_prepare_cbinit_config.assert_called_once_with(service_type)
        self._recipe._cbinit_conf.set_conf_value.assert_called_once_with(
            name="first_logon_behaviour", value=self._recipe.behaviour)


class TestCloudbaseinitMockServiceRecipe(unittest.TestCase):
    def setUp(self):
        self._recipe = windows.CloudbaseinitMockServiceRecipe(mock.Mock())

    @mock.patch('argus.recipes.cloud.windows.CloudbaseinitRecipe.'
                'prepare_cbinit_config')
    def test_prepare_cbinit_config(self, mock_prepare_cbinit_config):
        expected_logging = ["Inject guest IP for mocked service access."]
        service_type = mock.sentinel
        self._recipe._cbinit_conf = mock.Mock()
        with test_utils.LogSnatcher('argus.recipes.cloud.windows') as snatcher:
            self._recipe.prepare_cbinit_config(service_type)
        self.assertEqual(expected_logging, snatcher.output)
        mock_prepare_cbinit_config.assert_called_once_with(service_type)
        self._recipe._cbinit_conf.set_conf_value.assert_called_once_with(
            name=self._recipe.config_entry,
            value=self._recipe.metadata_address,
            section=self._recipe.config_group)


class TestCloudbaseinitCloudstackRecipe(unittest.TestCase):
    def setUp(self):
        self._recipe = windows.CloudbaseinitCloudstackRecipe(mock.Mock())

    @mock.patch('argus.recipes.cloud.windows.CloudbaseinitMockServiceRecipe.'
                'prepare_cbinit_config')
    def test_prepare_cbinit_config(self, mock_prepare_cbinit_config):
        service_type = mock.sentinel
        self._recipe._cbinit_conf = mock.Mock()
        self._recipe.prepare_cbinit_config(service_type)
        mock_prepare_cbinit_config.assert_called_once_with(service_type)
        self._recipe._cbinit_conf.set_conf_value.assert_called_once_with(
            name='password_server_port',
            value=CONFIG.cloudstack_mock.password_server_port,
            section=self._recipe.config_group)


class TestCloudbaseinitMaasRecipe(unittest.TestCase):
    def setUp(self):
        self._recipe = windows.CloudbaseinitMaasRecipe(mock.Mock())

    @mock.patch('argus.recipes.cloud.windows.CloudbaseinitMockServiceRecipe.'
                'prepare_cbinit_config')
    def test_prepare_cbinit_config(self, mock_prepare_cbinit_config):
        service_type = mock.sentinel
        self._recipe._cbinit_conf = mock.Mock()
        self._recipe.prepare_cbinit_config(service_type)
        mock_prepare_cbinit_config.assert_called_once_with(service_type)
        required_fields = (
            "maas_oauth_consumer_key",
            "maas_oauth_consumer_secret",
            "maas_oauth_token_key",
            "maas_oauth_token_secret",
        )
        self.assertEqual(
            self._recipe._cbinit_conf.set_conf_value.call_count,
            len(required_fields))


class TestCloudbaseinitWinrmRecipe(unittest.TestCase):
    def setUp(self):
        self._recipe = windows.CloudbaseinitWinrmRecipe(mock.Mock())

    @mock.patch('argus.recipes.cloud.windows.CloudbaseinitCreateUserRecipe.'
                'prepare_cbinit_config')
    def test_prepare_cbinit_config(self, mock_prepare_cbinit_config):
        service_type = mock.sentinel
        self._recipe._cbinit_conf = mock.Mock()
        self._recipe.prepare_cbinit_config(service_type)
        mock_prepare_cbinit_config.assert_called_once_with(service_type)
        self._recipe._cbinit_conf.set_conf_value.assert_called_once_with(
            name="plugins",
            value="cloudbaseinit.plugins.windows.createuser."
                  "CreateUserPlugin,"
                  "cloudbaseinit.plugins.windows.setuserpassword."
                  "SetUserPasswordPlugin,"
                  "cloudbaseinit.plugins.windows.winrmlistener."
                  "ConfigWinRMListenerPlugin,"
                  "cloudbaseinit.plugins.windows.winrmcertificateauth."
                  "ConfigWinRMCertificateAuthPlugin"
        )


class TestCloudbaseinitKeysRecipe(unittest.TestCase):
    def setUp(self):
        self._recipe = windows.CloudbaseinitKeysRecipe(mock.Mock())

    @mock.patch('argus.recipes.cloud.windows.CloudbaseinitCreateUserRecipe.'
                'prepare_cbinit_config')
    @mock.patch('argus.recipes.cloud.windows.CloudbaseinitHTTPRecipe.'
                'prepare_cbinit_config')
    def test_prepare_cbinit_config(self, mock_prepare_cbinit_config, _):
        service_type = mock.sentinel
        self._recipe._cbinit_conf = mock.Mock()
        self._recipe.prepare_cbinit_config(service_type)
        mock_prepare_cbinit_config.assert_called_once_with(service_type)
        self._recipe._cbinit_conf.set_conf_value.assert_called_once_with(
            name="plugins",
            value="cloudbaseinit.plugins.windows.createuser."
                  "CreateUserPlugin,"
                  "cloudbaseinit.plugins.windows.setuserpassword."
                  "SetUserPasswordPlugin,"
                  "cloudbaseinit.plugins.common.sshpublickeys."
                  "SetUserSSHPublicKeysPlugin,"
                  "cloudbaseinit.plugins.windows.winrmlistener."
                  "ConfigWinRMListenerPlugin,"
                  "cloudbaseinit.plugins.windows.winrmcertificateauth."
                  "ConfigWinRMCertificateAuthPlugin")


class TestCloudbaseinitLongHostname(unittest.TestCase):
    def setUp(self):
        self._recipe = windows.CloudbaseinitLongHostname(mock.Mock())

    @mock.patch('argus.recipes.cloud.windows.CloudbaseinitRecipe.'
                'prepare_cbinit_config')
    def test_prepare_cbinit_config(self, mock_prepare_cbinit_config):
        service_type = mock.sentinel
        expected_logging = ["Injecting netbios option in conf file."]
        self._recipe._cbinit_conf = mock.Mock()
        with test_utils.LogSnatcher('argus.recipes.cloud.windows') as snatcher:
            self._recipe.prepare_cbinit_config(service_type)
        self.assertEqual(expected_logging, snatcher.output)
        mock_prepare_cbinit_config.assert_called_once_with(service_type)
        self._recipe._cbinit_conf.set_conf_value.assert_called_once_with(
            name='netbios_host_name_compatibility', value='False')


class TestCloudbaseinitLocalScriptsRecipe(unittest.TestCase):
    def setUp(self):
        self._recipe = windows.CloudbaseinitLocalScriptsRecipe(mock.Mock())

    @mock.patch('argus.recipes.cloud.windows.CloudbaseinitRecipe.'
                'pre_sysprep')
    def test_pre_sysprep(self, mock_pre_sysprep):
        expected_logging = ["Downloading reboot-required local script."]
        self._recipe._cbinit_conf = mock.Mock()
        with test_utils.LogSnatcher('argus.recipes.cloud.windows') as snatcher:
            self._recipe.pre_sysprep()
        self.assertEqual(expected_logging, snatcher.output)
        mock_pre_sysprep.assert_called_once_with()
        resource_location = "windows/reboot.cmd"
        (self._recipe._backend.remote_client.manager.download_resource.
         assert_called_once_with(resource_location=resource_location,
                                 location=r'C:\Scripts\reboot.cmd'))


class TestCloudbaseinitImageRecipe(unittest.TestCase):
    def setUp(self):
        self._recipe = windows.CloudbaseinitImageRecipe(mock.Mock())

    @mock.patch('argus.introspection.cloud.windows.get_cbinit_dir')
    def test_wait_cbinit_finalization(self, mock_get_cbinit_dir):
        expected_logging = [
            "Check the heartbeat patch ...",
            "Wait for the Cloudbase-Init service to stop ..."
        ]
        self._recipe._execute = mock.sentinel
        mock_get_cbinit_dir.return_value = "fake path"
        paths = [ntpath.join(mock_get_cbinit_dir.return_value, "log", name)
                 for name in ["cloudbase-init-unattend.log",
                              "cloudbase-init.log"]]
        with test_utils.LogSnatcher('argus.recipes.cloud.windows') as snatcher:
            self._recipe.wait_cbinit_finalization()
        self.assertEqual(expected_logging, snatcher.output)
        mock_get_cbinit_dir.assert_called_once_with(self._recipe._execute)
        (self._recipe._backend.remote_client.manager.check_cbinit_service.
         assert_called_once_with(searched_paths=paths))
        (self._recipe._backend.remote_client.manager.wait_cbinit_service.
         assert_called_once_with())

    @mock.patch('argus.recipes.cloud.windows.six.moves')
    @mock.patch('argus.recipes.cloud.windows.CloudbaseinitImageRecipe.'
                'wait_cbinit_finalization')
    @mock.patch('argus.recipes.cloud.windows.CloudbaseinitImageRecipe.'
                'execution_prologue')
    def _test_prepare(self, mock_execution_prologue,
                      mock_wait_finalization, mock_moves, pause=False):
        CONFIG.argus.pause = pause
        expected_logging = [
            "Preparing already sysprepped instance...",
            "Finished preparing instance."
        ]
        with test_utils.LogSnatcher('argus.recipes.cloud.windows') as snatcher:
            self._recipe.prepare()
        self.assertEqual(expected_logging, snatcher.output)
        mock_execution_prologue.assert_called_once_with()
        mock_wait_finalization.assert_called_once_with()
        if pause:
            mock_moves.input.assert_called_once_with(
                "Press Enter to continue...")

    def test_prepare(self):
        self._test_prepare()

    def test_prepare_with_pause(self):
        self._test_prepare(pause=True)
