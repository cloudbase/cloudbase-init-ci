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
import types
import unittest

import six

from argus import util


LOG = util.get_logger()


def _build_new_function(func, name):
    code = six.get_function_code(func)
    func_globals = six.get_function_globals(func)
    func_defaults = six.get_function_defaults(func)
    func_closure = six.get_function_closure(func)
    return types.FunctionType(code, func_globals,
                              name, func_defaults,
                              func_closure)


class ScenarioMeta(type):
    """Metaclass for merging test methods from a given list of test cases."""

    def __new__(mcs, name, bases, attrs):
        cls = super(ScenarioMeta, mcs).__new__(mcs, name, bases, attrs)
        test_loader = unittest.TestLoader()
        if not cls.is_final():
            LOG.warning("Class %s is not a final class", cls)
            return cls

        cls.conf = util.get_config()
        for test_class in cls.test_classes:
            test_names = test_loader.getTestCaseNames(test_class)
            for test_name in test_names:

                # skip tests that have
                # required_service_type != cls.service_type
                test_obj = getattr(test_class, test_name)
                if hasattr(test_obj, 'required_service_type'):
                    if test_obj.required_service_type != cls.service_type:
                        continue

                def delegator(self, class_name=test_class,
                              test_name=test_name):
                    getattr(class_name(cls.conf, self.backend, self.recipe,
                                       self.introspection, test_name),
                            test_name)()

                if hasattr(cls, test_name):
                    test_name = 'test_%s_%s' % (test_class.__name__,
                                                test_name)

                # Create a new function from the delegator with the
                # correct name, since tools such as nose test runner,
                # will use func.func_name, which will be delegator otherwise.
                new_func = _build_new_function(delegator, test_name)
                setattr(cls, test_name, new_func)

        return cls

    def is_final(cls):
        """Check current class if is final.

        Checks if the class is final and if it has all the attributes set.
        """
        return all(item for item in (cls.backend_type, cls.introspection_type,
                                     cls.recipe_type, cls.test_classes))


@six.add_metaclass(ScenarioMeta)
class BaseScenario(unittest.TestCase):
    """Scenario which sets up an instance and prepares it using a recipe."""

    backend_type = None
    """The backend class which will be used."""

    introspection_type = None
    """The introspection class which will be used."""

    recipe_type = None
    """The recipe class which will be used."""

    test_classes = None
    """A tuple of test classes which will be merged into the scenario."""

    userdata = None
    """The userdata that will be available in the instance

    This can be anything as long as the underlying backend supports it.
    """

    metadata = None
    """The metadata that will be available in the instance.

    This can be anything as long as the underlying backend supports it.
    """

    availability_zone = None
    backend = None
    introspection = None
    recipe = None
    conf = None

    @classmethod
    def setUpClass(cls):
        """Prepare the scenario for running

        This means that the backend will be instantiated and an
        instance will be created and prepared. After the preparation
        is finished, the tests can run and can introspect the instance
        to check what they are supposed to be checking.
        """
        # pylint: disable=not-callable
        # Pylint is not aware that the attrs are reassigned in other modules,
        # so we're just disabling the errors for now.

        LOG.info("Running scenario %s", cls.__name__)
        # Create output_directory when given
        if cls.conf.argus.output_directory:
            try:
                os.mkdir(cls.conf.argus.output_directory)
            except OSError:
                LOG.warning("Could not create the output directory.")

        try:
            cls.backend = cls.backend_type(cls.conf, cls.__name__,
                                           cls.userdata, cls.metadata,
                                           cls.availability_zone)
            cls.backend.setup_instance()

            cls.prepare_instance()

            cls.introspection = cls.introspection_type(
                cls.conf, cls.backend.remote_client)
        except Exception as exc:
            LOG.exception("Building scenario %r failed with %s",
                          cls.__name__, exc)
            cls.tearDownClass()
            raise

    @classmethod
    def prepare_instance(cls):
        """Prepare the underlying instance."""
        # pylint: disable=not-callable
        # Pylint is not aware that the attrs are reassigned in other modules,
        # so we're just disabling the errors for now.
        cls.recipe = cls.recipe_type(cls.conf, cls.backend)
        cls.prepare_recipe()
        cls.backend.save_instance_output()

    @classmethod
    def prepare_recipe(cls):
        """Call the *prepare* method of the underlying recipe

        This method can be overwritten in the case the recipe's
        *prepare* method needs special arguments passed down.
        """
        return cls.recipe.prepare()

    @classmethod
    def tearDownClass(cls):
        """Cleanup this scenario

        This usually means that any resource that was created in
        :meth:`setUpClass` needs to be destroyed here.
        """
        if cls.backend:
            cls.backend.cleanup()
