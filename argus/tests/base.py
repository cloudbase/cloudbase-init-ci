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

import unittest


class BaseTestCase(unittest.TestCase):
    """Test case parametrized with a back-end and an introspection object."""

    def __init__(self, backend, recipe, introspection, *args, **kwargs):
        super(BaseTestCase, self).__init__(*args, **kwargs)
        self._backend = backend
        self._recipe = recipe
        self._introspection = introspection
