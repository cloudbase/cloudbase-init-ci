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

# pylint: disable=no-value-for-parameter, protected-access, arguments-differ
# pylint: disable=bad-super-call

import unittest
from argus.config_generator.windows import base
import six


try:
    import unittest.mock as mock
except ImportError:
    import mock


class FakeBaseWindowsConfig(base.BaseWindowsConfig):
    def __init__(self):
        super(FakeBaseWindowsConfig, self).__init__(mock.sentinel)

    def _config_specific_paths(self):
        return mock.sentinel

    def set_conf_value(self, name, value, section):
        return mock.sentinel


class BaseWindowsConfig(unittest.TestCase):

    @mock.patch('argus.config_generator.windows.base.'
                'BaseWindowsConfig._config_specific_paths')
    @mock.patch('argus.config_generator.windows.base.'
                'BaseWindowsConfig._get_base_conf')
    def setUp(self, mock_get_base_conf, _):
        mock_get_base_conf.return_value = mock.sentinel
        self._cbinit_config = FakeBaseWindowsConfig()

    def test_conf(self):
        self._cbinit_config._conf = mock.sentinel
        result = self._cbinit_config.conf
        self.assertEqual(result, self._cbinit_config._conf)

    @mock.patch('six.moves.configparser.ConfigParser')
    @mock.patch('argus.util.get_resource')
    @mock.patch('argus.config_generator.windows.base.StringIO')
    def _test_get_base_conf(self, mock_string_io, mock_get_resource,
                            mock_configparser, py_version):
        mock_string_io.return_value = mock.sentinel
        mock_get_resource.return_value = mock.sentinel
        mock_conf = mock.Mock()
        mock_configparser.return_value = mock_conf
        if py_version == 2:
            six.PY2 = True
        else:
            six.PY2 = None

        result = self._cbinit_config._get_base_conf(mock.sentinel)
        self.assertEqual(result, mock_conf)
        mock_string_io.assert_called_once_with(mock_get_resource.return_value)
        mock_get_resource.assert_called_once_with(mock.sentinel)
        mock_configparser.assert_called_once_with()
        if py_version == 2:
            mock_conf.readfp.assert_called_once_with(
                mock_string_io.return_value)
        else:
            mock_conf.read_file.assert_called_once_with(
                mock_string_io.return_value)

    def test_get_base_conf_py2(self):
        self._test_get_base_conf(py_version=2)

    def test_get_base_conf_py_not_2(self):
        self._test_get_base_conf(py_version=3)

    @mock.patch('argus.config_generator.windows.base.'
                'BaseWindowsConfig.conf')
    @mock.patch('argus.config_generator.windows.base.StringIO')
    @mock.patch('ntpath.join')
    def _test_apply_config(self, mock_join, mock_string_io, _, is_file):
        mock_join.return_value = mock.sentinel
        mock_manager = mock.Mock()
        mock_manager.is_file.return_value = is_file
        mock_buff = mock.Mock()
        mock_data = mock.Mock()
        mock_data.splitlines.return_value = [mock.Mock] * 5
        mock_buff.read.return_value = mock_data
        mock_string_io.return_value = mock_buff
        mock_client = mock.Mock()
        mock_client.mock_manager = mock_manager
        self._cbinit_config._client = mock_client
        self._cbinit_config.config_name = mock.sentinel

        self._cbinit_config.apply_config(mock.sentinel)

        mock_join.assert_called_once_with(mock.sentinel, mock.sentinel)
        self._cbinit_config._client.manager.is_file.assert_called_once_with(
            mock.sentinel)
        if is_file:
            self._cbinit_config._client.manager.remove.assert_called_once_with(
                mock.sentinel)
        mock_string_io.assert_called_once_with()
        self._cbinit_config.conf.write.assert_called_once_with(
            mock_string_io.return_value)
        mock_buff.seek.assert_called_once_with(0)
        mock_buff.read.assert_called_once_with()
        mock_data.splitlines.assert_called_once_with()
        self.assertEqual(self._cbinit_config._client.write_file.call_count, 5)

    def test_apply_config_is_file(self):
        self._test_apply_config(is_file=True)

    def test_apply_config_is_no_file(self):
        self._test_apply_config(is_file=None)

    def test_config_specific_paths(self):
        result = (super(FakeBaseWindowsConfig, self._cbinit_config).
                  _config_specific_paths())
        self.assertEqual(result, None)
