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
class BaseBackend(object):
    """Class for managing instances

    The *backend* is used for building and managing an underlying
    instance, being it an OpenStack instance, OpenNebula instance
    or a containerized OS.

    :param conf:
        A configuration object, which holds argus related info.
    :param name:
        The name of the instance that will be created.
    :param userdata:
        If any, the userdata which will be available in the
        instance to the corresponding cloud initialization
        service.
    :param metadata:
        If any, the metadata which should be available in the
        instance to the correpsonding cloud initialization
        service.
    """
    def __init__(self, conf, name=None, userdata=None, metadata=None,
                 availability_zone=None):
        self._name = name
        self._userdata = userdata
        self._metadata = metadata
        self._conf = conf
        self._availability_zone = availability_zone

    @abc.abstractmethod
    def setup_instance(self):
        """Setup an underlying instance."""

    @abc.abstractmethod
    def cleanup(self):
        """Destroy and cleanup the relevant resources created by setup_instance."""
