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
from argus import config as argus_config
from argus.recipes.cloud import base
from argus.unit_tests import test_utils
from argus import util


try:
    import unittest.mock as mock
except ImportError:
    import mock


CONFIG = argus_config.CONFIG
LOG = util.get_logger()


class FakeBaseCloudbaseinitRecipe(base.BaseCloudbaseinitRecipe):
    def __init__(self, backend):
        base.BaseCloudbaseinitRecipe.__init__(self, backend)

    def wait_for_boot_completion(self):
        pass

    def get_installation_script(self):
        pass

    def install_cbinit(self):
        pass

    def wait_cbinit_finalization(self):
        pass

    def sysprep(self):
        pass

    def replace_install(self):
        pass

    def replace_code(self):
        pass

    def prepare_cbinit_config(self, service_type):
        pass

    def inject_cbinit_config(self):
        pass

    def get_cb_init_logs(self):
        pass

    def get_cb_init_confs(self):
        pass


class TestBaseCloudbaseinitRecipe(unittest.TestCase):
    def setUp(self):
        self._base = FakeBaseCloudbaseinitRecipe(mock.Mock())

    @mock.patch('argus.recipes.cloud.base.six.moves')
    def _test_prepare(self, mock_six_moves, pause=False):
        CONFIG.argus.pause = pause
        expected_logging = [
            "Preparing instance...",
            "Finished preparing instance."
        ]
        with test_utils.LogSnatcher('argus.recipes.cloud.base') as snatcher:
            self._base.prepare(service_type="fake type")
        self.assertEqual(expected_logging, snatcher.output)
        if pause:
            mock_six_moves.input.assert_called_once_with(
                "Press Enter to continue...")

    def test_prepare(self):
        self._test_prepare()

    def test_prepare_pause(self):
        self._test_prepare(pause=True)
