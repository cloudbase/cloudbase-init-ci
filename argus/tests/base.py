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

import types
import unittest

import six


class BaseTestCase(unittest.TestCase):
    """
    Extends unittest.TestCase by adding two member variables to instances,
    backend and introspection.
    """

    def __init__(self, backend, introspection, *args, **kwargs):
        super(BaseTestCase, self).__init__(*args, **kwargs)
        self.backend = backend
        self.introspection = introspection


class ScenarioMeta(type):
    def __new__(mcs, name, bases, attrs):
        cls = super(ScenarioMeta, mcs).__new__(mcs, name, bases, attrs)
        test_loader = unittest.TestLoader()
        if not cls.test_classes:
            return cls
        for test_class in cls.test_classes:
            test_names = test_loader.getTestCaseNames(test_class)
            for test_name in test_names:

                def delegator(self, class_name=test_class,
                              test_name=test_name):
                    getattr(class_name(self.backend, self.introspection,
                                       test_name), test_name)()

                if hasattr(cls, test_name):
                    test_name = 'test_%s_%s' % (test_class.__name__,
                                                test_name)

                setattr(
                    cls, test_name, types.FunctionType(
                        delegator.func_code, delegator.func_globals,
                        test_name, delegator.func_defaults))
        return cls


@six.add_metaclass(ScenarioMeta)
class BaseScenario(unittest.TestCase):
    """Test case which sets up an instance and prepares it using a recipe"""

    backend_type = None
    introspection_type = None
    recipe_type = None
    test_classes = None

    backend = None
    introspection = None
    recipe = None

    @classmethod
    def setUpClass(cls):
        cls.backend = cls.backend_type()
        cls.backend.setup_instance()

        cls.recipe = cls.recipe_type(cls.backend)
        cls.recipe.prepare()

        cls.introspection = cls.introspection_type(cls.backend.remote_client)

    @classmethod
    def tearDownClass(cls):
        cls.backend.cleanup()
