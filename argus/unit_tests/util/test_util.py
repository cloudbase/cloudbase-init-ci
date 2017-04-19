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
# pylint: disable=wrong-import-order
import unittest

from argus import util

try:
    import unittest.mock as mock
except ImportError:
    import mock


class TestCreateTempFile(unittest.TestCase):

    @mock.patch('os.remove')
    @mock.patch('os.write')
    @mock.patch('os.close')
    @mock.patch('tempfile.mkstemp')
    def test_create_temp_file(self, mock_mkstemp,
                              mock_close, mock_write, mock_remove):
        content = mock.Mock()
        content.encode.return_value = mock.sentinel
        mock_mkstemp.return_value = "fd", "path"
        with util.create_tempfile(content) as result:
            self.assertEqual(result, "path")
        mock_mkstemp.assert_called_once_with()
        mock_write.assert_called_once_with(
            "fd", content.encode.return_value)
        mock_close.assert_called_once_with("fd")
        mock_remove.assert_called_once_with("path")
