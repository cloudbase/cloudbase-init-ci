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

import re

from tempest import config
from tempest.common.utils import data_utils

from argus import BaseTest
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


class TestServices(BaseTest):

    def test_service_keys(self):
        key = ('HKLM:SOFTWARE\\Wow6432Node\\Cloudbase` Solutions\\'
               'Cloudbase-init\\{0}\\Plugins'
               .format(self.instance['id']))               
        cmd = 'powershell (Get-Item %s).ValueCount' % key
        std_out = self.run_verbose_wsman(cmd)

        self.assertEqual(13, int(std_out))

    def test_service(self):
        cmd = ('powershell (Get-Service "| where -Property Name '
               '-match cloudbase-init").DisplayName')

        std_out = self.run_verbose_wsman(cmd)
        self.assertEqual("Cloud Initialization Service\r\n", str(std_out))

    def test_disk_expanded(self):
        # TODO(cpopa): after added image to instance creation,
        # added here as well        
        image = self.get_image_ref()
        image_size = image[1]['OS-EXT-IMG-SIZE:size']
        cmd = ('powershell (Get-WmiObject "win32_logicaldisk | '
               'where -Property DeviceID -Match C:").Size')

        std_out = self.run_verbose_wsman(cmd)
        self.assertGreaterThan(int(std_out), image_size)

    def test_username_created(self):
        cmd = ('powershell "Get-WmiObject Win32_Account | '
               'where -Property Name -contains {0}"'
               .format(CONF.cbinit.created_user))

        std_out = self.run_verbose_wsman(cmd)
        self.assertIsNotNone(std_out)

    def test_hostname_set(self):
        cmd = 'powershell (Get-WmiObject "Win32_ComputerSystem").Name'
        std_out = self.run_verbose_wsman(cmd)        
        server = self.instance_server()[1]
        
        self.assertEqual(str(std_out).lower(),
                         str(server['name'][:15]).lower() + '\r\n')

    def test_ntp_service_running(self):
        cmd = ('powershell (Get-Service "| where -Property Name '
               '-match W32Time").Status')
        std_out = self.run_verbose_wsman(cmd)
        
        self.assertEqual("Running\r\n", str(std_out))

    def test_password_set(self):        
        folder_name = data_utils.rand_name("folder")
        cmd = 'mkdir C:\\%s' % folder_name
        cmd2 = 'powershell "get-childitem c:\ | select-string %s"' % folder_name
        remote_client = util.WinRemoteClient(
            self.floating_ip['ip'],
            CONF.cbinit.created_user,
            self.password())
        remote_client.run_verbose_wsman(cmd)
        stdout = remote_client.run_verbose_wsman(cmd2)

        self.assertEqual(folder_name, str(stdout.strip("\r\n")))

    def test_sshpublickeys_set(self):        
        cmd = 'echo %cd%'
        remote_client = util.WinRemoteClient(
            self.floating_ip['ip'],
            CONF.cbinit.created_user,
            self.password())
        stdout = remote_client.run_verbose_wsman(cmd)        
        path = stdout.strip("\r\n") + '\\.ssh\\authorized_keys'

        cmd2 = 'powershell "cat %s"' % path
        stdout = remote_client.run_verbose_wsman(cmd2)

        self.assertEqual(self.keypair['public_key'],
                         stdout.replace('\r\n', '\n'))

    def test_userdata(self):        
        remote_client = util.WinRemoteClient(
            self.floating_ip['ip'],
            CONF.cbinit.created_user,
            self.password())

        cmd = 'powershell "(Get-ChildItem -Path  C:\ *.txt).Count'
        stdout = remote_client.run_verbose_wsman(cmd)

        self.assertEqual("4", stdout.strip("\r\n"))

    def test_mtu(self):
        # TODO: get value to compare with
        # net Win32_NetworkAdapterConfiguration        
        cmd = ('powershell "(Get-NetIpConfiguration -Detailed).'
               'NetIPv4Interface.NlMTU"')
        stdout = self.run_verbose_wsman(cmd)
        expected_mtu = _get_dhcp_value(DNSMASQ_NEUTRON, '26')

        self.assertEqual(stdout.strip('\r\n'), expected_mtu)
