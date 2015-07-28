from argus.backends import base


class TempestBackend(base.BaseBackend):

    def setup_instance(self):
        """Sets up an Openstack instance"""
