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
Contains Arestor Metadata Providers.
"""

import json

from arestor.client import arestor_client

from argus import config as argus_config
from argus import log as argus_log
from argus import util
from argus.metadata_provider import base


LOG = argus_log.LOG
CONFIG = argus_config.CONFIG


class ArestorMetadataProviderMixin(base.BaseMetadataProviderMixin):
    """Mixin for Arestor Metadata Provider."""

    # pylint: disable=no-member
    def get_url(self, service_type):
        """Return the metadata url."""
        return self._arestor_client.get_url()

    def get_password(self):
        """Get the encrypted password."""
        return self._arestor_client.get_password()

    def get_ssh_pubkeys(self):
        """Get a dictionary with ssh public keys."""
        return self._arestor_client.get_ssh_pubkeys()

    def get_ssh_privatekeys(self):
        """Get a dictionary with ssh private keys."""
        return {0: self._backend.private_key()}

    def set_ssh_pubkeys(self, public_key):
        """Get a dictionary with ssh public keys."""
        return self._arestor_client.set_ssh_pubkeys(public_key)

    def delete_all_data(self):
        """Clean up all metadata."""
        self._arestor_client.delete_all_data()


class ArestorMetadataProvider(base.BaseMetadataProvider,
                              ArestorMetadataProviderMixin):
    """Arestor Metadata Provider."""

    def __init__(self, backend, recipe):
        """Initialize a new Metadata Provider.

        :param backend: The Instance backend.
        :param recipe: The recipe used.
        """
        super(ArestorMetadataProvider, self).__init__(backend, recipe)
        self._arestor_client = arestor_client.ArestorClient(
            base_url=CONFIG.arestor.base_url,
            api_key=CONFIG.arestor.api_key,
            secret=CONFIG.arestor.secret,
            client_id="instance-{}".format(
                backend.instance_server().get('name')))

    @staticmethod
    def _get_namespace(service_type):
        """Return the metadata namespace."""
        # NOTE(mmicu): for Openstack we have the service_type set to http
        return service_type if service_type != "http" else "openstack"

    def setup_metadata(self, service_type):
        """Set up the required metadata."""
        super(ArestorMetadataProvider, self).setup_metadata(service_type)
        namespace = self._get_namespace(service_type)
        instance_server = self._backend.instance_server()
        name = instance_server.get("name")

        self._arestor_client.set_namespace(namespace)
        self._arestor_client.set_name(name)

        self._arestor_client.set_user_data(self._backend.userdata)
        self._arestor_client.set_metadata(json.dumps(self._backend.metadata))

        self._arestor_client.set_project_id("project-{}".format(name))
        self._arestor_client.set_launch_index("0")
        self._arestor_client.set_availability_zone(
            instance_server.get("OS-EXT-AZ:availability_zone",
                                "az-{}".format(name)))
        self._arestor_client.set_random_seed("random-seed-{}".format(name))
        self._arestor_client.set_uuid(instance_server.get("id"))
        self._arestor_client.set_uuid(name.lower())

        argus_x509_cert = [
            {
                "name": "argus_x509_cert",
                "type": "x509",
                "data": util.get_certificate()
            },
        ]
        argus_ssh_pubkeys = {
            "0": self._backend.public_key()
        }

        self._arestor_client.set_ssh_pubkeys(argus_ssh_pubkeys)
        self._arestor_client.set_keys(argus_x509_cert)
