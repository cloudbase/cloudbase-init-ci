import collection
import contextlib


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

        class Test(BaseServiceMockMixin, BaseWindowsTempestBackend):
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
