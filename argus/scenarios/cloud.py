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

from argus.scenarios import base
from argus.scenarios import service_mock
from argus import util


class named(collections.namedtuple("service", "application script_name "
                                              "host port")):

    @property
    def stop_link(self):
        link = "http://{host}:{port}{script_name}/stop_me/"
        return link.format(host=self.host,
                           port=self.port,
                           script_name=self.port)


class BaseWindowsScenario(base.BaseArgusScenario):
    """Base class for Windows-based scenarios."""

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

    def prepare_instance(self):
        with service_mock.instantiate_services(self.services, self):
            super(BaseServiceMockMixin, self).prepare_instance()


class EC2WindowsScenario(BaseServiceMockMixin, BaseWindowsScenario):
    """Scenario for testing the EC2 metadata service."""

    services = [
        named(application=service_mock.EC2MetadataServiceApp,
              script_name="",
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
