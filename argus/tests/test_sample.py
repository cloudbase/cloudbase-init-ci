import mock

from argus.tests import base


class TestScenario(base.BaseScenario):
    backend_type = mock.MagicMock()
    recipe_type = mock.MagicMock()
    introspection_type = mock.MagicMock()

    test_classes = [base.RandomTest]

