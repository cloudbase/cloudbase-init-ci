import abc

import six


@six.add_metaclass(abc.ABCMeta)
class BaseBackend(object):

    @abc.abstractmethod
    def setup_instance(self):
        """Called by setUpClass to setup an instance"""
