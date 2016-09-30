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

import abc

import six


@six.add_metaclass(abc.ABCMeta)
class BaseInstanceIntrospection(object):
    """Generic utility class for introspecting an instance.

    :param conf:
        The configuration object used by argus.
    :param remote_client:
        A client which can be used by argus.
        This needs to be an instance of
        :class:`argus.remote_client.BaseClient`.
    """

    def __init__(self, conf, remote_client):
        self.remote_client = remote_client
        self._conf = conf
