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

import base64
import contextlib
import textwrap

import multiprocessing

import cherrypy
from six.moves import urllib


def _instantiate_services(services, scenario):
    for service in services:
        app = service.application
        script_name = service.script_name
        host = service.host
        port = service.port

        kwargs = {
            "root": app(scenario),
            "script_name": script_name,
            "config": {
                "/": {
                    "server.socket_host": host,
                    "server.socket_port": port,
                    "log.screen": False,
                }
            }
        }
        process = multiprocessing.Process(
            target=cherrypy.quickstart,
            kwargs=kwargs)
        process.start()
        yield process


@contextlib.contextmanager
def instantiate_services(services, scenario):
    """Context manager used for starting mocked metadata services."""

    # Start the service(s) in different process(es).
    processes = list(_instantiate_services(services, scenario))
    try:
        yield
    finally:
        # Send the shutdown "signal"
        for service in services:
            try:
                urllib.request.urlopen(service.stop_link)
            except urllib.error.URLError:
                pass
        for process in processes:
            process.join()
            process.terminate()


class BaseServiceApp(object):

    def __init__(self, scenario):
        self.scenario = scenario

    def _dispatch_method(self, operand):
        operand = operand.replace("-", "_")
        return getattr(self, operand)

    @cherrypy.expose
    def stop_me(self):  # pylint: disable=no-self-use
        """Stop the current running cherrypy engine."""
        cherrypy.engine.exit()


class EC2MetadataServiceApp(BaseServiceApp):
    pass


class CloudstackMetadataServiceApp(BaseServiceApp):
    """Metadata app for CloudStack service."""

    @cherrypy.expose
    def latest(self, data_type, operation=None):
        # Too complicated and overkill to use cherrypy.Dispatcher.
        # This should be as as simple as possible.
        return self._dispatch_method(data_type)(operation)

    def meta_data(self, operation):
        return self._dispatch_method(operation)()

    # pylint: disable=unused-argument
    def user_data(self, operation=None):
        return base64.encodestring(self.scenario._userdata)

    def instance_id(self):
        return self.scenario._server['id']

    def local_hostname(self):
        return self.scenario.instance_server()['name'][:15].lower()

    def public_keys(self):
        return self.scenario.public_key()

    # pylint: disable=no-self-use
    def service_offering(self):
        return textwrap.dedent("""
            availability-zone
            local-ipv4
            local-hostname
            public-ipv4
            public-hostname
            instance-id
            vm-id
            public-keys
            cloud-identifier""")


class CloudstackPasswordManagerApp(BaseServiceApp):
    """Metadata app for CloudStack password manager."""

    def __init__(self, scenario):
        super(CloudstackPasswordManagerApp, self).__init__(scenario)
        self._password = "Passw0rd"

    @cherrypy.expose
    def index(self):
        expected_header = "DomU_Request"
        if expected_header not in cherrypy.request.headers:
            raise cherrypy.HTTPError(400, "DomU_Request not given")

        operation = cherrypy.request.headers[expected_header]
        return self._dispatch_method(operation)()

    def send_my_password(self):
        if not self._password:
            return "saved_password"
        return self._password

    def saved_password(self):
        self._password = None
