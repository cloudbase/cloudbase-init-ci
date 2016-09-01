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

from argus.scenarios.cloud import base
from argus.scenarios.cloud import service_mock


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
              port=2000),
    ]


class CloudstackWindowsScenario(BaseServiceMockMixin,
                                base.CloudScenario):
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


class MaasWindowsScenario(BaseServiceMockMixin, base.CloudScenario):
    """Scenario for testing the Maas metadata service."""

    services = [
        named(application=service_mock.MaasMetadataServiceApp,
              script_name="/2012-03-01",
              host="0.0.0.0",
              port=2002),
    ]


class HTTPKeysWindowsScenario(BaseServiceMockMixin, base.CloudScenario):

    """Scenario for testing custom OpenStack http metadata service."""

    services = [
        named(application=service_mock.HTTPKeysMetadataServiceApp,
              script_name="/openstack",
              host="0.0.0.0",
              port=2003)
    ]
