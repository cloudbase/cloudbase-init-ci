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
from argus.introspection import base

try:
    import unittest.mock as mock
except ImportError:
    import mock


class TestBaseInstanceIntrospection(unittest.TestCase):
    def setUp(self):
        self._base = base.BaseInstanceIntrospection(mock.sentinel)

    def test_init(self):
        self.assertEqual(self._base.remote_client, mock.sentinel)
