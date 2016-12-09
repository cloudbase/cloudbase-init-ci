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
from argus.config import base

try:
    import unittest.mock as mock
except ImportError:
    import mock


class FakeOptions(base.Options):
    def __init__(self):
        super(FakeOptions, self).__init__(mock.sentinel)

    def register(self):
        pass

    def list(self):
        pass


class TestOptions(unittest.TestCase):
    def setUp(self):
        self._options = FakeOptions()

    def test_group_name(self):
        result = self._options.group_name
        self.assertEqual(result, self._options._group_name)

    def test_register(self):
        result = super(FakeOptions, self._options).register()
        self.assertEqual(result, None)

    def test_list(self):
        result = super(FakeOptions, self._options).list()
        self.assertEqual(result, None)
