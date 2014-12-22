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
from argus.tests import generic_tests
from argus import scenario
from argus import util

CONF = config.CONF


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


def _get_ntp_peers(output):
    peers = []
    for line in output.splitlines():
        if not line.startswith("Peer: "):
            continue
        _, _, entry_peers = line.partition(":")
        peers.extend(entry_peers.split(","))
    return list(filter(None, map(str.strip, peers)))


def _parse_licenses(output):
    """Parse the licenses information.

    It will return a dictionary of products and their
    license status.
    """
    licenses = {}
    # We are starting from 2, since the first line is the
    # list of fields and the second one is a separator.
    # We can't use csv to parse this, unfortunately.
    for line in output.strip().splitlines()[2:]:
        product, _, status = line.rpartition(" ")
        product = product.strip()
        licenses[product] = status
    return licenses


class WindowsUtils(generic_tests.GenericInstanceUtils):
    """Utilities for interrogating Windows instances."""

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
            homedir,
            CONF.argus.created_user,
            ".ssh",
            "authorized_keys")

    def get_instance_file_content(self, filepath):
        cmd = 'powershell "cat %s"' % filepath
        return self.remote_client.run_command_verbose(cmd)

    def get_userdata_executed_plugins(self):
        cmd = 'powershell "(Get-ChildItem -Path  C:\ *.txt).Count'
        stdout = self.remote_client.run_command_verbose(cmd)
        return int(stdout)

    def get_instance_mtu(self):
        cmd = ('powershell "(Get-NetIpConfiguration -Detailed).'
               'NetIPv4Interface.NlMTU"')
        stdout = self.remote_client.run_command_verbose(cmd)
        return stdout.strip('\r\n')

    def get_cloudbaseinit_traceback(self):
        code = util.get_resource('get_traceback.ps1')
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
            "Members\s+-+\s+(.*?)The\s+command",
            std_out, re.MULTILINE | re.DOTALL)
        if not member_search:
            raise ValueError('Unable to get members.')

        return list(filter(None, member_search.group(1).split()))


class TestWindowsServices(generic_tests.GenericTests,
                          scenario.BaseWindowsScenario):

    instance_utils_class = WindowsUtils

    def test_service_display_name(self):
        cmd = ('powershell (Get-Service "| where -Property Name '
               '-match cloudbase-init").DisplayName')

        stdout = self.run_command_verbose(cmd)
        self.assertEqual("Cloud Initialization Service\r\n", str(stdout))

    @generic_tests.skip_unless_dnsmasq_configured
    def test_ntp_service_running(self):
        # Test that the NTP service is started.
        cmd = ('powershell (Get-Service "| where -Property Name '
               '-match W32Time").Status')
        stdout = self.run_command_verbose(cmd)

        self.assertEqual("Running\r\n", str(stdout))

    def test_local_scripts_executed(self):
        super(TestWindowsServices, self).test_local_scripts_executed()

        command = 'powershell "Test-Path C:\\Scripts\\powershell.output"'
        stdout = self.remote_client.run_command_verbose(command)
        self.assertEqual('True', stdout.strip())

    def test_licensing(self):
        # Check that the instance OS was licensed properly.
        command = ('powershell "Get-WmiObject SoftwareLicensingProduct | '
                   'where PartialProductKey | Select Name, LicenseStatus"')
        stdout = self.remote_client.run_command_verbose(command)
        licenses = _parse_licenses(stdout)
        if len(licenses) > 1:
            self.fail("Too many expected products in licensing output.")

        license_status = list(licenses.values())[0]
        self.assertEqual(1, int(license_status))

    def test_https_winrm_configured(self):
        # Test that HTTPS transport protocol for WinRM is configured.
        # By default, the test images are built only for HTTP.
        remote_client = self.get_remote_client(CONF.argus.created_user,
                                               self.password(),
                                               protocol='https')
        stdout = remote_client.run_command_verbose('echo 1')
        self.assertEqual('1', stdout.strip())
