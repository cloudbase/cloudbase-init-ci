import mock

from argus.backends import tempest_backend as tempest_backend
from argus.introspection.cloud import windows
from argus.recipes.cloud import windows as windows_recipes
from argus.tests import base
from argus.tests.tests import mock_tests


class TestScenario(base.BaseScenario):
    backend_type = mock.MagicMock()
    recipe_type = mock.MagicMock()
    introspection_type = mock.MagicMock()

    test_classes = [mock_tests.RandomTest, mock_tests.NamespaceCollisionTest]


class TempestScenario(base.BaseScenario):
    backend_type = tempest_backend.BaseWindowsScenario
    recipe_type = windows_recipes.CloudbaseinitRecipe
    introspection_type = windows.InstanceIntrospection

    test_classes = [mock_tests.RandomTest, mock_tests.NamespaceCollisionTest]
