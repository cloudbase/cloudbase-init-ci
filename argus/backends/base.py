import abc

import six


@six.add_metaclass(abc.ABCMeta)
class BaseBackend(object):

    @abc.abstractmethod
    def create_instance(self):
        pass
