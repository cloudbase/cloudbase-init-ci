from argus.backends import tempest_backend as tempest_backend
from argus.introspection.cloud import windows
from argus.recipes.cloud import windows as windows_recipes
from argus.tests import base
from argus.tests.cloud.windows import test_smoke


class TempestScenario(base.BaseScenario):
    backend_type = tempest_backend.BaseWindowsScenario
    recipe_type = windows_recipes.CloudbaseinitRecipe
    introspection_type = windows.InstanceIntrospection

    test_classes = [test_smoke.TestSmoke]
