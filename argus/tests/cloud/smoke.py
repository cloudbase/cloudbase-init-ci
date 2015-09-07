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

import binascii
import os
import time
import unittest

# pylint: disable=import-error
from six.moves import urllib

from argus.tests import base
from argus.tests.cloud import util as test_util
from argus import util

DNSMASQ_NEUTRON = '/etc/neutron/dnsmasq-neutron.conf'

LOG = util.get_logger()


def _get_dhcp_value(key):
    """Get the value of an override from the dnsmasq-config file.

    An override will be have the format 'dhcp-option-force=key,value'.
    """
    lookup = "dhcp-option-force={}".format(key)
    with open(DNSMASQ_NEUTRON) as stream:
        for line in stream:
            if not line.startswith(lookup):
                continue
            _, _, option_value = line.strip().partition("=")
            _, _, value = option_value.partition(",")
            return value.strip()


class BaseTestPassword(base.BaseTestCase):
    """Base test class for testing that passwords were set properly."""

    def _run_remote_command(self, cmd, password):
        # Test that the proper password was set.
        remote_client = self._backend.get_remote_client(
            self._conf.cloudbaseinit.created_user, password)

        stdout = remote_client.run_command_verbose(cmd)
        return stdout

    def is_password_set(self, password):
        stdout = self._run_remote_command("echo 1", password)
        self.assertEqual('1', stdout.strip())


class TestPasswordMetadataSmoke(BaseTestPassword):
    """Password test with a provided metadata password.

    This should be used when the underlying metadata service does
    not support password posting.
    """

    def test_password_set_from_metadata(self):
        metadata = self._backend.get_metadata()
        if metadata and metadata.get('admin_pass'):
            password = metadata['admin_pass']
            self.is_password_set(password)
        else:
            raise unittest.SkipTest("No metadata password")


class TestPasswordPostedSmoke(BaseTestPassword):
    """Test that the password was set and posted to the metadata service

    This will attempt a WinRM login on the instance, which will use the
    password which was correctly set by the underlying cloud
    initialisation software.
    """

    @property
    def password(self):
        return self._backend.instance_password()

    @test_util.requires_service('http')
    def test_password_set_posted(self):
        self.is_password_set(password=self.password)


class TestPasswordPostedRescueSmoke(TestPasswordPostedSmoke):
    """Test that the password can be used in case of rescued instances."""

    @test_util.requires_service('http')
    def test_password_set_on_rescue(self):
        password = self.password

        stdout = self._run_remote_command("echo 1", password=password)
        self.assertEqual('1', stdout.strip())

        self._backend.rescue_server()
        self._backend.prepare_instance()
        stdout = self._run_remote_command("echo 2", password=password)
        self.assertEqual('2', stdout.strip())

        self._backend.unrescue_server()
        stdout = self._run_remote_command("echo 3", password=password)
        self.assertEqual('3', stdout.strip())


class TestCloudstackUpdatePasswordSmoke(base.BaseTestCase):
    """
    Test that the cloud initialisation service
    can update passwords when using the Cloudstack metadata service.
    """

    @property
    def service_url(self):
        return "http://%(host)s:%(port)s/" % {"host": "0.0.0.0",
                                              "port": 8080}

    @property
    def password(self):
        generated = binascii.hexlify(os.urandom(14)).decode()
        return generated + "!*"

    def _update_password(self, password):
        url = urllib.parse.urljoin(self.service_url, 'password')
        if password:
            params = {'password': password}
        else:
            params = {}
        data = urllib.parse.urlencode(params)
        request = urllib.request.Request(url, data=data)
        try:
            response = urllib.request.urlopen(request)
        except urllib.error.HTTPError as exc:
            return exc.code
        return response.getcode()

    def _wait_for_service_status(self, status, retry_count=3,
                                 retry_interval=1):
        while retry_count:
            response_status = None
            retry_count -= 1
            try:
                response = urllib.request.urlopen(self.service_url)
                response_status = response.getcode()
            except urllib.error.HTTPError as error:
                response_status = error.code
            except urllib.error.URLError:
                pass

            if response_status == status:
                return True
            time.sleep(retry_interval)

        return False

    def _wait_for_completion(self, password):
        wait_cmd = ('powershell (Get-Service "| where -Property Name '
                    '-match cloudbase-init").Status')
        remote_client = self._backend.get_remote_client(
            self._conf.cloudbaseinit.created_user, password)
        remote_client.run_command_until_condition(
            wait_cmd,
            lambda out: out.strip() == 'Stopped',
            retry_count=util.RETRY_COUNT, delay=util.RETRY_DELAY)

    def _test_password(self, password, expected):
        # Set the password in the Password Server.
        response = self._update_password(password)
        self.assertEqual(200, response)

        # Reboot the instance.
        self._backend.reboot_instance()

        # Check if the password was set properly.
        self._wait_for_completion(expected)

    def test_update_password(self):
        # Get the password from the metadata.
        password = self._backend.get_metadata()['admin_pass']

        with self._backend.instantiate_mock_services():
            # Wait until the web service starts serving requests.
            self.assertTrue(self._wait_for_service_status(status=400))

            # Set a new password in Password Server and test if the
            # plugin updates the password.
            new_password = self.password
            self._test_password(password=new_password, expected=new_password)
            self._backend.save_instance_output(suffix="password-1")

            # Remove the password from Password Server in order to check
            # if the plugin keeps the last password.
            self._test_password(password=None, expected=new_password)
            self._backend.save_instance_output(suffix="password-2")

            # Change the password again and check if the plugin updates it.
            self._test_password(password=password, expected=password)
            self._backend.save_instance_output(suffix="password-3")


class TestCreatedUser(base.BaseTestCase):
    """
    Test that the user created by the cloud initialisation service
    was actually created.
    """

    def test_username_created(self):
        # Verify that the expected created user exists.
        exists = self._introspection.username_exists(
            self._conf.cloudbaseinit.created_user)
        self.assertTrue(exists)


class TestSetTimezone(base.BaseTestCase):
    """Test that the expected timezone was set in the instance."""

    def test_set_timezone(self):
        # Verify that the instance timezone matches what we are
        # expecting from it.
        timezone = self._introspection.get_timezone()
        self.assertEqual("Georgian Standard Time", timezone.strip())


class TestSetHostname(base.BaseTestCase):
    """Test that the expected hostname was set in the instance."""

    def test_set_hostname(self):
        # Verify that the instance hostname matches what we are
        # expecting from it.

        hostname = self._introspection.get_instance_hostname()
        self.assertEqual("newhostname", hostname.strip())


class TestNoError(base.BaseTestCase):
    """Test class which verifies that no traceback occurs."""

    def test_any_exception_occurred(self):
        # Verify that any exception occurred in the instance
        # for cloudbaseinit.
        instance_traceback = self._introspection.get_cloudbaseinit_traceback()
        self.assertEqual('', instance_traceback)


class TestPowershellMultipartX86TxtExists(base.BaseTestCase):
    """Tests that the file powershell_multipart_x86.txt exists on C:"""

    def test_file_exists(self):
        names = self._introspection.list_location("C:\\")
        self.assertIn("powershell_multipart_x86.txt", names)


# pylint: disable=abstract-method
class TestsBaseSmoke(TestCreatedUser,
                     TestPasswordPostedSmoke,
                     TestPasswordMetadataSmoke,
                     TestNoError,
                     base.BaseTestCase):
    """Various smoke tests for testing cloudbaseinit."""

    def test_plugins_count(self):
        # Test that we have the expected numbers of plugins.
        plugins_count = self._introspection.get_plugins_count(
            self._backend.instance_server()['id'])
        self.assertEqual(self._conf.cloudbaseinit.expected_plugins_count,
                         plugins_count)

    def test_disk_expanded(self):
        # Test the disk expanded properly.
        image = self._backend.get_image_by_ref()
        datastore_size = image['OS-EXT-IMG-SIZE:size']
        disk_size = self._introspection.get_disk_size()
        self.assertGreater(disk_size, datastore_size)

    def test_hostname_set(self):
        # Test that the hostname was properly set.
        instance_hostname = self._introspection.get_instance_hostname()
        server = self._backend.instance_server()

        self.assertEqual(instance_hostname,
                         str(server['name'][:15]).lower())

    @test_util.skip_unless_dnsmasq_configured
    def test_ntp_properly_configured(self):
        # Verify that the expected NTP peers are active.
        peers = self._introspection.get_instance_ntp_peers()
        expected_peers = _get_dhcp_value('42').split(",")
        if expected_peers is None:
            self.fail('DHCP NTP option was not configured.')

        self.assertEqual(expected_peers, peers)

    def test_sshpublickeys_set(self):
        # Verify that we set the expected ssh keys.
        authorized_keys = self._introspection.get_instance_keys_path()
        public_keys = self._introspection.get_instance_file_content(
            authorized_keys).splitlines()
        self.assertEqual(set(self._backend.public_key().splitlines()),
                         set(public_keys))

    @test_util.skip_unless_dnsmasq_configured
    def test_mtu(self):
        # Verify that we have the expected MTU in the instance.
        mtu = self._introspection.get_instance_mtu()
        expected_mtu = _get_dhcp_value('26')
        self.assertEqual(expected_mtu, mtu)

    def test_user_belongs_to_group(self):
        # Check that the created user belongs to the specified local groups
        members = self._introspection.get_group_members(
            self._conf.cloudbaseinit.group)
        self.assertIn(self._conf.cloudbaseinit.created_user, members)

    def test_get_console_output(self):
        # Verify that the product emits messages to the console output.
        output = self._backend.instance_output()
        self.assertTrue(output, "Console output was empty.")


class TestStaticNetwork(base.BaseTestCase):
    """Test that the static network was configured properly in instance."""

    def test_static_network(self):
        """Check if the attached NICs were properly configured."""
        # Get network adapter details within the guest compute node.
        guest_nics = self._backend.get_network_interfaces()

        # Get network adapter details within the instance.
        instance_nics = self._introspection.get_network_interfaces()

        # Filter them by DHCP disabled status for static checks.
        filter_nics = lambda nics: [nic for nic in nics if not nic["dhcp"]]
        guest_nics = filter_nics(guest_nics)
        instance_nics = filter_nics(instance_nics)

        # Sort by hardware address and compare results.
        sort_func = lambda arg: arg["mac"]
        guest_nics.sort(key=sort_func)
        instance_nics.sort(key=sort_func)
        # Do not take into account v6 DNSes, because
        # they aren't retrieved even when they are set.
        for nics in (guest_nics, instance_nics):
            for nic in nics:
                nic["dns6"] = None

        # If os version < 6.2 then ip v6 configuration is not available
        # so we need to remove all ip v6 related keys from the dicts
        version = self._introspection.get_instance_os_version()
        if version < (6, 2):
            for nic in guest_nics:
                for key in list(nic.keys()):
                    if key.endswith('6'):
                        del nic[key]
            for nic in instance_nics:
                for key in list(nic.keys()):
                    if key.endswith('6'):
                        del nic[key]

        self.assertEqual(guest_nics, instance_nics)


class TestPublicKeys(base.BaseTestCase):

    def test_public_keys(self):
        # Check multiple ssh keys case.
        authorized_keys = self._introspection.get_instance_keys_path()
        public_keys = self._introspection.get_instance_file_content(
            authorized_keys).splitlines()
        self.assertEqual(set(util.get_public_keys()),
                         set(public_keys))
