import mock

from argus.tests import base
from argus.tests.tests import mock_tests


class TestScenario(base.BaseScenario):
    backend_type = mock.MagicMock()
    recipe_type = mock.MagicMock()
    introspection_type = mock.MagicMock()

    test_classes = [mock_tests.RandomTest, mock_tests.NamespaceCollisionTest]
