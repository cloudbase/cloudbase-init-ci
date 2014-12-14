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
"""Tests for CloudbaseInit services."""
import contextlib
import os
import ntpath
import re
import tempfile
import shutil

from tempest.common.utils import data_utils

from argus import config
from argus import scenario
from argus import util

CONF = config.CONF
DNSMASQ_NEUTRON = '/etc/neutron/dnsmasq-neutron.conf'


def _get_dhcp_value(dnsmasq_neutron_path, key):
    regexp = re.compile(r'dhcp-option-forceregex match substring in '
                        'string python.{0},'.format(key))
    with open(dnsmasq_neutron_path) as f:
        for line in f:
            match = regexp.search(line)
            if match is not None:
                return line[match.end():].strip('\n')


@contextlib.contextmanager
def _create_tempdir():
    tempdir = tempfile.mkdtemp(prefix="cloudbaseinit-ci-tests")
    try:
        yield tempdir
    finally:
        shutil.rmtree(tempdir)


@contextlib.contextmanager
def _create_tempfile(content=None):
    with _create_tempdir() as temp:
        fd, path = tempfile.mkstemp(dir=temp)
        os.close(fd)
        if content:
            with open(path, 'w') as stream:
                stream.write(content)
        yield path


def _group_members(client, group):
    """Get a list of members, belonging to the given group."""
    cmd = "net localgroup {}".format(group)
    std_out = client.run_command_verbose(cmd)
    member_search = re.search(
        "Members\s+-+\s+(.*?)The\s+command",
        std_out, re.MULTILINE | re.DOTALL)
    if not member_search:
        raise ValueError('Unable to get members.')

    return list(filter(None, member_search.group(1).split()))


class TestServices(scenario.BaseScenario):

    def test_plugins_count(self):
        # Test the number of expected plugins.
        key = ('HKLM:SOFTWARE\\Wow6432Node\\Cloudbase` Solutions\\'
               'Cloudbase-init\\{0}\\Plugins'
               .format(self.server['id']))
        cmd = 'powershell (Get-Item %s).ValueCount' % key
        stdout = self.run_command_verbose(cmd)

        self.assertEqual(CONF.argus.expected_plugins_count,
                         int(stdout))

    def test_service_display_name(self):
        cmd = ('powershell (Get-Service "| where -Property Name '
               '-match cloudbase-init").DisplayName')

        stdout = self.run_command_verbose(cmd)
        self.assertEqual("Cloud Initialization Service\r\n", str(stdout))

    def test_disk_expanded(self):
        # Test the disk expanded properly.
        image = self.get_image_ref()
        image_size = image[1]['OS-EXT-IMG-SIZE:size']
        cmd = ('powershell (Get-WmiObject "win32_logicaldisk | '
               'where -Property DeviceID -Match C:").Size')

        stdout = self.run_command_verbose(cmd)
        self.assertGreater(int(stdout), image_size)

    def test_username_created(self):
        # Test that the user expected to be created by
        # CreateUserPlugin exists.
        cmd = ('powershell "Get-WmiObject Win32_Account | '
               'where -Property Name -contains {0}"'
               .format(CONF.argus.created_user))

        stdout = self.run_command_verbose(cmd)
        self.assertIsNotNone(stdout)

    def test_hostname_set(self):
        # Test that the hostname was properly set.
        cmd = 'powershell (Get-WmiObject "Win32_ComputerSystem").Name'
        stdout = self.run_command_verbose(cmd)
        server = self.instance_server()[1]

        self.assertEqual(str(stdout).lower().strip(),
                         str(server['name'][:15]).lower())

    def test_ntp_service_running(self):
        # Test that the NTP service is started.
        cmd = ('powershell (Get-Service "| where -Property Name '
               '-match W32Time").Status')
        stdout = self.run_command_verbose(cmd)

        self.assertEqual("Running\r\n", str(stdout))

    def test_password_set(self):
        # Test that the proper password was set.<F2>
        folder_name = data_utils.rand_name("folder")
        cmd = 'mkdir C:\\%s' % folder_name
        cmd2 = ('powershell "get-childitem c:\ | select-string %s"'
                % folder_name)
        remote_client = util.WinRemoteClient(
            self.floating_ip['ip'],
            CONF.argus.created_user,
            self.password())
        remote_client.run_command_verbose(cmd)
        stdout = remote_client.run_command_verbose(cmd2)

        self.assertEqual(folder_name, stdout.strip("\r\n"))

    def test_sshpublickeys_set(self):
        # Test that the SSH public keys were set.
        cmd = 'echo %cd%'
        stdout = self.remote_client.run_command_verbose(cmd)
        homedir, _, _ = stdout.rpartition(ntpath.sep)
        keys_path = ntpath.join(
            homedir,
            CONF.argus.created_user,
            ".ssh",
            "authorized_keys")

        cmd2 = 'powershell "cat %s"' % keys_path
        stdout = self.remote_client.run_command_verbose(cmd2)

        self.assertEqual(self.keypair['public_key'],
                         stdout.replace('\r\n', '\n'))

    def test_userdata(self):
        # Test that the userdata plugin executed properly the scripts.
        cmd = 'powershell "(Get-ChildItem -Path  C:\ *.txt).Count'
        stdout = self.remote_client.run_command_verbose(cmd)

        self.assertEqual("4", stdout.strip("\r\n"))

    def test_mtu(self):
        # TODO(cpopa): Get value to compare with.
        # net Win32_NetworkAdapterConfiguration
        cmd = ('powershell "(Get-NetIpConfiguration -Detailed).'
               'NetIPv4Interface.NlMTU"')
        stdout = self.run_command_verbose(cmd)
        expected_mtu = _get_dhcp_value(DNSMASQ_NEUTRON, '26')

        self.assertEqual(stdout.strip('\r\n'), expected_mtu)

    def test_any_exception_occurred(self):
        # Check that any exception occurred during execution
        # of the CloudbaseInit service.
        code = util.get_resource('get_traceback.ps1')
        remote_script = "C:\\{}.ps1".format(data_utils.rand_name())
        with _create_tempfile(content=code) as tmp:
            self.remote_client.copy_file(tmp, remote_script)
            stdout = self.remote_client.run_command_verbose(
                "powershell " + remote_script)
            self.assertEqual('', stdout.strip())

    def test_local_scripts_executed(self):
        # Check that the local scripts plugin was executed.

        # First, check if the Scripts folder was created.
        command = 'powershell "Test-Path C:\\Scripts"'
        stdout = self.remote_client.run_command_verbose(command)
        self.assertEqual('True', stdout.strip())

        # Next, check that every script we registered was called.
        command = 'powershell "Test-Path C:\\Scripts\\shell.output"'
        stdout = self.remote_client.run_command_verbose(command)
        self.assertEqual('True', stdout.strip())

        command = 'powershell "Test-Path C:\\Scripts\\powershell.output"'
        stdout = self.remote_client.run_command_verbose(command)
        self.assertEqual('True', stdout.strip())

    def test_user_belongs_to_group(self):
        # Check that the created user belongs to the specified local gorups
        members = _group_members(self.remote_client, CONF.argus.group)
        self.assertIn(CONF.argus.created_user, members)
