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

# pylint: disable=no-value-for-parameter, protected-access, bad-super-call

import unittest
from argus.config_generator import base

try:
    import unittest.mock as mock
except ImportError:
    import mock


class FakeBaseConfig(base.BaseConfig):

    def __init__(self):
        super(FakeBaseConfig, self).__init__(mock.sentinel)

    def set_conf_value(self, name, value, section):
        return mock.sentinel

    def apply_config(self, path):
        return mock.sentinel


class TestBaseConfig(unittest.TestCase):
    def setUp(self):
        self._baseconfig = FakeBaseConfig()

    def test_set_conf_value(self):
        result = (super(FakeBaseConfig, self._baseconfig).
                  set_conf_value(mock.sentinel, mock.sentinel,
                                 mock.sentinel))
        self.assertEqual(result, None)

    def test_apply_config(self):
        result = (super(FakeBaseConfig, self._baseconfig).
                  apply_config(mock.sentinel))
        self.assertEqual(result, None)
