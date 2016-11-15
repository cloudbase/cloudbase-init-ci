# Copyright 2016 Cloudbase Solutions Srl
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

# pylint: disable=no-value-for-parameter, protected-access, arguments-differ
# pylint: disable=unused-argument

import unittest

from argus.backends.heat import heat_backend
from argus import exceptions
from heatclient import exc

try:
    import unittest.mock as mock
except ImportError:
    import mock


class FakeBaseHeatBackend(heat_backend.BaseHeatBackend):

    def __inti__(self):
        super(FakeBaseHeatBackend, self).__init__()

    def get_remote_client(self):
        return mock.sentinel

    def remote_client(self):
        return mock.sentinel


class TestBaseHeatBackend(unittest.TestCase):

    @mock.patch('argus.backends.heat.client.heat_client')
    @mock.patch('argus.backends.tempest.manager.APIManager')
    def setUp(self, mock_api_manager, mock_heat_client):
        self._base_heat_backend = FakeBaseHeatBackend()

    def test_build_template(self):
        instance_name = mock.sentinel
        key = mock.sentinel
        image_name = mock.sentinel
        flavor_name = mock.sentinel
        user_data = mock.sentinel
        floating_network_id = mock.sentinel
        private_net_id = mock.sentinel
        expected_template = {
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
        result = self._base_heat_backend._build_template(
            instance_name, key, image_name, flavor_name,
            user_data, floating_network_id, private_net_id)
        self.assertEqual(result, expected_template)

    @mock.patch('argus.config.CONFIG.argus')
    def test_configure_network(self, mock_config):
        mock_config.dns_nameservers = mock.sentinel
        mock_credentials = mock.Mock()
        mock_credentials.subnet = {"id": mock.sentinel}
        (self._base_heat_backend._manager.subnets_client.
         update_subnet) = mock.Mock(return_value=mock.sentinel)
        self._base_heat_backend._configure_networking(mock_credentials)
        (self._base_heat_backend._manager.subnets_client.update_subnet.
         assert_called_once_with(
             mock_credentials.subnet["id"],
             dns_nameservers=mock_config.dns_nameservers))

    @mock.patch('argus.backends.base.CloudBackend.setup_instance')
    @mock.patch('argus.config.CONFIG.openstack')
    def test_setup_instance(self, mock_config, mock_super):
        mock_config.image_ref = mock.sentinel
        mock_config.flavor_ref = mock.sentinel
        mock_manager = mock.Mock()
        mock_manager.image_client = mock.Mock()
        mock_manager.image_client.get_image_meta.return_value = {
            "name": mock.sentinel
        }
        mock_manager.flavors_client = mock.Mock()
        mock_manager.flavors_client.show_flavor.return_value = {
            "flavor": {
                "name": mock.sentinel
            }
        }
        mock_manager.create_keypair = mock.Mock()
        mock_manager.create_keypair.return_value = mock.sentinel
        mock_credentials = mock.Mock()
        mock_credentials.router = {
            'external_gateway_info': {
                'network_id': mock.sentinel
            }
        }
        mock_credentials.network = {
            "id": mock.sentinel
        }
        self._base_heat_backend._build_template = mock.Mock()
        self._base_heat_backend._build_template.return_value = mock.sentinel
        self._base_heat_backend._heat_client.stacks.create = mock.Mock()
        mock_manager.primary_credentials.return_value = mock_credentials
        self._base_heat_backend._configure_networking = mock.Mock()
        self._base_heat_backend._manager = mock_manager
        self._base_heat_backend.setup_instance()

        (mock_manager.image_client.get_image_meta.
         assert_called_once_with(mock_config.image_ref))
        (mock_manager.flavors_client.show_flavor.assert_called_once_with(
            mock_config.flavor_ref))
        (mock_manager.create_keypair.assert_called_once_with(
            name=self._base_heat_backend.__class__.__name__))
        (mock_manager.primary_credentials.assert_called_once_with())
        (self._base_heat_backend._configure_networking.assert_called_once_with(
            mock_credentials))
        self._base_heat_backend._build_template.assert_called_once_with(
            self._base_heat_backend._name,
            self._base_heat_backend._keypair.name,
            mock_config.image_ref, mock_config.flavor_ref,
            self._base_heat_backend.userdata,
            mock.sentinel, mock.sentinel)
        fields = {
            'stack_name': self._base_heat_backend._name,
            'disable_rollback': True,
            'parameters': {},
            'template': self._base_heat_backend._build_template.return_value,
            'files': {},
            'environment': {},
        }
        (self._base_heat_backend._heat_client.stacks.create.
         assert_called_once_with(**fields))

    def _test_cleanup(self, reduce_=True, fails=False):
        if self._base_heat_backend._keypair:
            self._base_heat_backend._keypair = mock.Mock()
            self._base_heat_backend._keypair.destroy = mock.Mock()

        self._base_heat_backend._heat_client.stacks.list = mock.Mock()
        if reduce_ is False:
            (self._base_heat_backend._heat_client.stacks.list.
             return_value) = []
        else:
            (self._base_heat_backend._heat_client.stacks.list.
             return_value) = [1]

        self._base_heat_backend._delete_floating_ip = mock.Mock()
        self._base_heat_backend._heat_client.stacks.delete = mock.Mock()
        if fails:
            (self._base_heat_backend._heat_client.stacks.delete.
             side_effect) = Exception
        self._base_heat_backend._wait_stacks = mock.Mock()
        self._base_heat_backend._manager.cleanup_credentials = mock.Mock()

        if fails:
            with self.assertRaises(Exception):
                result = self._base_heat_backend.cleanup()
        else:
            result = self._base_heat_backend.cleanup()

        if self._base_heat_backend._keypair:
            (self._base_heat_backend._keypair.destroy.
             assert_called_once_with())
        if reduce_ is False:
            self.assertEqual(result, None)
        else:
            (self._base_heat_backend._delete_floating_ip.
             assert_called_once_with())
            (self._base_heat_backend._heat_client.stacks.delete.
             assert_called_once_with(
                 stack_id=self._base_heat_backend._name))
            count = 1
            if fails:
                count = 0
            (self.assertEqual(self._base_heat_backend.
                              _wait_stacks.call_count, count))
            (self._base_heat_backend._manager.cleanup_credentials.
             assert_called_once_with())

    def test_cleanup_no_reduce_destroy_key(self):
        self._base_heat_backend._keypair = mock.sentinel
        self._test_cleanup(reduce_=False)

    def test_cleanup_success(self):
        self._base_heat_backend._keypair = None
        self._test_cleanup()

    def test_cleanup_fails(self):
        self._base_heat_backend._keypair = None
        self._test_cleanup(fails=True)

    def test_get_stacks(self):
        list_ = [1, 2, 3, 4, 5]
        self._base_heat_backend._heat_client.stacks.list = mock.Mock()
        (self._base_heat_backend._heat_client.stacks.list.
         return_value) = list_
        result = self._base_heat_backend._get_stacks()
        self.assertEqual(result, len(list_))

    def test_wait_stacks_fails(self):
        raised_exception = exceptions.ArgusHeatTeardown(
            "All stacks failed to be deleted in time!")
        self._base_heat_backend._get_stacks = mock.Mock()
        self._base_heat_backend._get_stacks.return_value = 0
        with self.assertRaises(exceptions.ArgusHeatTeardown) as ex:
            self._base_heat_backend._wait_stacks()
        self.assertEqual(ex.exception.message, str(raised_exception))

    @mock.patch("time.sleep", return_value=None)
    def test_wait_stacks(self, _):
        self._base_heat_backend._get_stacks = mock.Mock()
        self._base_heat_backend._get_stacks.side_effect = [1, 1, 0]
        result = self._base_heat_backend._wait_stacks(retry_delay=1,
                                                      retry_count=5)
        self.assertEqual(result, None)
        self.assertEqual(self._base_heat_backend._get_stacks.call_count, 3)

    def test_delete_floating_ip_fails(self):
        (self._base_heat_backend._manager.floating_ips_client.
         delete_floating_ip) = mock.Mock()
        self._base_heat_backend._floating_ip_resource = {"id": mock.sentinel}
        self._base_heat_backend._search_resource_until_status = mock.Mock()
        (self._base_heat_backend._search_resource_until_status.
         side_effect) = exceptions.ArgusError

        self._base_heat_backend._delete_floating_ip()

    def test_search_resoutce_until_status_http_error(self):
        self._base_heat_backend._name = "fake name"
        raised_exception = exceptions.ArgusError('Stack not found: %s' %
                                                 self._base_heat_backend._name)
        self._base_heat_backend._heat_client.resources.list = mock.Mock()
        (self._base_heat_backend._heat_client.resources.list.
         side_effect) = exc.HTTPNotFound()
        with self.assertRaises(exceptions.ArgusError) as ex:
            self._base_heat_backend._search_resource_until_status(
                mock.sentinel)
        self.assertEqual(ex.exception.message,
                         str(raised_exception))

    def test_search_resource_until_status_limit_exceded(self):
        resource_name = "fake resource"
        self._base_heat_backend._name = "fake name"
        raised_exception = exceptions.ArgusError(
            "No resource %s found with name %s"
            % (resource_name, self._base_heat_backend._name))
        self._base_heat_backend._name = "fake name"
        (self._base_heat_backend._heat_client.resources.list.
         side_effect) = raised_exception
        with self.assertRaises(exceptions.ArgusError) as ex:
            self._base_heat_backend._search_resource_until_status(
                resource_name, 0)
        self.assertEqual(ex.exception.message, str(raised_exception))

    def test_search_resource_until_status_success(self):
        resource_name = mock.sentinel
        status_completed = mock.sentinel
        mock_list = mock.Mock()
        mock_resource = mock.Mock()
        mock_resource.resource_type = resource_name
        mock_resource.resource_status = status_completed
        mock_resource.physical_resource_id = mock.sentinel
        mock_list.return_value = [mock_resource]
        self._base_heat_backend._heat_client.resources.list = mock_list
        result = self._base_heat_backend._search_resource_until_status(
            resource_name, status=status_completed)
        self.assertEqual(result, mock_resource.physical_resource_id)

    @mock.patch("time.sleep", return_value=None)
    def test_search_resource_until_status_timeout(self, _):
        resource_name = "fake_resource"
        status_completed = mock.sentinel
        self._base_heat_backend._name = "fake_name"
        exp = exceptions.ArgusError("No resource %s found with name %s"
                                    % (resource_name,
                                       self._base_heat_backend._name))
        mock_list = mock.Mock()
        mock_resource = mock.Mock()
        mock_resource.resource_type = resource_name
        mock_resource.resource_status = "fake status"
        mock_resource.physical_resource_id = mock.sentinel
        mock_list.return_value = [mock_resource]
        self._base_heat_backend._heat_client.resources.list = mock_list
        with self.assertRaises(exceptions.ArgusError) as ex:
            self._base_heat_backend._search_resource_until_status(
                resource_name, status=status_completed)
        self.assertEqual(ex.exception.message, str(exp))

    @mock.patch("time.sleep", return_value=None)
    def test_search_resource_until_status_(self, _):
        resource_name = mock.sentinel
        status_completed = mock.sentinel
        exp = exceptions.ArgusError("No resource %s found with name %s"
                                    % (resource_name,
                                       self._base_heat_backend._name))
        mock_list = mock.Mock()
        mock_resource = mock.Mock()
        mock_resource.resource_type = "fake_resource"
        mock_list.return_value = [mock_resource]
        self._base_heat_backend._heat_client.resources.list = mock_list
        with self.assertRaises(exceptions.ArgusError) as ex:
            self._base_heat_backend._search_resource_until_status(
                resource_name, status=status_completed)
        self.assertEqual(ex.exception.message, str(exp))

    def test_internal_id(self):
        def fake_function():
            return mock.sentinel
        mock_search_until_status = mock.Mock()
        mock_search_until_status.return_value = fake_function
        (self._base_heat_backend.
         _search_resource_until_status) = mock_search_until_status
        result = self._base_heat_backend._internal_id()
        self.assertEqual(result, fake_function())
        (self._base_heat_backend._search_resource_until_status.
         assert_called_once_with(heat_backend.OS_NOVA_RESOURCE))

    def test_internal_instance_id(self):
        self._base_heat_backend._internal_id = mock.sentinel
        result = self._base_heat_backend.internal_instance_id()
        self.assertEqual(result, self._base_heat_backend._internal_id)

    @mock.patch('argus.backends.heat.heat_backend.BaseHeatBackend.'
                '_search_resource_until_status')
    def test_floating_ip_resource(self, _):
        def fake_function():
            return mock.sentinel
        mock_floating = mock.Mock()
        mock_floating.show_floating_ip.return_value = {
            "floating_ip": fake_function
        }
        self._base_heat_backend._manager.floating_ips_client = mock_floating
        result = self._base_heat_backend._floating_ip_resource()
        self.assertEqual(result, fake_function())

    def test_floating_ip(self):
        self._base_heat_backend._floating_ip_resource = {"ip": mock.sentinel}
        result = self._base_heat_backend.floating_ip()
        self.assertEqual(result,
                         self._base_heat_backend._floating_ip_resource['ip'])

    @mock.patch('argus.backends.tempest.manager.OUTPUT_SIZE')
    def test_instance_output(self, mock_output_size):
        self._base_heat_backend._manager = mock.Mock()
        (self._base_heat_backend._manager.instance_output.
         return_value) = mock.sentinel
        self._base_heat_backend.internal_instance_id = mock.Mock()
        result = self._base_heat_backend.instance_output()
        self.assertEqual(
            result,
            self._base_heat_backend._manager.instance_output.return_value)

    def test_reboot_instance(self):
        self._base_heat_backend._manager = mock.Mock()
        (self._base_heat_backend._manager.reboot_instance.
         return_value) = mock.sentinel
        self._base_heat_backend.internal_instance_id = mock.Mock()
        result = self._base_heat_backend.reboot_instance()
        self.assertEqual(
            result,
            self._base_heat_backend._manager.reboot_instance.return_value)
        self._base_heat_backend.internal_instance_id.assert_called_once_with()

    def test_instance_password(self):
        self._base_heat_backend.internal_instance_id = mock.Mock()
        self._base_heat_backend._keypair = mock.sentinel
        self._base_heat_backend._manager = mock.Mock()
        (self._base_heat_backend._manager.instance_password.
         return_value) = mock.sentinel
        result = self._base_heat_backend.instance_password()
        self.assertEqual(
            result,
            self._base_heat_backend._manager.instance_password.return_value)
        (self._base_heat_backend._manager.instance_password.
         assert_called_once_with(
             self._base_heat_backend.internal_instance_id(),
             self._base_heat_backend._keypair))

    def test_private_key(self):
        self._base_heat_backend._keypair = mock.Mock()
        self._base_heat_backend._keypair.private_key = mock.sentinel
        result = self._base_heat_backend.private_key()
        self.assertEqual(result, self._base_heat_backend._keypair.private_key)

    def test_public_key(self):
        self._base_heat_backend._keypair = mock.Mock()
        self._base_heat_backend._keypair.public_key = mock.sentinel
        result = self._base_heat_backend.public_key()
        self.assertEqual(result, self._base_heat_backend._keypair.public_key)

    def test_instance_server(self):
        self._base_heat_backend._manager = mock.Mock()
        (self._base_heat_backend._manager.instance_server.
         return_value) = mock.sentinel
        self._base_heat_backend.internal_instance_id = mock.Mock()
        result = self._base_heat_backend.instance_server()
        self.assertEqual(
            result,
            self._base_heat_backend._manager.instance_server.return_value)
        self._base_heat_backend.internal_instance_id.assert_called_once_with()

    @mock.patch('argus.config.CONFIG.openstack')
    def test_get_image_by_ref(self, mock_config):
        self._base_heat_backend._manager.compute_images_client = mock.Mock()
        (self._base_heat_backend._manager.compute_images_client.
         show_image.return_value) = mock.sentinel
        mock_config.image_ref = mock.sentinel

        result = self._base_heat_backend.get_image_by_ref()
        self.assertEqual(
            result,
            self._base_heat_backend._manager.compute_images_client.
            show_image.return_value)
        (self._base_heat_backend._manager.compute_images_client.show_image.
         assert_called_once_with(mock_config.image_ref))

    def test_get_mtu(self):
        self._base_heat_backend._manager = mock.Mock()
        self._base_heat_backend._manager.get_mtu.return_value = mock.sentinel
        result = self._base_heat_backend.get_mtu()
        self.assertEqual(result,
                         self._base_heat_backend._manager.get_mtu.return_value)
