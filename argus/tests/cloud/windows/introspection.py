# Copyright 2015 Cloudbase Solutions Srl
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


import contextlib
import ntpath
import os
import re
import shutil
import tempfile

from tempest.common.utils import data_utils

from argus.tests.cloud import introspection
from argus import util


CONF = util.get_config()


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
        file_desc, path = tempfile.mkstemp(dir=temp)
        os.close(file_desc)
        if content:
            with open(path, 'w') as stream:
                stream.write(content)
        yield path


def _get_ntp_peers(output):
    peers = []
    for line in output.splitlines():
        if not line.startswith("Peer: "):
            continue
        _, _, entry_peers = line.partition(":")
        peers.extend(entry_peers.split(","))
    return list(filter(None, map(str.strip, peers)))


class WindowsInstanceIntrospection(introspection.BaseInstanceIntrospection):
    """Utilities for introspecting a Windows instance."""

    def get_plugins_count(self):
        key = ('HKLM:SOFTWARE\\Wow6432Node\\Cloudbase` Solutions\\'
               'Cloudbase-init\\{0}\\Plugins'
               .format(self.instance))
        cmd = 'powershell (Get-Item %s).ValueCount' % key
        stdout = self.remote_client.run_command_verbose(cmd)
        return int(stdout)

    def get_disk_size(self):
        cmd = ('powershell (Get-WmiObject "win32_logicaldisk | '
               'where -Property DeviceID -Match C:").Size')
        return int(self.remote_client.run_command_verbose(cmd))

    def username_exists(self, username):
        cmd = ('powershell "Get-WmiObject Win32_Account | '
               'where -Property Name -contains {0}"'
               .format(username))

        stdout = self.remote_client.run_command_verbose(cmd)
        return bool(stdout)

    def get_instance_hostname(self):
        cmd = 'powershell (Get-WmiObject "Win32_ComputerSystem").Name'
        stdout = self.remote_client.run_command_verbose(cmd)
        return stdout.lower().strip()

    def get_instance_ntp_peers(self):
        command = 'w32tm /query /peers'
        stdout = self.remote_client.run_command_verbose(command)
        return _get_ntp_peers(stdout)

    def get_instance_keys_path(self):
        cmd = 'echo %cd%'
        stdout = self.remote_client.run_command_verbose(cmd)
        homedir, _, _ = stdout.rpartition(ntpath.sep)
        return ntpath.join(
            homedir, self.image.created_user,
            ".ssh", "authorized_keys")

    def get_instance_file_content(self, filepath):
        cmd = 'powershell "cat %s"' % filepath
        return self.remote_client.run_command_verbose(cmd)

    def get_userdata_executed_plugins(self):
        cmd = 'powershell "(Get-ChildItem -Path  C:\\ *.txt).Count'
        stdout = self.remote_client.run_command_verbose(cmd)
        return int(stdout)

    def get_instance_mtu(self):
        cmd = ('powershell "(Get-NetIpConfiguration -Detailed).'
               'NetIPv4Interface.NlMTU"')
        stdout = self.remote_client.run_command_verbose(cmd)
        return stdout.strip('\r\n')

    def get_cloudbaseinit_traceback(self):
        code = util.get_resource('windows/get_traceback.ps1')
        remote_script = "C:\\{}.ps1".format(data_utils.rand_name())
        with _create_tempfile(content=code) as tmp:
            self.remote_client.copy_file(tmp, remote_script)
            stdout = self.remote_client.run_command_verbose(
                "powershell " + remote_script)
            return stdout.strip()

    def instance_shell_script_executed(self):
        command = 'powershell "Test-Path C:\\Scripts\\shell.output"'
        stdout = self.remote_client.run_command_verbose(command)
        return stdout.strip() == 'True'

    def get_group_members(self, group):
        cmd = "net localgroup {}".format(group)
        std_out = self.remote_client.run_command_verbose(cmd)
        member_search = re.search(
            r"Members\s+-+\s+(.*?)The\s+command",
            std_out, re.MULTILINE | re.DOTALL)
        if not member_search:
            raise ValueError('Unable to get members.')

        return list(filter(None, member_search.group(1).split()))

    def list_location(self, location):
        command = "dir {} /b".format(location)
        stdout = self.remote_client.run_command_verbose(command)
        return list(filter(None, stdout.splitlines()))

    def get_service_triggers(self, service):
        """Get the triggers of the given service.

        Return a tuple of two elements, where the first is the start
        trigger and the second is the end trigger.
        """
        command = "sc qtriggerinfo {}".format(service)
        stdout = self.remote_client.run_command_verbose(command)
        match = re.search(r"START SERVICE\s+(.*?):.*?STOP SERVICE\s+(.*?):",
                          stdout, re.DOTALL)
        if not match:
            raise ValueError("Unable to get the triggers for the "
                             "given service.")
        return (match.group(1).strip(), match.group(2).strip())
