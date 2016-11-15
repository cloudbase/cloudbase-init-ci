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

# pylint: disable=no-value-for-parameter, protected-access, abstract-method

import unittest
from argus.backends import base
from argus import util

try:
    import unittest.mock as mock
except ImportError:
    import mock


LOG = util.get_logger()


class FakeBaseBackend(base.BaseBackend):

    def __init__(self):
        super(FakeBaseBackend, self).__init__()

    def setup_instance(self):
        """Setup an underlying instance."""
        return True

    def cleanup(self):
        """Destroy and cleanup the relevant resources.

         Cleanup the resources created by :meth:`setup_instance`,
         such as the keypairs, floating ips and credentials.
         """
        return True

    def remote_client(self):
        """An astract property which should return the default client."""
        return "fake client"


class FakeCloudBackend(base.CloudBackend, FakeBaseBackend):

    def __init__(self):
        super(FakeCloudBackend, self).__init__()

    def get_remote_client(self, username=None, password=None, **kwargs):
        """Get a remote client

        This is different than :attr:`remote_client`, because that
        will always return a client with predefined credentials,
        while this method allows for a fine-grained control over this aspect.
        `password` can be omitted if authentication by SSH key is used.
        The **kwargs parameter can be used for additional
        options (currently none).
        """
        return "fake remote client"

    def instance_output(self, limit=None):
        """Get the underlying's instance output, if any.

        :param limit:
            Number of lines to fetch from the end of console log.
        """
        return "fake output"

    def internal_instance_id(self):
        """Get the underlying's instance id.

        Gets the id depending on the internals of the backend.
        """
        return "fake id"

    def reboot_instance(self):
        """Reboot the underlying instance."""
        return "fake reboot"

    def instance_password(self):
        """Get the underlying instance password, if any."""
        return "fake password"

    def private_key(self):
        """Get the underlying private key."""
        return "fake private key"

    def public_key(self):
        """Get the underlying public key."""
        return "fake public key"

    def floating_ip(self):
        """Get the floating ip that was attached to the underlying instance."""
        return "fake floating ip"


class TestCloudBackend(unittest.TestCase):

    def setUp(self):
        self._cloud_backend = FakeCloudBackend()

    def test_get_log_template_empty(self):
        result = self._cloud_backend._get_log_template(None)
        self.assertEqual(result, '{}.log')

    def test_get_log_template_suffix(self):
        result = self._cloud_backend._get_log_template("fake_suffix")
        self.assertEqual(result, '{}-fake_suffix.log')

    @mock.patch('argus.unit_tests.backends.test_base.'
                'FakeCloudBackend.instance_output')
    @mock.patch('os.path')
    @mock.patch('argus.unit_tests.backends.test_base.'
                'FakeCloudBackend._get_log_template')
    @mock.patch('argus.config.CONFIG.argus')
    def _test_save_instance_output(self, mock_config, mock_get_log_template,
                                   mock_os_path, mock_instance_output,
                                   output_directory=None,
                                   console_output=None):
        mock_config.output_directory = output_directory
        if output_directory is None:
            self._cloud_backend.save_instance_output()
            self.assertEqual(mock_get_log_template.call_count, 0)
            return
        if console_output is None:
            mock_config.output_directory = "fake output"
            mock_content = mock.Mock()
            mock_content.strip.return_value = None
            mock_os_path.join.return_value = "fake join"
            mock_instance_output.return_value = mock_content
            with mock.patch('argus.backends.base.LOG') as mock_LOG:
                self._cloud_backend.save_instance_output()
                mock_get_log_template.assert_called_once_with(None)
                mock_instance_output.assert_called_once_with()
                self.assertEqual(mock_content.strip.call_count, 1)
                mock_LOG.warning.assert_called_once_with(
                    "Empty console output; nothing to save.")
            return
        else:
            mock_config.output_directory = "no_console_output"
            mock_content = mock.Mock()
            mock_content.strip.return_value = "fake content"
            mock_os_path.join.return_value = "fake path"
            mock_instance_output.return_value = mock_content

            with mock.patch('argus.backends.base.LOG') as mock_LOG:
                with mock.patch('argus.backends.base.open') as mock_open_file:
                    self._cloud_backend.save_instance_output()
                    mock_get_log_template.assert_called_once_with(None)
                    mock_instance_output.assert_called_once_with()
                    self.assertEqual(mock_content.call_count, 0)
                    mock_open_file.assert_called_once_with(
                        mock_os_path.join.return_value, "wb")
                    mock_LOG.info.assert_called_once_with(
                        "Saving instance console output to: %s",
                        mock_os_path.join.return_value
                    )

    def test_save_instance_output_no_output_directory(self):
        self._test_save_instance_output(output_directory=None)

    def test_save_instance_output_no_console(self):
        self._test_save_instance_output(console_output=None,
                                        output_directory="fake directory")

    def test_save_instance_output_continues(self):
        self._test_save_instance_output(console_output=True,
                                        output_directory="fake directory")

    def test_instance_output(self):
        result = self._cloud_backend.instance_output()
        self.assertEqual(result, "fake output")

    def test_internal_instance_id(self):
        result = self._cloud_backend.internal_instance_id()
        self.assertEqual(result, "fake id")

    def test_reboot_instance(self):
        result = self._cloud_backend.reboot_instance()
        self.assertEqual(result, "fake reboot")

    def test_instance_password(self):
        result = self._cloud_backend.instance_password()
        self.assertEqual(result, "fake password")

    def test_private_key(self):
        result = self._cloud_backend.private_key()
        self.assertEqual(result, "fake private key")

    def test_public_key(self):
        result = self._cloud_backend.public_key()
        self.assertEqual(result, "fake public key")

    def test_floating_ip(self):
        result = self._cloud_backend.floating_ip()
        self.assertEqual(result, "fake floating ip")
