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

from argus.backends import factory as backends_factory


class BaseTestCase(unittest.TestCase):
    """Test case which sets up an instance and prepares it using a recipe"""

    backend_type = None
    introspection_type = None
    recipe_type = None

    backend = None
    introspection = None
    recipe = None

    @classmethod
    def setUpClass(cls):
        cls.backend = backends_factory.get_backend(cls.backend_type)
        cls.backend.setup_instance()

        # TODO (ionuthulub) setup introspection
        # TODO (ionuthulub) setup the recipe

        cls.recipe.prepare()

    @classmethod
    def tearDownClass(cls):
        cls.backend.cleanup()
