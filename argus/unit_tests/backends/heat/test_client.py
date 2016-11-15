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

# pylint: disable=no-value-for-parameter, too-many-lines, protected-access
# pylint: disable=too-many-public-methods

import unittest
from argus.backends.heat import client
from heatclient import exc
from heatclient import client as heatclient_client
from keystoneclient.auth.identity import v2 as v2_auth
from keystoneclient.auth.identity import v3 as v3_auth
from keystoneclient import exceptions as ks_exc


try:
    import unittest.mock as mock
except ImportError:
    import mock


class TestHeatClient(unittest.TestCase):

    @mock.patch('six.moves.urllib_parse.urlparse')
    @mock.patch('keystoneclient.discover.Discover')
    def _test_discover_auth_versions_exception(
            self, mock_discover, mock_url_parse,
            client_exception=None, expected_auth="fake auth"):
        auths = {
            "/v2": None,
            "/v3": None
        }
        if client_exception is None:
            mock_url_for = mock.Mock()
            mock_url_for.url_for.side_effect = tuple(auths)
            mock_discover.return_value = mock_url_for
            result = client._discover_auth_versions(
                mock.sentinel, mock.sentinel)
            self.assertEqual(result, tuple(auths.values()))
        else:
            auth_url = mock.sentinel
            mock_discover.side_effect = ks_exc.ClientException()

            mock_path = mock.Mock()
            mock_path.path = expected_auth
            mock_url_parse.return_value = mock_path

            if expected_auth in auths.keys():
                result = client._discover_auth_versions(
                    mock.sentinel, auth_url)
                auths[expected_auth] = auth_url
                self.assertEqual(
                    sorted(result), sorted(tuple(auths.values())))
            else:
                msg = ('Unable to determine the Keystone version '
                       'to authenticate with using the given '
                       'auth_url. Identity service may not support API '
                       'version discovery. Please provide a versioned '
                       'auth_url instead.')
                exp = exc.CommandError(msg)
                with self.assertRaises(exc.CommandError) as ex:
                    client._discover_auth_versions(
                        mock.sentinel, mock.sentinel)
                self.assertEqual(ex.exception.message, exp.message)

    @mock.patch('keystoneclient.discover.Discover')
    def test_discover_auth_version_success(self, mock_discover):
        mock_url_for = mock.Mock()
        mock_url_for.url_for = mock.Mock(side_effect=['2.0', '3.0'])
        mock_discover.return_value = mock_url_for
        result = client._discover_auth_versions(mock.sentinel, mock.sentinel)
        self.assertEqual(result, ('2.0', '3.0'))

    def test_discover_auth_version_v2(self):
        self._test_discover_auth_versions_exception(
            client_exception=True,
            expected_auth='/v2'
        )

    def test_discover_auth_version_v3(self):
        self._test_discover_auth_versions_exception(
            client_exception=True,
            expected_auth='/v3'
        )

    def test_discover_auth_version_command_error(self):
        self._test_discover_auth_versions_exception(
            client_exception=True
        )

    def _test_keystone_v3_auth(self, auth_token):
        v3_auth_url = mock.sentinel
        kwargs = {
            "fake param 1": mock.sentinel,
            "auth_token": auth_token,
            "fake param 2": mock.sentinel
        }
        if auth_token is None:
            class_ = v3_auth.password.Password
        else:
            class_ = v3_auth.token.Token
        with mock.patch('keystoneclient.auth.identity.v3.' + class_.__name__,
                        spec=class_) as mock_class:
            result = client._get_keystone_v3_auth(v3_auth_url, **kwargs)
            self.assertTrue(isinstance(result, class_))
            if auth_token is None:
                kwargs.pop('auth_token', None)
                mock_class.assert_called_once_with(v3_auth_url, **kwargs)
            else:
                mock_class.assert_called_once_with(v3_auth_url, auth_token)

    def test_password(self):
        self._test_keystone_v3_auth(auth_token=None)

    def test_token(self):
        self._test_keystone_v3_auth(auth_token=mock.sentinel)

    def _test_get_keystone_v2_auth(self, auth_token):
        v2_auth_url = mock.sentinel
        kwargs = {
            "fake param 1": mock.sentinel,
            "auth_token": auth_token,
            "fake param 2": mock.sentinel,
            "project_id": mock.sentinel,
            "project_name": mock.sentinel,
            "tenant_id": mock.sentinel,
            "tenant_name": mock.sentinel,
            "username": mock.sentinel,
            "password": mock.sentinel
        }
        if auth_token is not None:
            class_ = v2_auth.Token
        else:
            class_ = v2_auth.Password

        with mock.patch('keystoneclient.auth.identity.v2.' + class_.__name__,
                        spec=class_) as mock_class:
            result = client._get_keystone_v2_auth(v2_auth_url, **kwargs)
            self.assertTrue(isinstance(result, class_))

        if auth_token is not None:
            mock_class.assert_called_once_with(
                v2_auth_url, auth_token,
                tenant_id=mock.sentinel,
                tenant_name=mock.sentinel)
        else:
            mock_class.assert_called_once_with(
                v2_auth_url,
                username=kwargs.pop('username', None),
                password=kwargs.pop('password', None),
                tenant_id=mock.sentinel,
                tenant_name=mock.sentinel)

    def test_get_keystone_v2_auth_token(self):
        self._test_get_keystone_v2_auth(auth_token=mock.sentinel)

    def test_get_keystone_v2_auth_password(self):
        self._test_get_keystone_v2_auth(auth_token=None)

    @mock.patch('argus.backends.heat.client._get_keystone_v3_auth')
    @mock.patch('argus.backends.heat.client._get_keystone_v2_auth')
    @mock.patch('argus.backends.heat.client._discover_auth_versions')
    def _test_get_keystone_auth(self, mock_discover, mock_v2, mock_v3,
                                v2_auth_url=None, v3_auth_url=None, **kwargs):
        mock_discover.return_value = (v2_auth_url, v3_auth_url)
        mock_v2.return_value = mock.sentinel
        mock_v3.return_value = mock.sentinel
        result = client._get_keystone_auth(mock.sentinel, mock.sentinel,
                                           **kwargs)
        if v3_auth_url and v2_auth_url:
            user_domain_name = kwargs.get('user_domain_name', None)
            user_domain_id = kwargs.get('user_domain_id', None)
            project_domain_name = kwargs.get('project_domain_name', None)
            project_domain_id = kwargs.get('project_domain_id', None)
            if (user_domain_name or user_domain_id or project_domain_name or
                    project_domain_id):
                mock_v3.assert_called_once_with(v3_auth_url, **kwargs)
                self.assertEqual(result, v3_auth_url)
            else:
                mock_v2.assert_called_once_with(v2_auth_url, **kwargs)
                self.assertEqual(result, v2_auth_url)
        elif v3_auth_url:
            mock_v3.assert_called_once_with(v3_auth_url, **kwargs)
            self.assertEqual(result, v3_auth_url)
        elif v2_auth_url:
            mock_v2.assert_called_once_with(v2_auth_url, **kwargs)
            self.assertEqual(result, v2_auth_url)

    def test_get_keystone_auth_v3_v2(self):
        kwargs = {
            "user_domain_name": mock.sentinel
        }
        self._test_get_keystone_auth(v2_auth_url=mock.sentinel,
                                     v3_auth_url=mock.sentinel, **kwargs)

    def test_get_keystone_auth_v3_v2_no_kwargs(self):
        self._test_get_keystone_auth(v2_auth_url=mock.sentinel,
                                     v3_auth_url=mock.sentinel)

    def test_get_keystone_auth_v3(self):
        kwargs = {
            "user_domain_name": mock.sentinel
        }
        self._test_get_keystone_auth(v3_auth_url=mock.sentinel, **kwargs)

    def test_get_keystone_auth_v2(self):
        kwargs = {
            "user_domain_name": mock.sentinel
        }
        self._test_get_keystone_auth(v2_auth_url=mock.sentinel, **kwargs)

    @mock.patch('argus.backends.heat.client._discover_auth_versions')
    def test_get_keystone_auth_fails(self, mock_discover):
        v2_auth_url, v3_auth_url = None, None
        mock_discover.return_value = (v2_auth_url, v3_auth_url)
        with self.assertRaises(exc.CommandError) as ex:
            client._get_keystone_auth("session", "url")
            self.assertEqual(ex, 'Unable to determine the Keystone '
                             'version to authenticate with using the '
                             'given auth_url.')

    @mock.patch('argus.backends.heat.client._get_keystone_auth')
    @mock.patch('heatclient.common.utils.env')
    @mock.patch('keystoneclient.session.Session')
    def test_heat_client(self, mock_kssession, mock_env, mock_get_ks_auth):
        mock_env.return_value = mock.sentinel
        mock_get_endpoint = mock.Mock()
        mock_get_endpoint.get_endpoint.return_value = mock.sentinel
        mock_get_ks_auth.return_value = mock_get_endpoint

        class Credentials(object):
            def __init__(self):
                self.username = "fake username"
                self.user_id = "fake user id"
                self.password = "fake password"
                self.tenant_id = "fake tenant id"
                self.tenant_name = "fake tenant name"

        credentials = Credentials()
        result = client.heat_client(credentials)
        self.assertTrue(result, heatclient_client.Client)
        mock_kssession.assert_called_once_with(verify=True)
        mock_env.assert_called_once_with('OS_AUTH_URL')
