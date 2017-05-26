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
from argus.recipes import base

try:
    import unittest.mock as mock
except ImportError:
    import mock


class FakeBaseRecipe(base.BaseRecipe):
    def __init__(self, backend):
        base.BaseRecipe.__init__(self, backend)

    def prepare(self, **kwargs):
        pass

    def cleanup(self, **kwargs):
        pass


class TestBaseRecipe(unittest.TestCase):
    def setUp(self):
        self._base = FakeBaseRecipe(mock.Mock())

    def test_execute(self):
        (self._base._backend.remote_client.run_command_with_retry.
         return_value) = ["fake execute"]
        result = self._base._execute(cmd="fake_cmd")
        self.assertEqual(result, "fake execute")
        (self._base._backend.remote_client.run_command_with_retry.
         assert_called_once_with(
             "fake_cmd", count=base.RETRY_COUNT, delay=base.RETRY_DELAY,
             command_type=None,
             upper_timeout=base.CONFIG.argus.upper_timeout))

    def test__execute_until_condition(self):
        self._base._execute_until_condition(cmd="fake_cmd", cond="fake_cond")
        (self._base._backend.remote_client.run_command_until_condition.
         assert_called_once_with(
             "fake_cmd", "fake_cond", retry_count=base.RETRY_COUNT,
             delay=base.RETRY_DELAY, command_type=None,))
