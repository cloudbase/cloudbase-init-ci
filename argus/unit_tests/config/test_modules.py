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

# pylint: disable=no-value-for-parameter, too-many-lines, protected-access
# pylint: disable=too-many-public-methods

import unittest

try:
    import unittest.mock as mock
except ImportError:
    import mock


class TestCloudbaseInitOptions(unittest.TestCase):

    def setUp(self):
        self.modules_list = (
            'argus.config.ci.ArgusOptions',
            'argus.config.cloudbaseinit.CloudbaseInitOptions',
            'argus.config.openstack.OpenStackOptions',
            'argus.config.mock_cloudstack.MockCloudStackOptions',
            'argus.config.mock_ec2.MockEC2Options',
            'argus.config.mock_maas.MockMAASOptions',
            'argus.config.mock_openstack.MockOpenStackOptions',
            'argus.config.local.LocalOptions',
        )

    @mock.patch('argus.config.ci.cfg.OptGroup')
    def test_register(self, mock_cfg):
        mock_cfg.return_value = mock.sentinel
        for module in self.modules_list:
            parts = module.rsplit('.', 1)
            module = __import__(parts[0], fromlist=parts[1])
            class_loaded = getattr(module, parts[1])

            options = class_loaded(mock.sentinel)
            options._config = mock.Mock()
            options.register()
            options._config.register_group.assert_called_once_with(
                mock_cfg.return_value)
            options._config.register_opts.assert_called_once_with(
                options._options, group=mock_cfg.return_value)

    def test_list(self):
        for module in self.modules_list:
            parts = module.rsplit('.', 1)
            module = __import__(parts[0], fromlist=parts[1])
            class_loaded = getattr(module, parts[1])

            options = class_loaded(mock.sentinel)
            result = options.list()
            self.assertEqual(result, options._options)
