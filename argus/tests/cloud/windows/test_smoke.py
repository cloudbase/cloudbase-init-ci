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

import pkg_resources

from argus.tests import base
from argus.tests.cloud import smoke
from argus.tests.cloud import util as test_util
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


class TestSmoke(smoke.TestsBaseSmoke):
    """Test additional Windows specific behaviour."""

    def test_service_display_name(self):
        cmd = ('powershell (Get-Service "| where -Property Name '
               '-match cloudbase-init").DisplayName')

        stdout = self.backend.remote_client.run_command_verbose(cmd)
        self.assertEqual("Cloud Initialization Service\r\n", str(stdout))

    @test_util.skip_unless_dnsmasq_configured
    def test_ntp_service_running(self):
        # Test that the NTP service is started.
        cmd = ('powershell (Get-Service "| where -Property Name '
               '-match W32Time").Status')
        stdout = self.backend.remote_client.run_command_verbose(cmd)

        self.assertEqual("Running\r\n", str(stdout))

    def test_licensing(self):
        # Check that the instance OS was licensed properly.
        command = ('powershell "Get-WmiObject SoftwareLicensingProduct | '
                   'where PartialProductKey | Select Name, LicenseStatus"')
        stdout = self.backend.remote_client.run_command_verbose(command)
        licenses = _parse_licenses(stdout)
        if len(licenses) > 1:
            self.fail("Too many expected products in licensing output.")

        license_status = list(licenses.values())[0]
        self.assertEqual(1, int(license_status))

    def test_https_winrm_configured(self):
        # Test that HTTPS transport protocol for WinRM is configured.
        # By default, the test images are built only for HTTP.
        remote_client = self.manager.get_remote_client(
            self.image.default_ci_username,
            self.image.default_ci_password,
            protocol='https')
        stdout = remote_client.run_command_verbose('echo 1')
        self.assertEqual('1', stdout.strip())

    @test_util.skip_unless_dnsmasq_configured
    def test_w32time_triggers(self):
        # Test that w32time has network availability triggers, not
        # domain joined triggers
        start_trigger, _ = self.introspection.get_service_triggers('w32time')
        self.assertEqual('IP ADDRESS AVAILABILITY', start_trigger)


class TestScriptsUserdataSmoke(TestSmoke):
    """This test is tied up to a particular userdata:

       resources/windows/multipart_userdata

    Because of this, it is separated from the actual Windows smoke tests,
    but inherits from it in order to test the same things.
    """

    def test_cloudconfig_userdata(self):
        # Verify that the cloudconfig part handler plugin executed correctly.
        files = self.introspection.get_cloudconfig_executed_plugins()
        expected = {
            'b64', 'b64_1',
            'gzip', 'gzip_1',
            'gzip_base64', 'gzip_base64_1', 'gzip_base64_2'
        }
        self.assertTrue(expected.issubset(set(files)),
                        "The expected set is not subset of {}"
                        .format(files))

        # The content of the cloudconfig files is '42', encoded
        # in various forms. This is known in advance, so the
        # multipart is tied with this test.
        self.assertEqual(set(files.values()), {'42'})

    def test_userdata(self):
        # Verify that we executed the expected number of
        # user data plugins.
        userdata_executed_plugins = (
            self.introspection.get_userdata_executed_plugins())
        self.assertEqual(5, userdata_executed_plugins)

    def test_local_scripts_executed(self):
        # Verify that the shell script we provided as local script
        # was executed.
        self.assertTrue(self.introspection.instance_shell_script_executed())
        self.assertTrue(self.introspection.instance_exe_script_executed())
        command = 'powershell "Test-Path C:\\Scripts\\powershell.output"'
        stdout = self.remote_client.run_command_verbose(command)
        self.assertEqual('True', stdout.strip())


"""
class TestEC2Userdata(base.TestBaseArgus):
    """Test the EC2 config userdata."""

    def test_ec2_script(self):
        file_name = "ec2file.txt"
        directory_name = "ec2dir"
        names = self.introspection.list_location("C:\\")
        self.assertIn(file_name, names)
        self.assertIn(directory_name, names)


class TestCertificateWinRM(base.TestBaseArgus):
    """Test that WinRM certificate authentication works as expected."""

    def test_winrm_certificate_auth(self):
        cert_pem = pkg_resources.resource_filename(
            "argus.resources", "cert.pem")
        cert_key = pkg_resources.resource_filename(
            "argus.resources", "key.pem")
        client = self.manager.get_remote_client(cert_pem=cert_pem,
                                                cert_key=cert_key)
        stdout = client.run_command_verbose("echo 1")
        self.assertEqual(stdout.strip(), "1")


class TestNextLogonPassword(base.TestBaseArgus):
    ads_uf_password_expired = 0x800000
    password_expired_flag = 1

    def _wait_for_completion(self):
        wait_cmd = ('powershell (Get-Service "| where -Property Name '
                    '-match cloudbase-init").Status')
        remote_client = self.manager.get_remote_client(
            self.image.default_ci_username,
            self.image.default_ci_password)
        remote_client.run_command_until_condition(
            wait_cmd,
            lambda out: out.strip() == 'Stopped',
            count=util.RETRY_COUNT, delay=util.RETRY_DELAY)

    def test_next_logon_password_not_changed(self):
        self._wait_for_completion()

        output = self.introspection.get_user_flags(
            CONF.cloudbaseinit.created_user)
        flags, password_expired = output.splitlines()
        flags = int(flags)
        password_expired = int(password_expired)

        self.assertEqual(password_expired, self.password_expired_flag)
        self.assertEqual(flags & self.ads_uf_password_expired,
                         self.ads_uf_password_expired,
                         "The user have different flags than expected.")


class TestLocalScripts(base.TestBaseArgus):

    def test_local_scripts(self):
        "Check if the script(s) executed entirely."
        names = self.introspection.list_location("C:\\")
        self.assertIn("reboot", names)
        self.assertIn("reboot2", names)
"""
