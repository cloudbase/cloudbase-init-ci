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

import contextlib
import os
import tempfile

from argus import util

with util.restore_excepthook():
    from tempest import clients
    from tempest.common import credentials
    from tempest.common import waiters


OUTPUT_STATUS_OK = 200
OUTPUT_SIZE = 128
OUTPUT_EPSILON = int(OUTPUT_SIZE / 10)
LOG = util.get_logger()


@contextlib.contextmanager
def _create_tempfile(content):
    fd, path = tempfile.mkstemp()
    os.write(fd, content.encode())
    os.close(fd)
    try:
        yield path
    finally:
        os.remove(path)


class APIManager(object):
    """Manager which uses tempest modules for interacting with the OpenStack API."""

    def __init__(self):
        self.isolated_creds = credentials.get_credentials_provider(
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
        self.availability_zone_client = self._manager.availability_zone_client

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
        self.networks_client = self._manager.networks_client

        # Heat client
        self.orchestration_client = self._manager.orchestration_client

    def cleanup_credentials(self):
        """Cleanup any credentials created during the initialization."""
        self.isolated_creds.clear_creds()

    def primary_credentials(self):
        """Get the underlying :class:`tempest.common.isolated_creds.IsolatedCreds`."""
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

    def reboot_instance(self, instance_id):
        """Reboot the instance with the given id."""
        self.servers_client.reboot_server(
            server_id=instance_id, reboot_type='soft')
        waiters.wait_for_server_status(
            self.servers_client,
            instance_id, 'ACTIVE')

    def instance_password(self, instance_id, keypair):
        """Get the password posted by the given instance.

        :param instance_id:
            The id of the instance for which the password will
            be returned.
        :param keypair:
            A keypair whose private key can be used to decrypt
            the password.
        """
        encoded_password = self.servers_client.get_password(
            instance_id)
        with _create_tempfile(keypair.private_key) as tmp:
            return util.decrypt_password(
                private_key=tmp,
                password=encoded_password['password'])

    def _instance_output(self, instance_id, limit):
        ret = self.servers_client.get_console_output(
            instance_id, limit)
        return ret.response, ret.data

    def instance_output(self, instance_id, limit):
        """Get the console output, sent from the instance.

        :param instance_id:
            The id of the instance for which the output will
            be retrieved.
        :param limit:
            Number of lines to fetch from the end of console log.
        """
        content = None
        while True:
            resp, content = self._instance_output(instance_id, limit)
            if resp.status != OUTPUT_STATUS_OK:
                LOG.error("Couldn't get console output <%d>.", resp.status)
                return

            if len(content.splitlines()) >= (limit - OUTPUT_EPSILON):
                limit *= 2
            else:
                break
        return content

    def instance_server(self, instance_id):
        """Get more details about the given instance id."""
        return self.servers_client.show_server(instance_id)


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
