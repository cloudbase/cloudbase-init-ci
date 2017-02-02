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
# pylint: disable=no-self-use, unused-argument, redefined-variable-type

import unittest
from argus.introspection.cloud import windows
from argus import util

try:
    import unittest.mock as mock
except ImportError:
    import mock


class TestWindows(unittest.TestCase):

    @mock.patch('shutil.rmtree')
    @mock.patch('tempfile.mkdtemp')
    def test_create_tempdir(self, mock_mkdtemp, mock_rmtree):
        mock_mkdtemp.return_value = mock.sentinel, mock.sentinel
        with windows._create_tempdir() as result:
            self.assertEqual(result, mock_mkdtemp.return_value)
        mock_mkdtemp.assert_called_once_with(prefix="cloudbaseinit-ci-tests")
        mock_rmtree.assert_called_once_with(mock_mkdtemp.return_value)

    @mock.patch('os.close')
    @mock.patch('tempfile.mkstemp')
    @mock.patch('argus.introspection.cloud.windows._create_tempdir')
    def _test_create_tempfile(self, mock_tempdir, mock_mkstemp, mock_close,
                              content=None):
        mock_mkstemp.return_value = "fake_file", "fake_path"
        if content is None:
            with windows._create_tempfile() as result:
                self.assertEqual(result, "fake_path")
        else:
            with mock.patch('argus.introspection.cloud.'
                            'windows.open') as mock_open:
                with windows._create_tempfile(content) as result:
                    self.assertEqual(result, "fake_path")
            mock_open.assert_called_once_with("fake_path", 'w')
        mock_mkstemp.assert_called_once_with(
            dir=mock_tempdir.return_value.__enter__())
        mock_close.assert_called_once_with("fake_file")

    def test_create_tempfile_no_content(self):
        self._test_create_tempfile()

    def test_create_tempfil(self):
        self._test_create_tempfile(content="fake content")

    def _test_get_ntp_peers(self, ouput_len, peer, lines_no):
        mock_line = mock.Mock()
        mock_line.startswith.return_value = (not ouput_len == 0)
        mock_line.partition.return_value = (peer.decode('utf-8'),) * ouput_len
        mock_output = mock.Mock()
        mock_output.splitlines.return_value = [mock_line] * lines_no
        expected_result = [peer.decode('utf-8').split(",")[0]] * ouput_len

        result = windows._get_ntp_peers(mock_output)

        self.assertEqual(result, expected_result)
        mock_output.splitlines.assert_called_once_with()
        self.assertEqual(mock_line.startswith.call_count, lines_no)
        self.assertEqual(mock_line.partition.call_count, ouput_len)

    def test_get_ntp_no_peers(self):
        self._test_get_ntp_peers(0, "Not Peer:", 3)

    def test_get_ntp_peers(self):
        self._test_get_ntp_peers(3, "Peer: fake_peer", 3)

    def test_escape_path(self):
        path = "(12 34))"
        expected_result = path
        for char in windows.ESC:
            expected_result = expected_result.replace(char, "`{}".format(char))

        result = windows.escape_path(path)

        self.assertEqual(result, expected_result)

    def _test_get_ips(self, ips_as_string, expected_result):
        result = windows._get_ips(ips_as_string)
        self.assertEqual(result, expected_result)

    def test_get_ips(self):
        expected_result = ["1.2.3.4", "1.2.3.5"], ["1:2:3:4", "1:2.3.4"]
        self._test_get_ips(
            "header 1.2.3.4 1:2:3:4 1.2.3.5 1:2.3.4", expected_result)

    def test_get_ips_none(self):
        self._test_get_ips("no_ips    ", ([], []))

    @mock.patch('argus.introspection.cloud.windows._get_ips')
    def test_get_nic_details(self, mock_get_ips):
        details = ["mac fake_mac", "address", "address",
                   "gateway", "netmask", "netmask", "dns", "dhcp true"]
        mock_get_ips.side_effect = [
            (["ipv4", None], []),              # address
            (["ipv4", None], [None, "ipv6"]),  # address
            (None, ["ipv6"]),                  # gateway
            (["ipv4", None], [None]),          # netmask
            (["ipv4", None], [None, 'ipv6']),          # netmask
            ("ipv4", "ipv6")                   # dns
        ]
        result = windows._get_nic_details(details)
        expected_result = windows.NICDetails(
            mac='fake_mac',
            address=windows.Address(v4='ipv4', v6='ipv6'),
            gateway=windows.Address(v4=None, v6='ipv6'),
            netmask=windows.Address(v4='ipv4', v6='ipv6'),
            dns=windows.Address(v4='ipv4', v6='ipv6'),
            dhcp=True
        )
        self.assertEqual(result, expected_result)

    @mock.patch('argus.introspection.cloud.windows.ntpath')
    @mock.patch('argus.introspection.cloud.windows.escape_path')
    def _test_get_cbinit_dir(self, mock_escape_path, mock_ntpath,
                             arch="None", no_error=True):
        mock_excute_function = mock.Mock()
        mock_location = mock.Mock()
        mock_location.strip.return_value = "fake_location"
        mock_escape_path.return_value = "fake location"
        side_effect_list = [arch] + [mock_location]
        if arch == "AMD64":
            side_effect_list.append(mock_location)
            side_effect_list.append("fake_status")
        if no_error:
            side_effect_list.append("true")
        else:
            side_effect_list.append("fake_status")
        mock_excute_function.side_effect = side_effect_list

        if no_error:
            mock_ntpath.join.return_value = "fake path"
            result = windows.get_cbinit_dir(mock_excute_function)
            self.assertEqual(result, "fake path")
            mock_ntpath.join.assert_called_once_with(
                "fake_location", "Cloudbase Solutions", "Cloudbase-Init")
        else:
            from argus import exceptions
            with self.assertRaises(exceptions.ArgusError) as ex:
                result = windows.get_cbinit_dir(mock_excute_function)
            self.assertEqual(ex.exception.message, 'Cloudbase-Init '
                             'installation directory not found')

    def ztest_get_cbinit_dir_amd64(self):
        self._test_get_cbinit_dir(arch='AMD64')

    def ztest_get_cbinit_dir(self):
        self._test_get_cbinit_dir()

    def ztest_get_cbinit_dir_error(self):
        self._test_get_cbinit_dir(no_error=False)

    @mock.patch('ntpath.join')
    @mock.patch('argus.introspection.cloud.windows.get_cbinit_dir')
    def test_set_config_option(self, mock_cbinit_dir, mock_join):
        mock_cbinit_dir.return_value = "fake dir"
        mock_join.return_value = mock.sentinel

        option = mock.sentinel
        value = mock.sentinel
        execute_function = mock.Mock()

        windows.set_config_option(option, value, execute_function)

        mock_cbinit_dir.assert_called_once_with(execute_function)
        mock_join.assert_called_once_with("fake dir", "conf",
                                          "cloudbase-init.conf")
        cmd = ('((Get-Content {0!r}) + {1!r}) | Set-Content {0!r}'.
               format(mock_join.return_value,
                      "{} = {}".format(option, value)))
        execute_function.assert_called_with(cmd, command_type=util.POWERSHELL)

    @mock.patch('ntpath.join')
    @mock.patch('argus.introspection.cloud.windows.get_cbinit_dir')
    def _test_get_python_dir(self, mock_cbinit_dir, mock_join, python_dir):
        mock_cbinit_dir.return_value = "fake dir"
        mock_join.return_value = mock.sentinel

        mock_stdout = mock.Mock()
        if python_dir:
            mock_stdout.splitlines.return_value = [
                "fake_line", "pYthOn27", "python"]
        else:
            mock_stdout.splitlines.return_value = [
                "fake_line", "fake_line 2", "fake line 3"]

        mock_strip = mock.Mock()
        mock_strip.strip.return_value = mock_stdout

        execute_function = mock.Mock()
        execute_function.return_value = mock_strip

        result = windows.get_python_dir(execute_function)

        mock_cbinit_dir.assert_called_once_with(execute_function)
        mock_strip.strip.assert_called_once_with()
        command = 'dir "{}" /b'.format(mock_cbinit_dir.return_value)
        execute_function.assert_called_with(command, command_type=util.CMD)
        if python_dir:
            mock_join.assert_called_once_with(mock_cbinit_dir.return_value,
                                              "pYthOn27")
            self.assertEqual(result, mock_join.return_value)
        else:
            self.assertEqual(mock_join.call_count, 0)
            self.assertEqual(result, None)

    def ztest_get_python_dir(self):
        self._test_get_python_dir(python_dir=True)

    def ztest_get_python_dir_none(self):
        self._test_get_python_dir(python_dir=None)

    def _test_get_cbinit_key(self, x64):
        mock_result = mock.Mock()
        if x64:
            mock_result.strip.return_value = "TruE"
        else:
            mock_result.strip.return_value = "None"

        mock_excute_function = mock.Mock()
        mock_excute_function.return_value = mock_result

        result = windows.get_cbinit_key(mock_excute_function)

        if x64:
            key = ("HKLM:SOFTWARE\\Cloudbase` Solutions\\"
                   "Cloudbase-init")
        else:
            key = ("HKLM:SOFTWARE\\Wow6432Node\\Cloudbase` Solutions\\"
                   "Cloudbase-init")
        self.assertEqual(result, key)

    def test_get_cbinit_key(self):
        self._test_get_cbinit_key(x64=False)

    def test_get_cbinit_key_x64(self):
        self._test_get_cbinit_key(x64=True)

    @mock.patch('argus.introspection.cloud.windows.util')
    def ztest_get_os_version(self, mock_util):
        mock_util.get_int_from_str.return_value = mock.sentinel
        mock_util.POWERSHELL = mock.sentinel
        mock_stdout = mock.Mock()
        mock_stdout.strip.return_value = mock.sentinel
        mock_client = mock.Mock()
        mock_client.run_command_with_retry.return_value = (mock_stdout,
                                                           None, None)

        result = windows.get_os_version(mock_client, "fake field")

        self.assertEqual(result, mock_util.get_int_from_str.return_value)
        cmd = "[System.Environment]::OSVersion.Version.{}".format("fake field")
        mock_client.run_command_with_retry.assert_called_once_with(
            cmd, command_type=mock_util.POWERSHELL)
        mock_util.get_int_from_str.assert_called_once_with(mock.sentinel)

    @mock.patch('re.search')
    @mock.patch('re.split')
    def _test_parse_netsh_output(self, mock_re_split, mock_re_search,
                                 interfaces_number):
        mock_subinterface = mock.Mock()
        mock_subinterface.partition.return_value = 'iface', None, None
        mock_subinterface.lower.side_effect = (
            ['loopback'] + ['fake data'] * (interfaces_number - 1))

        mock_interface = mock.Mock()
        mock_interface.strip.return_value = mock_subinterface

        fake_block = (
            ['ignored'] + [mock_interface, 'fake content'] * interfaces_number)
        mock_re_split.return_value = fake_block
        mock_mtu = mock.Mock()
        mock_mtu.group.return_value = "fake mtu"
        mock_re_search.return_value = mock_mtu

        result = windows.parse_netsh_output(mock.Mock())

        expected_result = [
            windows.Interface(name="iface", mtu="fake mtu")
        ] * (interfaces_number - 1)
        self.assertEqual(result, expected_result)
        self.assertEqual(mock_interface.strip.call_count, interfaces_number)
        self.assertEqual(mock_subinterface.partition.call_count,
                         interfaces_number)
        self.assertEqual(mock_subinterface.lower.call_count, interfaces_number)

    def test_parse_netsh_output(self):
        self._test_parse_netsh_output(interfaces_number=3)

    def test_parse_netsh_output_loopback_only(self):
        self._test_parse_netsh_output(interfaces_number=1)


class TestInstanceIntrospection(unittest.TestCase):
    @mock.patch('argus.introspection.cloud.base.CloudInstanceIntrospection')
    def setUp(self, mock_cloud_instance_introspection):
        mock_remote_client = mock.Mock()
        mock_remote_client.manager.WINDOWS_MANAGEMENT_CMDLET = "fake_cmdlet"
        self._introspect = windows.InstanceIntrospection(mock_remote_client)

    @mock.patch('argus.util.POWERSHELL')
    def test_get_disk_size(self, mock_util_ps):
        self._introspect.remote_client.run_command_verbose.return_value = 0
        result = self._introspect.get_disk_size()
        self.assertEqual(result, 0)

    def _test_username_exists(self, exists):
        (self._introspect.remote_client.run_command_verbose.
         return_value) = exists
        result = self._introspect.username_exists("fake username")
        self.assertEqual(result, exists)
        cmdlet = (self._introspect.remote_client.
                  manager.WINDOWS_MANAGEMENT_CMDLET)
        cmd = ('{0} Win32_Account | where {{$_.Name -contains "{1}"}}'
               .format(cmdlet, "fake username"))
        (self._introspect.remote_client.run_command_verbose.
         assert_called_once_with(cmd, command_type=util.POWERSHELL))

    def test_username_exists(self):
        self._test_username_exists(True)

    def test_username_not_exists(self):
        self._test_username_exists(False)

    @mock.patch('argus.introspection.cloud.windows._get_ntp_peers')
    def test_get_instance_ntp(self, mock_get_ntp_peers):
        mock_get_ntp_peers.return_value = mock.sentinel
        stdout = mock.sentinel
        (self._introspect.remote_client.run_command_verbose.
         return_value) = stdout
        result = self._introspect.get_instance_ntp_peers()
        self.assertEqual(result, mock_get_ntp_peers.return_value)
        mock_get_ntp_peers.assert_called_once_with(stdout)

    @mock.patch('argus.introspection.cloud.windows.CONFIG')
    @mock.patch('ntpath.join')
    def test_get_instance_keys_path(self, mock_join, mock_config):
        mock_stdout = mock.Mock()
        mock_stdout.rpartition.return_value = "fake dir", None, None
        (self._introspect.remote_client.run_command_verbose.
         return_value) = mock_stdout
        mock_join.return_value = mock.sentinel

        result = self._introspect.get_instance_keys_path()

        mock_join.assert_called_once_with(
            "fake dir", mock_config.cloudbaseinit.created_user,
            ".ssh", "authorized_keys")
        self.assertEqual(result, mock_join.return_value)

    def test_get_instance_file_content(self):
        expected_result = mock.sentinel
        filepath = "fake path"
        cmd = '[io.file]::ReadAllText("%s")' % filepath
        (self._introspect.remote_client.run_command_verbose.
         return_value) = expected_result

        result = self._introspect.get_instance_file_content(filepath)

        self.assertEqual(result, expected_result)
        (self._introspect.remote_client.run_command_verbose.
         assert_called_once_with(cmd, command_type=util.POWERSHELL))

    def test_get_userdata_executed_plugins(self):
        expected_result = 1
        cmd = r'(Get-ChildItem -Path  C:\ *.txt).Count'
        (self._introspect.remote_client.run_command_verbose.
         return_value) = expected_result

        result = self._introspect.get_userdata_executed_plugins()

        self.assertEqual(result, expected_result)
        (self._introspect.remote_client.run_command_verbose.
         assert_called_once_with(cmd, command_type=util.POWERSHELL))

    @mock.patch('argus.introspection.cloud.windows.parse_netsh_output')
    def test_get_instance_mtu(self, mock_parse_netsh):
        mock_parse_netsh.return_value = [mock.sentinel]
        expected_result = mock.sentinel
        cmd = 'netsh interface ipv4 show subinterfaces level=verbose'
        (self._introspect.remote_client.run_command_verbose.
         return_value) = expected_result

        result = self._introspect.get_instance_mtu()

        self.assertEqual(result, mock_parse_netsh.return_value[0])
        (self._introspect.remote_client.run_command_verbose.
         assert_called_once_with(cmd, command_type=util.CMD))

    @mock.patch('argus.introspection.cloud.windows._create_tempfile')
    @mock.patch('argus.introspection.cloud.windows.util')
    def test_get_cloudbaseinit_traceback(self, mock_util, mock_create_temp):
        mock_util.get_resource.return_value = "fake resource"
        mock_util.rand_name.return_value = "fake_name"
        mock_stdout = mock.Mock()
        mock_stdout.strip.return_value = "fake strip"
        (self._introspect.remote_client.run_command_verbose.
         return_value) = mock_stdout
        result = self._introspect.get_cloudbaseinit_traceback()
        self.assertEqual(result, "fake strip")
        mock_util.get_resource.assert_called_once_with(
            'windows/get_traceback.ps1')
        mock_util.rand_name.assert_called_once_with()
        mock_create_temp.assert_called_once_with(content="fake resource")
        self._introspect.remote_client.copy_file.assert_called_once_with(
            mock_create_temp.return_value.__enter__(),
            "C:\\{}.ps1".format("fake_name"))
        (self._introspect.remote_client.run_command_verbose.
         assert_called_once_with(
             "C:\\{}.ps1".format("fake_name"),
             command_type=mock_util.POWERSHELL_SCRIPT_REMOTESIGNED))

    def test_file_exists(self):
        mock_stdout = mock.Mock()
        mock_stdout.strip.return_value = 'True'
        filepath = "fake path"
        cmd = 'Test-Path {}'.format(filepath)
        (self._introspect.remote_client.run_command_verbose.
         return_value) = mock_stdout
        result = self._introspect._file_exist(filepath)

        (self._introspect.remote_client.run_command_verbose.
         assert_called_once_with(cmd, command_type=util.POWERSHELL))
        self.assertEqual(result, True)

    @mock.patch('argus.introspection.cloud.windows.'
                'InstanceIntrospection._file_exist')
    def test_instance_exe_script_executed(self, mock_file_exists):
        mock_file_exists.return_value = mock.sentinel

        result = self._introspect.instance_exe_script_executed()

        self.assertEqual(result, mock_file_exists.return_value)
        mock_file_exists.assert_called_once_with("C:\\Scripts\\exe.output")

    @mock.patch('argus.introspection.cloud.windows.re')
    def _test_get_group_members(self, mock_re, no_error=True):
        group = "fake group"
        if no_error:
            mock_split = mock.Mock()
            mock_split.split.return_value = ["fake", None, "result"]
            mock_member_search = mock.Mock()
            mock_member_search.group.return_value = mock_split
            mock_re.search.return_value = mock_member_search
            result = self._introspect.get_group_members(group)
            self.assertEqual(result, ["fake", "result"])
        else:
            mock_re.search.return_value = no_error
            with self.assertRaises(ValueError) as ex:
                result = self._introspect.get_group_members(group)
            self.assertEqual(ex.exception.message, 'Unable to get members.')

        cmd = "net localgroup {}".format(group)
        (self._introspect.remote_client.run_command_verbose.
         assert_called_once_with(cmd, command_type=util.CMD))

    def test_get_group_members(self):
        self._test_get_group_members()

    def test_get_group_members_error(self):
        self._test_get_group_members(no_error=False)

    def test_list_location(self):
        location = "fake location"
        command = "dir {} /b".format(location)
        mock_stdout = mock.Mock()
        expected_result = [mock.sentinel, mock.sentinel]
        mock_stdout.splitlines.return_value = [
            mock.sentinel, None, mock.sentinel]
        (self._introspect.remote_client.run_command_verbose.
         return_value) = mock_stdout

        result = self._introspect.list_location(location)
        self.assertEqual(result, expected_result)
        (self._introspect.remote_client.run_command_verbose.
         assert_called_once_with(command, command_type=util.CMD))

    @mock.patch('argus.introspection.cloud.windows.re')
    def _test_get_service_triggers(self, mock_re, no_error=True):
        service = "fake service"
        mock_re.search.return_value = no_error
        if no_error:
            mock_strip = mock.Mock()
            mock_strip.strip.return_value = "fake result"
            mock_match = mock.Mock()
            mock_match.group.return_value = mock_strip
            mock_re.search.return_value = mock_match
            result = self._introspect.get_service_triggers(service)
            self.assertEqual(result, ("fake result", "fake result"))
        else:
            with self.assertRaises(ValueError) as ex:
                result = self._introspect.get_service_triggers(service)
            self.assertEqual(ex.exception.message,
                             "Unable to get the triggers for the "
                             "given service.")
        command = "sc qtriggerinfo {}".format(service)
        (self._introspect.remote_client.run_command_verbose.
         assert_called_once_with(command, command_type=util.CMD))

    def test_get_service_triggers(self):
        self._test_get_service_triggers()

    def test_get_service_triggers_error(self):
        self._test_get_service_triggers(no_error=False)

    @mock.patch('argus.introspection.cloud.windows.get_os_version')
    def test_get_instance_os_version(self, mock_get_os_version):
        expected_result = ['major version', 'minor version']
        mock_get_os_version.side_effect = expected_result
        result = self._introspect.get_instance_os_version()
        self.assertEqual(result, tuple(expected_result))

    @mock.patch('argus.introspection.cloud.windows.'
                'InstanceIntrospection.get_instance_file_content')
    def test_get_cloudconfig_executed_plugins(self, mock_get_file_content):
        mock_get_file_content.return_value = "fake content"
        result = self._introspect.get_cloudconfig_executed_plugins()
        files = {
            'b64': 'fake content',
            'b64_1': 'fake content',
            'gzip': 'fake content',
            'gzip_1': 'fake content',
            'gzip_base64': 'fake content',
            'gzip_base64_1': 'fake content',
            'gzip_base64_2': 'fake content'
        }
        self.assertEqual(result, files)
        self.assertEqual(mock_get_file_content.call_count, 7)

    def test_get_timezone(self):
        (self._introspect.remote_client.run_command_verbose.
         return_value) = "fake timezone"
        command = "tzutil /g"
        result = self._introspect.get_timezone()
        self.assertEqual(result, "fake timezone")
        (self._introspect.remote_client.run_command_verbose.
         assert_called_once_with(command, command_type=util.POWERSHELL))

    def test_get_instance_hostname(self):
        (self._introspect.remote_client.run_command_verbose.
         return_value) = "fake hostname"
        command = "hostname"
        result = self._introspect.get_instance_hostname()
        self.assertEqual(result, "fake hostname")
        (self._introspect.remote_client.run_command_verbose.
         assert_called_once_with(command, command_type=util.CMD))

    def test_get_user_flags(self):
        (self._introspect.remote_client.manager.get_agent_command.
         return_value) = "fake cmd"
        (self._introspect.remote_client.run_command_verbose.
         return_value) = "fake result"

        result = self._introspect.get_user_flags("fake user")
        self.assertEqual(result, "fake result")
        (self._introspect.remote_client.manager.get_agent_command.
         assert_called_once_with(agent_action="get_user_flags",
                                 source="fake user"))
        (self._introspect.remote_client.run_command_verbose.
         assert_called_once_with("fake cmd"))

    def test_get_swap_status(self):
        (self._introspect.remote_client.run_command_verbose.
         return_value) = r'?:\pagefile.sys'
        swap_query = (r"HKLM:\SYSTEM\CurrentControlSet\Control\Session"
                      r" Manager\Memory Management")
        cmd = r"(Get-ItemProperty '{}').PagingFiles".format(swap_query)
        result = self._introspect.get_swap_status()
        self.assertEqual(result, True)
        (self._introspect.remote_client.run_command_verbose.
         assert_called_once_with(cmd))

    @mock.patch('argus.introspection.cloud.windows._get_nic_details')
    def test_get_network_interfaces(self, mock_get_nic_details):
        (self._introspect.remote_client.run_command_verbose.
         return_value) = "fake result\n\n\n\n\nfake result\n" + \
                         windows.SEP + windows.SEP
        result = self._introspect.get_network_interfaces()
        for nic in result:
            for item in nic:
                self.assertIsInstance(nic.get(item), mock.MagicMock)
        location = r"C:\network_details.ps1"
        (self._introspect.remote_client.manager.download_resource.
         assert_called_once_with(
             resource_location="windows/network_details.ps1",
             location=location))
        (self._introspect.remote_client.run_command_verbose.
         assert_called_once_with(location, command_type=util.POWERSHELL))
        mock_get_nic_details.assert_called_once_with(
            ['fake result', '', '', '', '', 'fake result'])
