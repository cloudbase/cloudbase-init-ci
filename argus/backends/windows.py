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

from argus.client import windows
from argus import config as argus_config
from argus import util
from argus.metadata_provider import base as base_metadata_provider

CONFIG = argus_config.CONFIG


class WindowsBackendMixin(object):
    """Mixin back-end tailored for interacting with Windows."""

    # pylint: disable=unused-argument
    def get_remote_client(self, username=None, password=None,
                          protocol='http', **kwargs):
        """Uses : class:`argus.util.WinRemoteClient` as underlying client."""

        if username is None:
            username = CONFIG.openstack.image_username
        if password is None:
            password = CONFIG.openstack.image_password
        return windows.WinRemoteClient(self.floating_ip(),
                                       username, password,
                                       transport_protocol=protocol)

    remote_client = util.cached_property(get_remote_client, 'remote_client')


class BaseMetadataProviderMixin(
        base_metadata_provider.BaseMetadataProviderMixin):
    """Backend Metadata Provider mixin."""

    def get_url(self, service_type):
        """Return the metadata url."""
        return util.DEFAULT_METADATA_URL.get(service_type)

    def get_password(self):
        """Get the encrypted password."""
        return self.instance_password()

    def get_ssh_pubkeys(self):
        """Get a dictionary with ssh public keys."""
        return {0: self.public_key()}

    def get_ssh_privatekeys(self):
        """Get a dictionary with ssh private keys."""
        return {0: self.private_key()}

    def set_ssh_pubkeys(self, public_key):
        """Set a dictionary with ssh public keys."""
        raise NotImplementedError()

    def delete_all_data(self):
        """Clean up all metadata."""
        pass

    def prepare_metadata(self, service_type):
        """Prepare the metadata."""
        pass
