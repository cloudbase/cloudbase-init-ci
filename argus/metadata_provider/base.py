# Copyright 2017 Cloudbase Solutions Srl
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

"""
Contains base Metadata Providers.
"""

import abc
import six


from argus import config as argus_config
from argus import log as argus_log
from argus import util


LOG = argus_log.LOG
CONFIG = argus_config.CONFIG


@six.add_metaclass(abc.ABCMeta)
class BaseMetadataProviderMixin(object):
    """Base class for a MetadataProviderMixin."""

    # pylint: disable=no-member
    @abc.abstractmethod
    def get_url(self, service_type):
        """Return the metadata url."""
        pass

    @abc.abstractmethod
    def get_password(self):
        """Get the encrypted password."""
        pass

    @abc.abstractmethod
    def get_ssh_pubkeys(self):
        """Get a dictionary with ssh public keys."""
        pass

    @abc.abstractmethod
    def get_ssh_privatekeys(self):
        """Get a dictionary with ssh private keys."""
        pass

    @abc.abstractmethod
    def set_ssh_pubkeys(self, public_key):
        """Set a dictionary with ssh public keys."""
        pass

    @abc.abstractmethod
    def delete_all_data(self):
        """Clean up all metadata."""
        pass

    def prepare_metadata(self, service_type):
        """Prepare the metadata."""
        self.setup_metadata(service_type)


@six.add_metaclass(abc.ABCMeta)
class BaseMetadataProvider(object):
    """Base class for Metadata Providers."""

    def __init__(self, backend, recipe):
        """Initialize a new Metadata Provider.

        :param backend: The Instance backend.
        :param recipe: The recipe used.
        """
        self._backend = backend
        self._recipe = recipe
        self._service_type = util.HTTP_SERVICE

    def setup_metadata(self, service_type):
        """Set up the required metadata."""
        if not self._service_type:
            self._service_type = service_type
