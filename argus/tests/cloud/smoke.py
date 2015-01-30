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

from argus import scenario
from argus import util
from argus.tests.cloud import util as test_util

CONF = util.get_config()
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


class PasswordRescueSmokeTest(scenario.BaseArgusTest):

    def _run_remote_command(self, cmd):
        remote_client = self.manager.get_remote_client(
            self.image.created_user,
            self.manager.instance_password())
        stdout = remote_client.run_command_verbose(cmd)
        return stdout

    @test_util.requires_service('http')
    def test_password_set(self):
        stdout = self._run_remote_command("echo 1")
        self.assertEqual('1', stdout.strip())

        self.manager.rescue_server()
        self.manager.prepare_instance()
        stdout = self._run_remote_command("echo 2")
        self.assertEqual('2', stdout.strip())

        self.manager.unrescue_server()
        stdout = self._run_remote_command("echo 3")
        self.assertEqual('3', stdout.strip())


class PasswordSmokeTest(scenario.BaseArgusTest):

    @test_util.requires_service('http')
    def test_password_set(self):
        # Test that the proper password was set.
        remote_client = self.manager.get_remote_client(
            self.image.created_user,
            self.manager.instance_password())
        # Pylint emits properly this error, but it doesn't understand
        # that this class is used as a mixin later on (and will
        # never understand these cases). So it's okay to disable
        # the message here.
        # pylint: disable=no-member

        stdout = remote_client.run_command_verbose("echo 1")
        self.assertEqual('1', stdout.strip())


# pylint: disable=abstract-method
class BaseSmokeTests(PasswordSmokeTest,
                     scenario.BaseArgusTest):
    """Various smoke tests for testing cloudbaseinit.

    Each OS test version must implement the abstract methods provided here,
    the methods will be called by each required test.
    The tests provided here are testing that basic behaviour of
    cloudbaseinit is fulfilled. OS specific tests should go in the
    specific subclass.
    """

    def test_plugins_count(self):
        # Test that we have the expected numbers of plugins.
        plugins_count = self.introspection.get_plugins_count()
        self.assertEqual(CONF.cloudbaseinit.expected_plugins_count,
                         plugins_count)

    def test_disk_expanded(self):
        # Test the disk expanded properly.
        image = self.manager.get_image_ref()
        datastore_size = image['OS-EXT-IMG-SIZE:size']
        disk_size = self.introspection.get_disk_size()
        self.assertGreater(disk_size, datastore_size)

    def test_username_created(self):
        # Verify that the expected created user exists.
        exists = self.introspection.username_exists(self.image.created_user)
        self.assertTrue(exists)

    def test_hostname_set(self):
        # Test that the hostname was properly set.
        instance_hostname = self.introspection.get_instance_hostname()
        server = self.manager.instance_server()[1]

        self.assertEqual(instance_hostname,
                         str(server['name'][:15]).lower())

    @test_util.skip_unless_dnsmasq_configured
    def test_ntp_properly_configured(self):
        # Verify that the expected NTP peers are active.
        peers = self.introspection.get_instance_ntp_peers()
        expected_peers = _get_dhcp_value('42').split(",")
        if expected_peers is None:
            self.fail('DHCP NTP option was not configured.')

        self.assertEqual(expected_peers, peers)

    def test_sshpublickeys_set(self):
        # Verify that we set the expected ssh keys.
        authorized_keys = self.introspection.get_instance_keys_path()
        public_key = self.introspection.get_instance_file_content(
            authorized_keys).replace('\r\n', '\n')
        self.assertEqual(self.manager.public_key(), public_key)

    @test_util.skip_unless_dnsmasq_configured
    def test_mtu(self):
        # Verify that we have the expected MTU in the instance.
        mtu = self.introspection.get_instance_mtu()
        expected_mtu = _get_dhcp_value('26')
        self.assertEqual(expected_mtu, mtu)

    def test_any_exception_occurred(self):
        # Verify that any exception occurred in the instance
        # for cloudbaseinit.
        instance_traceback = self.introspection.get_cloudbaseinit_traceback()
        self.assertEqual('', instance_traceback)

    def test_user_belongs_to_group(self):
        # Check that the created user belongs to the specified local groups
        members = self.introspection.get_group_members(self.image.group)
        self.assertIn(self.image.created_user, members)

    def test_get_console_output(self):
        # Verify that the product emits messages to the console output.
        resp, output = self.manager.instance_output(10)
        self.assertEqual(200, resp.status)
        self.assertTrue(output, "Console output was empty.")
        lines = len(output.split('\n'))
        self.assertEqual(lines, 10)
