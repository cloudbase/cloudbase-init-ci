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

"""Various utilities for the cloud base types of tests."""

import os
import unittest

from argus import exceptions
from argus import util


__all__ = (
    'skip_unless_dnsmasq_configured',
    'requires_service',
)


DNSMASQ_NEUTRON = '/etc/neutron/dnsmasq-neutron.conf'
DHCP_AGENT = '/etc/neutron/dhcp_agent.ini'


@util.run_once
def _dnsmasq_configured():
    """Verify that the dnsmasq_config_file was set and it exists.

    Without it, tests for MTU or NTP will fail, since their plugins
    are relying on DHCP to provide this information.
    """
    if not os.path.exists(DHCP_AGENT):
        return False
    try:
        with open(DHCP_AGENT) as stream:
            for line in stream:
                if not line.startswith('dnsmasq_config_file'):
                    continue
                _, _, dnsmasq_file = line.partition("=")
                if dnsmasq_file.strip() == DNSMASQ_NEUTRON:
                    return True
    except IOError:
        raise exceptions.ArgusPermissionDenied("Add read permission for %s." %
                                               DHCP_AGENT)
    return False


def skip_unless_dnsmasq_configured(func):
    msg = (
        "Test will fail if the `dhcp-option-force` option "
        "was not configured by the `dnsmasq_config_file` "
        "from neutron/dhcp-agent.ini.")
    return unittest.skipUnless(_dnsmasq_configured(), msg)(func)


def requires_service(service_type='http'):
    """Sets function attribute required_service_type to service_type."""

    def decorator(func):
        func.required_service_type = service_type
        return func
    return decorator


def decrypt_password(password, private_key):
    """Decrypt the password using the private key.

    :param password: The password we want to decrypt
    :param private_ley: The private key to use
    """
    with util.create_tempfile(private_key) as tmp:
        return util.decrypt_password(
            private_key=tmp,
            password=password)


class InstancePasswordMixin(object):

    @property
    def password(self):
        enc_password = self._recipe.metadata_provider.get_password()
        private_keys = self._recipe.metadata_provider.get_ssh_privatekeys()
        private_key = private_keys.values().pop()
        return decrypt_password(enc_password, private_key)
