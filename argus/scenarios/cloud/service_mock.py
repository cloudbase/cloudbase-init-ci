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

import json
import multiprocessing
import textwrap
import time
import warnings

import cherrypy
# pylint: disable=import-error
from six.moves import http_client
from six.moves import urllib

from argus import util


CLOUDSTACK_EXPECTED_HEADER = "Domu-Request"
STOP_LINK_RETRY_COUNT = 5


def _create_service_server(service, backend):
    app = service.application
    script_name = service.script_name
    host = service.host
    port = service.port

    cherrypy.config.update({
        "server.socket_host": host,
        "server.socket_port": port,
        "log.screen": False,
    })
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        cherrypy.quickstart(app(backend), script_name)


def _instantiate_services(services, backend):
    for service in services:
        process = multiprocessing.Process(
            target=_create_service_server,
            args=(service, backend))
        process.start()
        yield process


class ServiceManager(object):
    """Creates the required mocked service processes."""

    def __init__(self, services, backend):
        self._services = services
        self._processes = list(_instantiate_services(services, backend))

    def terminate(self):
        # Send the shutdown "signal".
        for service in self._services:
            for _ in range(STOP_LINK_RETRY_COUNT):
                # Do a best effort to stop the service.
                try:
                    urllib.request.urlopen(service.stop_link)
                    break
                except (urllib.error.URLError, http_client.BadStatusLine):
                    time.sleep(1)

        for process in self._processes:
            process.terminate()
            process.join()


@cherrypy.tools.response_headers(headers=[("Content-Type", "text/plain")])
class BaseServiceApp(object):

    def __init__(self, backend):
        self._backend = backend

    def _dispatch_method(self, operand):
        operand = operand.replace("-", "_")
        return getattr(self, operand)

    @cherrypy.expose
    def stop_me(self):  # pylint: disable=no-self-use
        """Stop the current running cherrypy engine."""
        cherrypy.engine.exit()


class MetadataServiceAppMixin(object):
    """Common metadata resources."""

    def instance_id(self):
        return self._backend.internal_instance_id()

    def local_hostname(self):
        return self._backend.instance_server()['name'][:15].lower()

    def public_keys(self):
        # The public key(s) should be let prefixed with EOL
        # (as the metadata providers will do).
        return self._backend.public_key()


class EC2MetadataServiceApp(MetadataServiceAppMixin, BaseServiceApp):
    """Mock server for testing EC2 metadata service."""

    def __init__(self, *args, **kwargs):
        super(EC2MetadataServiceApp, self).__init__(*args, **kwargs)
        self._keydict = None

    @property
    def keydict(self):
        """Build a dictionary with all the public keys.

        Use as keys their indexes in increasing order starting with 0.
        """
        if not self._keydict:
            keys = (super(EC2MetadataServiceApp, self)
                    .public_keys().splitlines())
            self._keydict = dict(enumerate(keys))
        return self._keydict

    @cherrypy.expose
    def default(self, *args):
        operation, remain = args[0], args[1:]
        return self._dispatch_method(operation)(*remain)

    def public_keys(self, *remain):
        """Mimic the behavior of EC2 metadata service.

        A first request to /public-keys will return all the available keys,
        each one per line in this form: "index=key-name". Then, based on the
        number of keys and their indexes, will follow requests like
        /public-keys/<index>/openssh-key which returns the actual content.
        """
        if not len(remain):
            # Return their indexes and names.
            return "\n".join(["{}={}".format(idx, key.split()[-1])
                              for idx, key in self.keydict.items()])
        # Return the corresponding key, based on the given index.
        return self.keydict.get(int(remain[0]))


class CloudstackMetadataServiceApp(MetadataServiceAppMixin, BaseServiceApp):
    """Metadata application for CloudStack service."""

    @cherrypy.expose
    def latest(self, data_type, operation=None):
        # Too complicated and overkill to use cherrypy.Dispatcher.
        # This should be as simple as possible.
        return self._dispatch_method(data_type)(operation)

    def meta_data(self, operation):
        if operation is not None:
            return self._dispatch_method(operation)()
        return "meta-data"

    # pylint: disable=unused-argument
    def user_data(self, operation=None):
        userdata = self._backend.userdata
        return userdata or ""

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
    """Metadata application for CloudStack password manager."""

    def __init__(self, backend):
        super(CloudstackPasswordManagerApp, self).__init__(backend)
        self._password = "Passw0rd"

    @cherrypy.expose
    def index(self):
        expected_header = CLOUDSTACK_EXPECTED_HEADER
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

    @cherrypy.expose
    def password(self, password=None):
        if cherrypy.request.method != 'POST':
            raise cherrypy.HTTPError(405, 'Method not allowed')
        self._password = password


class MaasMetadataServiceApp(MetadataServiceAppMixin, BaseServiceApp):
    """Metadata application for MAAS service."""

    @staticmethod
    def _verify_headers():
        if 'Authorization' not in cherrypy.request.headers:
            raise cherrypy.HTTPError(400, "Authorization header not given")

        auth = cherrypy.request.headers['Authorization']
        if not auth.startswith('OAuth'):
            raise cherrypy.HTTPError(400, "Authorization header malformed. "
                                          "It should start with `OAuth`.")

        auth = auth[6:]
        parts = map(str.strip, auth.split(","))
        auth_parts = {part.split("=")[0] for part in parts}

        required_headers = {
            'oauth_version', 'oauth_nonce',
            'oauth_timestamp', 'oauth_token',
            'oauth_consumer_key',
        }
        if not required_headers.issubset(auth_parts):
            missing = required_headers - auth_parts
            message = "Expected headers not found %r" % missing
            raise cherrypy.HTTPError(400, message)

    @cherrypy.expose
    def user_data(self):
        self._verify_headers()
        return self._backend.userdata or ""

    @cherrypy.expose
    def meta_data(self, operation=None):
        self._verify_headers()
        if operation is not None:
            return self._dispatch_method(operation)()
        return "meta-data"

    @staticmethod
    def x509():
        return util.get_certificate()


class HTTPKeysMetadataServiceApp(BaseServiceApp):
    """Custom OpenStack http metadata."""

    @util.cached_property
    def _get_metadata(self):
        """Fill-in the metadata password provided by the config file."""
        metadata = {
            "keys": [
                {
                    "name": "argus_cert",
                    "type": "x509",
                    "data": util.get_certificate()
                }
            ] + [{
                "name": "argus_key",
                "type": "ssh",
                "data": data
            } for data in util.get_public_keys()]
        }
        key = "admin_pass"
        metadata[key] = self._backend.metadata[key]
        return metadata

    @cherrypy.expose
    def default(self, *args):
        link = "/".join(args)
        if "latest/meta_data.json" not in link:
            # Handle invalid and password posting cases.
            raise cherrypy.HTTPError(404)
        return json.dumps(self._get_metadata)
