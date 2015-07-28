from argus.backends.tempest import TempestBackend


def get_backend(_type):
    """Factory method for creating instances of BaseBackend.

    :param str _type: the desired backend type
    :returns: instance of _type or None if _type doesn't exist
    :rtype: _type
    """
    if _type is 'tempest':
        return TempestBackend()
    raise TypeError('Invalid backend type "%s"' % _type)
