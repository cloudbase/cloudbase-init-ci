from argus.tests import base


class RandomTest(base.BaseTestCase):
    def test_success(self):
        self.assertTrue(True)

    def test_failure(self):
        self.assertTrue(False)


class NamespaceCollisionTest(RandomTest):
    pass
