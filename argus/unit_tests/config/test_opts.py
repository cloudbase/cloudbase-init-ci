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

# pylint: disable=no-value-for-parameter, protected-access, unused-argument

import unittest
from argus.config import base as conf_base
from argus.config import opts

try:
    import unittest.mock as mock
except ImportError:
    import mock


class TestOpts(unittest.TestCase):

    @mock.patch('argus.config.factory.get_options')
    @mock.patch('argus.config.base.Options')
    def test_get_options_empty(self, mock_options, mock_get_options):
        mock_get_options.return_value = []
        result = opts.get_options()
        self.assertEqual(result, mock_get_options.return_value)

    @mock.patch('argus.config.factory.get_options')
    def test_get_options_no_subclass(self, mock_get_options):
        mock_get_options.return_value = [mock.Mock] * 5
        result = opts.get_options()
        self.assertEqual(result, [])

    @mock.patch('collections.defaultdict')
    @mock.patch('argus.config.factory.get_options')
    def test_get_options(self, mock_get_options, mock_collections):
        import random
        group_name = "fake_group_name"
        result_len = random.randint(1, 10)

        class Fake(conf_base.Options):

            def __init__(self, _):
                super(Fake, self).__init__(
                    mock.sentinel, group_name)

            def register(self):
                pass

            def list(self):
                return [1]

        mock_get_options.return_value = [Fake] * result_len
        mock_collections.return_value = {group_name: []}

        result = opts.get_options()
        self.assertEqual(result, [(group_name, [1] * result_len)])
