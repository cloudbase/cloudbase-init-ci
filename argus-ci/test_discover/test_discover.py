# Copyright 2014 Cloudbase-init
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
import sys

if sys.version_info >= (2, 7):
    import unittest
else:
    import unittest2 as unittest


# TODO(cpopa): make it configurable?
TEST_DIR = './argus-ci/tests'


def load_tests(loader, tests, pattern):
    suite = unittest.TestSuite()
    base_path = os.path.split(os.path.dirname(os.path.abspath(__file__)))[0]
    base_path = os.path.split(base_path)[0]
    if not pattern:
        suite.addTests(loader.discover(TEST_DIR, top_level_dir=base_path))
    else:
        suite.addTests(loader.discover(TEST_DIR, pattern=pattern,
                                       top_level_dir=base_path))
    return suite
