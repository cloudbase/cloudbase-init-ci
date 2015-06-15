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

import collections
import contextlib

from argus import exceptions
from argus.scenarios import base
from argus.scenarios import service_mock
from argus import util

with util.restore_excepthook():
    from tempest.common import isolated_creds


CONF = util.get_config()
SUBNET6_CIDR = "::ffff:a00:0/120"
DNSES6 = ["::ffff:808:808", "::ffff:808:404"]


class named(collections.namedtuple("service", "application script_name "
                                              "host port")):

    @property
    def stop_link(self):
        link = "http://{host}:{port}{script_name}/stop_me/"
        return link.format(host=self.host,
                           port=self.port,
                           script_name=self.script_name)


class BaseWindowsScenario(base.BaseArgusScenario):
    """Base class for Windows-based scenarios."""

    def __init__(self, *args, **kwargs):
        super(BaseWindowsScenario, self).__init__(*args, **kwargs)
        # Installer details.
        self.build = None
        self.arch = None

    def _get_log_template(self, suffix):
        template = super(BaseWindowsScenario, self)._get_log_template(suffix)
        if self.build and self.arch:
            # Prepend the log with the installer information (cloud).
            template = "{}-{}-{}".format(self.build, self.arch, template)
        return template

    def _prepare_instance(self):
        recipe = super(BaseWindowsScenario, self)._prepare_instance()
        recipe.build = self.build
        recipe.arch = self.arch
        return recipe

    def get_remote_client(self, username=None, password=None,
                          protocol='http', **kwargs):
        if username is None:
            username = self._image.default_ci_username
        if password is None:
            password = self._image.default_ci_password
        return util.WinRemoteClient(self._floating_ip['ip'],
                                    username,
                                    password,
                                    transport_protocol=protocol)

    remote_client = util.cached_property(get_remote_client, 'remote_client')


class NetworkWindowsScenario(BaseWindowsScenario):
    """Scenario for testing static network configuration.

    Creates an additional internal network which will be
    bound explicitly with the new created instance.
    """

    def _get_isolated_network(self):
        """Returns the network itself from the isolated network resources.

        This works only with the isolated credentials and
        this step is achieved by allowing/forcing tenant isolation.
        """
        # Extract the just created private network.
        return self._credentials().network

    def _get_networks(self):
        """Explicitly gather and return the private networks.

        All these networks will be attached to the newly created
        instance without letting nova to handle this part.
        """
        _networks = self._network_client.list_networks()["networks"]
        # Skip external/private networks.
        networks = [net["id"] for net in _networks
                    if not net["router:external"]]
        # Put in front the main private network.
        head = self._get_isolated_network()["id"]
        networks.remove(head)
        networks.insert(0, head)
        # Adapt the list to a format accepted by the API.
        return [{"uuid": net} for net in networks]

    def _create_private_network(self):
        """Create an extra private network to be attached.

        This network is the one with disabled DHCP and
        ready for static configuration by cb-init.
        """
        tenant_id = self._credentials().tenant_id
        # pylint: disable=protected-access
        net_resources = self._isolated_creds._create_network_resources(
            tenant_id)

        # Store the network for later cleanup.
        key = "fake"
        fake_net_creds = util.get_namedtuple(
            "FakeCreds",
            ("network", "subnet", "router",
             "user_id", "tenant_id", "username", "tenant_name"),
            net_resources + (None,) * 4)
        self._isolated_creds.isolated_creds[key] = fake_net_creds

        # Disable DHCP for this network to test static configuration and
        # also add default DNS name servers.
        subnet_id = fake_net_creds.subnet["id"]
        net_client = self._network_client
        net_client.update_subnet(subnet_id, enable_dhcp=False,
                                 dns_nameservers=CONF.argus.dns_nameservers)

        # Change the allocation pool to configure any IP,
        # other the one used already with dynamic settings.
        allocation_pools = net_client.show_subnet(subnet_id)["subnet"][
            "allocation_pools"]
        allocation_pools[0]["start"] = util.next_ip(
            allocation_pools[0]["start"], step=2)
        net_client.update_subnet(subnet_id, allocation_pools=allocation_pools)

        # Create and attach an IPv6 subnet for this network. Also, register
        # it for later cleanup.
        subnet6_name = util.rand_name(self.__class__.__name__) + "-subnet6"
        network_id = fake_net_creds.network["id"]
        net_client.create_subnet(
            network_id=network_id,
            cidr=SUBNET6_CIDR,
            name=subnet6_name,
            dns_nameservers=DNSES6,
            tenant_id=tenant_id,
            enable_dhcp=False,
            ip_version=6)

    def _prepare_run(self):
        # Just like a normal preparer, but this time
        # with explicitly specified attached networks.
        super(NetworkWindowsScenario, self)._prepare_run()

        if not isinstance(self._isolated_creds,
                          isolated_creds.IsolatedCreds):
            raise exceptions.ArgusError(
                "Network resources are not available."
            )

        self._create_private_network()
        self._networks = self._get_networks()

    def get_network_interfaces(self):
        """Retrieve and parse network details from the compute node."""
        net_client = self._network_client
        guest_nics = []
        for network in self._networks or []:
            network_id = network["uuid"]
            net_details = net_client.show_network(network_id)["network"]
            nic = dict.fromkeys(util.NETWORK_KEYS)
            for subnet_id in net_details["subnets"]:
                details = net_client.show_subnet(subnet_id)["subnet"]

                # The network interface should follow the format found under
                # `windows.InstanceIntrospection.get_network_interfaces`
                # method or `argus.util.NETWORK_KEYS` model.
                v6switch = details["ip_version"] == 6
                v6suffix = "6" if v6switch else ""
                nic["dhcp"] = details["enable_dhcp"]
                nic["dns" + v6suffix] = details["dns_nameservers"]
                nic["gateway" + v6suffix] = details["gateway_ip"]
                nic["netmask" + v6suffix] = (
                    details["cidr"].split("/")[1] if v6switch
                    else util.cidr2netmask(details["cidr"]))

                # Find rest of the details under the ports using this subnet.
                # There should be no conflicts because on the current
                # architecture every instance is using its own router,
                # subnet and network accessible only to it.
                ports = net_client.list_ports()["ports"]
                for port in ports:
                    # Select instance related ports only, with the
                    # corresponding subnet ID.
                    if "compute" not in port["device_owner"]:
                        continue
                    ip_address = None
                    for fixed_ip in port["fixed_ips"]:
                        if fixed_ip["subnet_id"] == subnet_id:
                            ip_address = fixed_ip["ip_address"]
                            break
                    if not ip_address:
                        continue
                    nic["mac"] = port["mac_address"].upper()
                    nic["address" + v6suffix] = ip_address
                    break

            guest_nics.append(nic)
        return guest_nics


class RescueWindowsScenario(BaseWindowsScenario):
    """Instance rescue Windows-based scenario."""

    def rescue_server(self):
        admin_pass = self._image.default_ci_password
        self._servers_client.rescue_server(self._server['id'],
                                           adminPass=admin_pass)
        self._servers_client.wait_for_server_status(self._server['id'],
                                                    'RESCUE')

    def unrescue_server(self):
        self._servers_client.unrescue_server(self._server['id'])
        self._servers_client.wait_for_server_status(self._server['id'],
                                                    'ACTIVE')


class BaseServiceMockMixin(object):
    """Mixin class for mocking metadata services.

    In order to have support for mocked metadata services, set a list
    of :meth:`named` entries in the class, as such::

        class Test(BaseServiceMockMixin, BaseArgusScenario):
            services = [
                 named(application, script_name, host, port)
            ]

    These services will be started and will be stopped after
    :meth:`prepare_instance` finishes.
    """

    @contextlib.contextmanager
    def instantiate_mock_services(self):
        with service_mock.instantiate_services(self.services, self):
            yield

    def prepare_instance(self):
        with self.instantiate_mock_services():
            super(BaseServiceMockMixin, self).prepare_instance()


class EC2WindowsScenario(BaseServiceMockMixin, BaseWindowsScenario):
    """Scenario for testing the EC2 metadata service."""

    services = [
        named(application=service_mock.EC2MetadataServiceApp,
              script_name="/2009-04-04/meta-data",
              host="0.0.0.0",
              port=2000),
    ]


class CloudstackWindowsScenario(BaseServiceMockMixin,
                                BaseWindowsScenario):
    """Scenario for testing the Cloudstack metadata service."""

    services = [
        named(application=service_mock.CloudstackMetadataServiceApp,
              script_name="",
              host="0.0.0.0",
              port=2001),
        named(application=service_mock.CloudstackPasswordManagerApp,
              script_name="",
              host="0.0.0.0",
              port=8080),
    ]

    def reboot_instance(self):
        self._servers_client.reboot(server_id=self._server['id'],
                                    reboot_type='soft')
        self._servers_client.wait_for_server_status(self._server['id'],
                                                    'ACTIVE')


class MaasWindowsScenario(BaseServiceMockMixin, BaseWindowsScenario):
    """Scenario for testing the Maas metadata service."""

    services = [
        named(application=service_mock.MaasMetadataServiceApp,
              script_name="/2012-03-01",
              host="0.0.0.0",
              port=2002),
    ]


class HTTPKeysWindowsScenario(BaseServiceMockMixin, BaseWindowsScenario):

    """Scenario for testing custom OpenStack http metadata service."""

    services = [
        named(application=service_mock.HTTPKeysMetadataServiceApp,
              script_name="/openstack",
              host="0.0.0.0",
              port=2003)
    ]
