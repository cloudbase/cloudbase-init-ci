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
import time

from heatclient import exc
import six

from argus.backends import base
from argus.backends.heat import client
from argus.backends.tempest import manager as api_manager
from argus.backends import windows
from argus import config as argus_config
from argus import exceptions
from argus import util

CONFIG = argus_config.CONFIG

OS_NOVA_RESOURCE = 'OS::Nova::Server'
OS_NEUTRON_FLOATING_IP = "OS::Neutron::FloatingIP"
RESOURCE_COMPLETED_STATUS = "CREATE_COMPLETE"
RESOURCE_DELETED_STATUS = "DELETE_CREATE"
HEAT_RESOURCE_LIMIT = 10
HEAT_RESOURCE_TIMEOUT = 0.5

RETRY_COUNT = 50
RETRY_DELAY = 10


# pylint: disable=abstract-method
@six.add_metaclass(abc.ABCMeta)
class BaseHeatBackend(base.CloudBackend):
    """A back-end which uses Heat as the driving core."""

    def __init__(self, name=None, userdata=None, metadata=None,
                 availability_zone=None):
        super(BaseHeatBackend, self).__init__(
            name=name, userdata=userdata, metadata=metadata,
            availability_zone=availability_zone)

        self._manager = api_manager.APIManager()
        self._heat_client = client.heat_client(
            self._manager.primary_credentials())
        self._keypair = None

    @staticmethod
    def _build_template(instance_name, key,
                        image_name, flavor_name, user_data,
                        floating_network_id, private_net_id):
        return {
            u'heat_template_version': u'2013-05-23',
            u'description': u'argus',
            u'resources': {
                u'server_floating_ip': {
                    u'type': u'OS::Neutron::FloatingIP',
                    u'properties': {
                        u'floating_network_id': floating_network_id,
                        u'port_id': {u'get_resource': u'server_port'}
                    }
                },
                instance_name: {
                    u'type': u'OS::Nova::Server',
                    u'properties': {
                        u'key_name': key,
                        u'image': image_name,
                        u'flavor': flavor_name,
                        u'user_data_format': 'RAW',
                        u'user_data': user_data,
                        u'networks': [
                            {u'port': {u'get_resource': u'server_port'}}
                        ]
                    }
                },
                u'server_port': {
                    u'type': u'OS::Neutron::Port',
                    u'properties': {
                        u'network_id': private_net_id,
                        u'security_groups': [
                            {u'get_resource': u'server_security_group'}
                        ]
                    }
                },
                u'server_security_group': {
                    u'type': u'OS::Neutron::SecurityGroup',
                    u'properties': {
                        u'rules': [
                            {u'remote_ip_prefix': u'0.0.0.0/0',
                             u'port_range_max': 5986,
                             u'port_range_min': 5986,
                             u'protocol': u'tcp'},
                            {u'remote_ip_prefix': u'0.0.0.0/0',
                             u'port_range_max': 5985,
                             u'port_range_min': 5985,
                             u'protocol': u'tcp'},
                            {u'remote_ip_prefix': u'0.0.0.0/0',
                             u'port_range_max': 3389,
                             u'port_range_min': 3389,
                             u'protocol': u'tcp'},
                            {u'remote_ip_prefix': u'0.0.0.0/0',
                             u'port_range_max': 22,
                             u'port_range_min': 22,
                             u'protocol': u'tcp'}
                        ],
                        u'description': u'Add security group rules for server',
                        u'name': u'security-group'}
                }
            }
        }

    def _configure_networking(self, credentials):
        subnet_id = credentials.subnet["id"]
        self._manager.subnets_client.update_subnet(
            subnet_id,
            dns_nameservers=CONFIG.argus.dns_nameservers)

    def setup_instance(self):
        super(BaseHeatBackend, self).setup_instance()

        # Get the image and the flavor name
        image_name = self._manager.image_client.get_image_meta(
            CONFIG.openstack.image_ref)['name']
        flavor_name = self._manager.flavors_client.show_flavor(
            CONFIG.openstack.flavor_ref)['flavor']['name']
        self._keypair = self._manager.create_keypair(
            name=self.__class__.__name__)

        # Get network info.
        credentials = self._manager.primary_credentials()
        self._configure_networking(credentials)
        gateway = credentials.router['external_gateway_info']
        floating_network_id = gateway['network_id']
        private_net_id = credentials.network['id']

        template = self._build_template(
            self._name, self._keypair.name,
            image_name, flavor_name, self.userdata,
            floating_network_id, private_net_id)
        fields = {
            'stack_name': self._name,
            'disable_rollback': True,
            'parameters': {},
            'template': template,
            'files': {},
            'environment': {},
        }

        self._heat_client.stacks.create(**fields)

    def cleanup(self):
        if self._keypair:
            self._keypair.destroy()

        # if no stack was created
        if not six.functools.reduce(lambda a, b: a + 1,
                                    self._heat_client.stacks.list(), 0):
            return
        try:
            self._delete_floating_ip()
            self._heat_client.stacks.delete(stack_id=self._name)
            self._wait_stacks()
        finally:
            self._manager.cleanup_credentials()

    def _get_stacks(self):
        """Return the number of heat stacks."""
        iterator = self._heat_client.stacks.list()
        return six.functools.reduce(lambda acc, e: acc + 1, iterator, 0)

    def _wait_stacks(self, retry_count=RETRY_COUNT,
                     retry_delay=RETRY_DELAY):
        """We are going to wait until all stacks are deleted."""
        stacks = self._get_stacks()
        retry_count = stacks * retry_count
        retry_delay = stacks * retry_delay
        while retry_count > 0:
            if not self._get_stacks():
                return
            else:
                retry_count -= 1
            time.sleep(retry_delay)
        raise exceptions.ArgusHeatTeardown(
            "All stacks failed to be deleted in time!")

    def _delete_floating_ip(self):
        # The floating IP in the new version is deleted when the
        # stack is deleted
        # In the new scenarios this code is not called but I keep
        # it to preserve the logic if more complicated back-ends are
        # needed
        self._manager.floating_ips_client.delete_floating_ip(
            self._floating_ip_resource['id'])
        try:
            self._search_resource_until_status(OS_NEUTRON_FLOATING_IP,
                                               status=RESOURCE_DELETED_STATUS)
        except exceptions.ArgusError:
            # Can't find it, just quit.
            return

    def _search_resource_until_status(self, resource_name,
                                      limit=HEAT_RESOURCE_LIMIT,
                                      status=RESOURCE_COMPLETED_STATUS):
        fields = {
            'stack_id': self._name,
            'nested_depth': 1,
        }
        while limit > 0:
            try:
                resources = self._heat_client.resources.list(**fields)
            except exc.HTTPNotFound:
                raise exceptions.ArgusError('Stack not found: %s' % self._name)
            else:
                for resource in resources:
                    if resource.resource_type == resource_name:
                        # Found the resource we were needing
                        if resource.resource_status == status:
                            return resource.physical_resource_id
                        else:
                            limit -= 1
                            time.sleep(HEAT_RESOURCE_TIMEOUT)
                            break
                else:
                    break

        raise exceptions.ArgusError("No resource %s found with name %s"
                                    % (resource_name, self._name))

    @util.cached_property
    def _internal_id(self):
        return self._search_resource_until_status(OS_NOVA_RESOURCE)

    def internal_instance_id(self):
        """Get the underlying instance ID.

        Gets the instance ID depending on the internals of the back-end.
        """
        return self._internal_id

    @util.cached_property
    def _floating_ip_resource(self):
        resource = self._search_resource_until_status(OS_NEUTRON_FLOATING_IP)
        floating_ip = self._manager.floating_ips_client.show_floating_ip(
            resource)
        return floating_ip['floating_ip']

    def floating_ip(self):
        """Get the underlying floating IP."""
        return self._floating_ip_resource['ip']

    def instance_output(self, limit=api_manager.OUTPUT_SIZE):
        """Get the console output, sent from the instance."""
        return self._manager.instance_output(
            self.internal_instance_id(),
            limit)

    def reboot_instance(self):
        """Reboot the underlying instance."""
        return self._manager.reboot_instance(self.internal_instance_id())

    def instance_password(self):
        """Get the underlying instance password, if any."""
        return self._manager.instance_password(
            self.internal_instance_id(),
            self._keypair)

    def private_key(self):
        """Get the underlying private key."""
        return self._keypair.private_key

    def public_key(self):
        """Get the underlying public key."""
        return self._keypair.public_key

    def instance_server(self):
        """Get the instance server object."""
        return self._manager.instance_server(self.internal_instance_id())

    def get_image_by_ref(self):
        """Get the image object by its reference id."""
        return self._manager.compute_images_client.show_image(
            CONFIG.openstack.image_ref)

    def get_mtu(self):
        return self._manager.get_mtu()


class WindowsHeatBackend(windows.WindowsBackendMixin, BaseHeatBackend):
    """Heat back-end tailored to work with Windows platforms."""
