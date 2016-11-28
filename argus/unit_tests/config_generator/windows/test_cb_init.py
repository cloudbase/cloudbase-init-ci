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
# pylint: disable=unused-argument

import unittest
from argus.config_generator.windows import cb_init

import argus

try:
    import unittest.mock as mock
except ImportError:
    import mock


class BasePopulatedCBInitConfig(unittest.TestCase):
    @mock.patch('argus.config_generator.windows.base.'
                'BaseWindowsConfig._get_base_conf')
    @mock.patch('argus.config_generator.windows.cb_init.'
                'BasePopulatedCBInitConfig._config_specific_paths')
    def setUp(self, _, __):
        self._base = cb_init.BasePopulatedCBInitConfig(mock.sentinel)

    def _test_set_conf_value(self, value="", has_section=False,
                             section="DEFAULT"):
        self._base.conf.has_section = mock.Mock(return_value=has_section)
        self._base.conf.add_section = mock.Mock()
        self._base.conf.set = mock.Mock()

        name = mock.Mock()
        value = mock.Mock()
        section = mock.Mock()

        self._base.set_conf_value(name, value=value, section=section)

        self._base.conf.has_section.assert_called_once_with(section)
        if not has_section and section != "DEFAULT":
            self._base.conf.add_section.assert_called_once_with(section)
        self._base.conf.set.assert_called_once_with(
            section, name, value)

    def test_set_conf_value_add_section(self):
        self._test_set_conf_value(value=mock.sentinel, has_section=False,
                                  section=mock.sentinel)

    def test_set_conf_value_no_add_section(self):
        self._test_set_conf_value(value=mock.sentinel, has_section=True,
                                  section=mock.sentinel)

    def test_execut(self):
        mock_client = mock.Mock()
        mock_client.run_command_with_retry.return_value = [mock.sentinel]
        self._base._client = mock_client

        result = self._base._execute(cmd=mock.sentinel, count=mock.sentinel,
                                     delay=mock.sentinel)
        self.assertEqual(result, mock.sentinel)

    @mock.patch('ntpath.join')
    @mock.patch('argus.config_generator.windows.cb_init.'
                'BasePopulatedCBInitConfig.set_conf_value')
    @mock.patch('argus.introspection.cloud.windows.get_cbinit_dir')
    def test_config_specific_paths(self, mock_get_cbinit_dir,
                                   mock_set_conf_value, mock_join):
        self._base._execute = mock.sentinel
        self._base._config_specific_paths()
        mock_get_cbinit_dir.assert_called_once_with(self._base._execute)
        self.assertEqual(mock_set_conf_value.call_count, 4)
        self.assertEqual(mock_join.call_count, 4)

    def test_get_service(self):
        service_type = "fake service"
        argus.util.SERVICES_PREFIX = "fake prefix"
        self._base.SERVICES[service_type] = "fake service type"
        result = self._base._get_service(service_type)
        expected_result = '.'.join(["fake prefix", "fake service type"])
        self.assertEqual(result, expected_result)

    def _test_set_service_type(self, service_type):
        self._base.set_conf_value = mock.Mock()
        if service_type is None:
            argus.util.HTTP_SERVICE = "fake service"
            services = [argus.util.HTTP_SERVICE]
        else:
            services = service_type
        self._base._get_service = mock.Mock(side_effect=services)
        self._base.set_service_type(service_type)
        self.assertEqual(
            self._base._get_service.call_count, len(services))
        self._base.set_conf_value.assert_called_once_with(
            "metadata_services", ",".join(services))

    def test_set_service_type(self):
        services_list = ['service 1', 'service 2', 'service 3']
        self._test_set_service_type(services_list)

    def test_set_service_type_(self):
        self._test_set_service_type(None)

    @mock.patch('ntpath.join')
    @mock.patch('argus.config_generator.windows.base.'
                'BaseWindowsConfig.apply_config')
    def test_apply_config(self, mock_apply_config, mock_join):
        path = "fake path"
        self._base.config_name = mock.sentinel
        mock_client = mock.Mock()
        self._base._client = mock_client
        argus.util.POWERSHELL = mock.sentinel
        cmd = ("(get-content '{filename}')| "
               "out-file '{filename}' -encoding ascii")
        mock_join.return_value = "fake path"

        self._base.apply_config(path)

        mock_apply_config.assert_called_once_with(path)
        mock_join.assert_called_once_with(path, self._base.config_name)
        self._base._client.run_command_with_retry.assert_called_once_with(
            cmd.format(filename=mock_join.return_value),
            command_type=argus.util.POWERSHELL)
