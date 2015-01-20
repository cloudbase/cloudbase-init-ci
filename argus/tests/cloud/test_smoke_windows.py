# Copyright 2014 Cloudbase Solutions Srl
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

"""Smoke tests for the cloudbaseinit."""

from argus import scenario
from argus.tests.cloud import introspection
from argus.tests.cloud import smoke
from argus import util


CONF = util.get_config()


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


class TestWindowsSmoke(smoke.BaseSmokeTests,
                       scenario.BaseWindowsScenario):

    introspection_class = introspection.WindowsInstanceIntrospection

    def test_service_display_name(self):
        cmd = ('powershell (Get-Service "| where -Property Name '
               '-match cloudbase-init").DisplayName')

        stdout = self.run_command_verbose(cmd)
        self.assertEqual("Cloud Initialization Service\r\n", str(stdout))

    @smoke.skip_unless_dnsmasq_configured
    def test_ntp_service_running(self):
        # Test that the NTP service is started.
        cmd = ('powershell (Get-Service "| where -Property Name '
               '-match W32Time").Status')
        stdout = self.run_command_verbose(cmd)

        self.assertEqual("Running\r\n", str(stdout))

    def test_local_scripts_executed(self):
        super(TestWindowsSmoke, self).test_local_scripts_executed()

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
        remote_client = self.get_remote_client(CONF.argus.default_ci_username,
                                               CONF.argus.default_ci_password,
                                               protocol='https')
        stdout = remote_client.run_command_verbose('echo 1')
        self.assertEqual('1', stdout.strip())

    @smoke.skip_unless_dnsmasq_configured
    def test_w32time_triggers(self):
        # Test that w32time has network availability triggers, not
        # domain joined triggers
        start_trigger, _ = self.introspection.get_service_triggers('w32time')
        self.assertEqual('IP ADDRESS AVAILABILITY', start_trigger)
