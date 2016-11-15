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

from heatclient import client
from heatclient.common import utils
from heatclient import exc
from keystoneclient.auth.identity import v2 as v2_auth
from keystoneclient.auth.identity import v3 as v3_auth
from keystoneclient import discover
from keystoneclient import exceptions as ks_exc
from keystoneclient import session as kssession
from six.moves import urllib_parse as urlparse


def _discover_auth_versions(session, auth_url):
    # discover the API versions the server is supporting base on the
    # given URL
    v2_auth_url = None
    v3_auth_url = None
    try:
        ks_discover = discover.Discover(session=session, auth_url=auth_url)
        v2_auth_url = ks_discover.url_for('2.0')
        v3_auth_url = ks_discover.url_for('3.0')
    except ks_exc.ClientException:
        # Identity service may not support discover API version.
        # Lets trying to figure out the API version from the original URL.
        path = urlparse.urlparse(auth_url).path
        path = path.lower()
        if path.startswith('/v3'):
            v3_auth_url = auth_url
        elif path.startswith('/v2'):
            v2_auth_url = auth_url
        else:
            # not enough information to determine the auth version
            msg = ('Unable to determine the Keystone version '
                   'to authenticate with using the given '
                   'auth_url. Identity service may not support API '
                   'version discovery. Please provide a versioned '
                   'auth_url instead.')
            raise exc.CommandError(msg)

    return v2_auth_url, v3_auth_url


def _get_keystone_v3_auth(v3_auth_url, **kwargs):
    auth_token = kwargs.pop('auth_token', None)
    if auth_token:
        return v3_auth.Token(v3_auth_url, auth_token)
    else:
        return v3_auth.Password(v3_auth_url, **kwargs)


def _get_keystone_v2_auth(v2_auth_url, **kwargs):
    auth_token = kwargs.pop('auth_token', None)
    tenant_id = kwargs.pop('project_id', None)
    tenant_name = kwargs.pop('project_name', None)
    if auth_token:
        return v2_auth.Token(v2_auth_url, auth_token,
                             tenant_id=tenant_id,
                             tenant_name=tenant_name)
    else:
        return v2_auth.Password(v2_auth_url,
                                username=kwargs.pop('username', None),
                                password=kwargs.pop('password', None),
                                tenant_id=tenant_id,
                                tenant_name=tenant_name)


def _get_keystone_auth(session, auth_url, **kwargs):
    # discover the supported keystone versions using the given URL
    (v2_auth_url, v3_auth_url) = _discover_auth_versions(
        session=session,
        auth_url=auth_url)

    # Determine which authentication plugin to use. First inspect the
    # auth_url to see the supported version. If both v3 and v2 are
    # supported, then use the highest version if possible.

    if v3_auth_url and v2_auth_url:
        user_domain_name = kwargs.get('user_domain_name', None)
        user_domain_id = kwargs.get('user_domain_id', None)
        project_domain_name = kwargs.get('project_domain_name', None)
        project_domain_id = kwargs.get('project_domain_id', None)

        # support both v2 and v3 auth. Use v3 if domain information is
        # provided.
        if (user_domain_name or user_domain_id or project_domain_name or
                project_domain_id):
            return _get_keystone_v3_auth(v3_auth_url, **kwargs)
        else:
            return _get_keystone_v2_auth(v2_auth_url, **kwargs)
    elif v3_auth_url:
        # support only v3
        return _get_keystone_v3_auth(v3_auth_url, **kwargs)
    elif v2_auth_url:
        # support only v2
        return _get_keystone_v2_auth(v2_auth_url, **kwargs)

    raise exc.CommandError('Unable to determine the Keystone version '
                           'to authenticate with using the given '
                           'auth_url.')


def heat_client(credentials, api_version=1):
    """Get a new Heat client using the given credentials."""
    endpoint = ''
    service_type = 'orchestration'
    keystone_session = kssession.Session(verify=True)
    os_auth_url = utils.env('OS_AUTH_URL')
    kwargs = {
        'username': credentials.username,
        'user_id': credentials.user_id,
        'password': credentials.password,
        'project_id': credentials.tenant_id,
        'project_name': credentials.tenant_name,
    }
    keystone_auth = _get_keystone_auth(keystone_session,
                                       os_auth_url, **kwargs)
    endpoint = keystone_auth.get_endpoint(keystone_session,
                                          service_type=service_type,
                                          region_name=None)

    endpoint_type = 'publicURL'
    kwargs = {
        'auth_url': os_auth_url,
        'session': keystone_session,
        'auth': keystone_auth,
        'service_type': service_type,
        'endpoint_type': endpoint_type,
        'username': credentials.username,
        'password': credentials.password,
        'include_pass': False
    }

    return client.Client(api_version, endpoint, **kwargs)
