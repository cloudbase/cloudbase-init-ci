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
from six.moves import urllib

from argus import config as argus_config
from argus.scenarios.cloud import base
from argus.scenarios.cloud import service_mock

CONFIG = argus_config.CONFIG


def get_port_number(url):
    """Gets the port number from a given url.

    :param url: String value of a URL.

    :rtype: int
    :returns: The port value from the given url.
    """
    parsed_url = urllib.parse.urlparse(url)
    if parsed_url.port is None:
        port_number = 443 if parsed_url.scheme == 'https' else 80
    else:
        port_number = parsed_url.port
    return port_number


class named(collections.namedtuple("service", "application script_name "
                                              "host port")):

    @property
    def stop_link(self):
        link = "http://{host}:{port}{script_name}/stop_me/"
        return link.format(host=self.host,
                           port=self.port,
                           script_name=self.script_name)


class BaseServiceMockMixin(object):
    """Mixin class for mocking metadata services.

    In order to have support for mocked metadata services, set a list
    of :meth:`named` entries in the class, as such::

        class Test(BaseServiceMockMixin, CloudScenario):
            services = [
                 named(application, script_name, host, port)
            ]
    """

    @classmethod
    def prepare_instance(cls):
        cls._service_manager = service_mock.ServiceManager(
            cls.services, cls.backend)
        super(BaseServiceMockMixin, cls).prepare_instance()

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, '_service_manager'):
            cls._service_manager.terminate()
        super(BaseServiceMockMixin, cls).tearDownClass()


class EC2WindowsScenario(BaseServiceMockMixin, base.CloudScenario):
    """Scenario for testing the EC2 metadata service."""

    services = [
        named(application=service_mock.EC2MetadataServiceApp,
              script_name="/2009-04-04/meta-data",
              host="0.0.0.0",
              port=get_port_number(CONFIG.ec2_mock.metadata_base_url)),
    ]


class CloudstackWindowsScenario(BaseServiceMockMixin,
                                base.CloudScenario):
    """Scenario for testing the Cloudstack metadata service."""

    services = [
        named(application=service_mock.CloudstackMetadataServiceApp,
              script_name="",
              host="0.0.0.0",
              port=get_port_number(CONFIG.cloudstack_mock.metadata_base_url)),
        named(application=service_mock.CloudstackPasswordManagerApp,
              script_name="",
              host="0.0.0.0",
              port=CONFIG.cloudstack_mock.password_server_port),
    ]


class MaasWindowsScenario(BaseServiceMockMixin, base.CloudScenario):
    """Scenario for testing the Maas metadata service."""

    services = [
        named(application=service_mock.MaasMetadataServiceApp,
              script_name="/2012-03-01",
              host="0.0.0.0",
              port=get_port_number(CONFIG.maas_mock.metadata_base_url)),
    ]


class HTTPKeysWindowsScenario(BaseServiceMockMixin, base.CloudScenario):

    """Scenario for testing custom OpenStack http metadata service."""

    services = [
        named(application=service_mock.HTTPKeysMetadataServiceApp,
              script_name="/openstack",
              host="0.0.0.0",
              port=get_port_number(CONFIG.openstack_mock.metadata_base_url))
    ]
