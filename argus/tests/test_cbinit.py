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
def create_tempdir():
    """Create a temporary directory.

    This is a context manager, which creates a new temporary
    directory and removes it when exiting from the context manager
    block.
    """
    tempdir = tempfile.mkdtemp(prefix="cloudbaseinit-ci-tests")
    try:
        yield tempdir
    finally:
        shutil.rmtree(tempdir)


@contextlib.contextmanager
def create_tempfile(content=None):
    """Create a temporary file.

    This is a context manager, which uses `create_tempdir` to obtain a
    temporary directory, where the file will be placed.

    :param content:
        Additionally, a string which will be written
        in the new file.
    """
    with create_tempdir() as temp:
        fd, path = tempfile.mkstemp(dir=temp)
        os.close(fd)
        if content:
            with open(path, 'w') as stream:
                stream.write(content)
        yield path


def group_members(client, group):
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

    # The actual tests.
    def test_service_keys(self):
        key = ('HKLM:SOFTWARE\\Wow6432Node\\Cloudbase` Solutions\\'
               'Cloudbase-init\\{0}\\Plugins'
               .format(self.server['id']))
        cmd = 'powershell (Get-Item %s).ValueCount' % key
        std_out = self.run_command_verbose(cmd)

        self.assertEqual(13, int(std_out))

    def test_service(self):
        cmd = ('powershell (Get-Service "| where -Property Name '
               '-match cloudbase-init").DisplayName')

        std_out = self.run_command_verbose(cmd)
        self.assertEqual("Cloud Initialization Service\r\n", str(std_out))

    def test_disk_expanded(self):
        # TODO(cpopa): after added image to instance creation,
        # added here as well
        image = self.get_image_ref()
        image_size = image[1]['OS-EXT-IMG-SIZE:size']
        cmd = ('powershell (Get-WmiObject "win32_logicaldisk | '
               'where -Property DeviceID -Match C:").Size')

        std_out = self.run_command_verbose(cmd)
        self.assertGreater(int(std_out), image_size)

    def test_username_created(self):
        cmd = ('powershell "Get-WmiObject Win32_Account | '
               'where -Property Name -contains {0}"'
               .format(CONF.argus.created_user))

        std_out = self.run_command_verbose(cmd)
        self.assertIsNotNone(std_out)

    def test_hostname_set(self):
        cmd = 'powershell (Get-WmiObject "Win32_ComputerSystem").Name'
        std_out = self.run_command_verbose(cmd)
        server = self.instance_server()[1]

        self.assertEqual(str(std_out).lower(),
                         str(server['name'][:15]).lower() + '\r\n')

    def test_ntp_service_running(self):
        cmd = ('powershell (Get-Service "| where -Property Name '
               '-match W32Time").Status')
        std_out = self.run_command_verbose(cmd)

        self.assertEqual("Running\r\n", str(std_out))

    def test_password_set(self):
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

        self.assertEqual(folder_name, str(stdout.strip("\r\n")))

    def test_sshpublickeys_set(self):
        cmd = 'echo %cd%'
        stdout = self.remote_client.run_command_verbose(cmd)
        path = stdout.strip("\r\n") + '\\.ssh\\authorized_keys'

        cmd2 = 'powershell "cat %s"' % path
        stdout = self.remote_client.run_command_verbose(cmd2)

        self.assertEqual(self.keypair['public_key'],
                         stdout.replace('\r\n', '\n'))

    def test_userdata(self):
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
        with create_tempfile(content=code) as tmp:
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
        members = group_members(self.remote_client, CONF.argus.group)
        self.assertIn(CONF.argus.created_user, members)
