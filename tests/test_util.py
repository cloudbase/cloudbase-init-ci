# Copyright 2015 Cloudbase Solutions Srl
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

import os
import tempfile
import textwrap
import unittest

from argus import util


class TestConfigurationPatcher(unittest.TestCase):
    """Test for argus.util.ConfigurationPatcher."""

    def _get_tempfile(self, content):
        fd, tmp = tempfile.mkstemp()
        os.close(fd)
        self.addCleanup(os.remove, tmp)

        with open(tmp, 'w') as stream:
            stream.write(content)
        return tmp

    def test_patcher(self):
        tmp = self._get_tempfile(textwrap.dedent('''
        [DEFAULT]
        b = 2
        a = 1

        [TEST]
        c = 3
        '''))

        patcher = util.ConfigurationPatcher(
            tmp,
            DEFAULT={'a': '2', 'b': '3'},
            TEST={'c': 4})
        with patcher:
            expected = textwrap.dedent('''
            [DEFAULT]
            b = 3
            a = 2

            [TEST]
            c = 4
            ''')
            with open(tmp) as stream:
                actual = stream.read()
            self.assertEqual(expected.strip(), actual.strip())
