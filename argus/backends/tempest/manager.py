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

from argus import util

with util.restore_excepthook():
    from tempest import clients
    from tempest.common import credentials


class APIManager(object):
    """Manager which uses tempest modules for interacting with the API."""

    def __init__(self):
        self.isolated_creds = credentials.get_isolated_credentials(
            self.__class__.__name__, network_resources={})
        primary_credentials = self.primary_credentials()
        self._manager = clients.Manager(credentials=primary_credentials)

        # Underlying clients.
        self.flavors_client = self._manager.flavors_client
        self.floating_ips_client = self._manager.floating_ips_client

        # Glance image client v1
        self.image_client = self._manager.image_client

        # Compute image client
        self.images_client = self._manager.images_client
        self.keypairs_client = self._manager.keypairs_client

        # Nova security groups client
        self.security_groups_client = self._manager.security_groups_client
        self.security_group_rules_client = \
            self._manager.security_group_rules_client

        self.servers_client = self._manager.servers_client
        self.volumes_client = self._manager.volumes_client
        self.snapshots_client = self._manager.snapshots_client
        self.interface_client = self._manager.interfaces_client

        # Neutron network client
        self.network_client = self._manager.network_client

        # Heat client
        self.orchestration_client = self._manager.orchestration_client

    def cleanup_credentials(self):
        """Cleanup any credentials created during the initialization."""
        self.isolated_creds.clear_isolated_creds()

    def primary_credentials(self):
        return self.isolated_creds.get_primary_creds()

    def create_keypair(self, name):
        """Create a new keypair with the given name

        This will return a new :class:`Keypair` object,
        which provides access to the public, private key pair,
        as well as a method for destroying the keypair if needed.
        """

        keypair = self.keypairs_client.create_keypair(
            name=name + "-key")['keypair']
        return Keypair(public_key=keypair['public_key'],
                       private_key=keypair['private_key'],
                       name=keypair['name'],
                       manager=self)


class Keypair(object):
    """A keypair container."""

    def __init__(self, name, public_key, private_key, manager):
        self.name = name
        self.public_key = public_key
        self.private_key = private_key
        self._manager = manager

    def destroy(self):
        """Destroy the current keypair."""
        self._manager.keypairs_client.delete_keypair(self.name)
