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

import functools
import os
import unittest

from argus import util


__all__ = (
    'skip_unless_dnsmasq_configured',
    'requires_service',
    'get_dict',
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
    with open(DHCP_AGENT) as stream:
        for line in stream:
            if not line.startswith('dnsmasq_config_file'):
                continue
            _, _, dnsmasq_file = line.partition("=")
            if dnsmasq_file.strip() == DNSMASQ_NEUTRON:
                return True
    return False


def skip_unless_dnsmasq_configured(func):
    msg = (
        "Test will fail if the `dhcp-option-force` option "
        "was not configured by the `dnsmasq_config_file` "
        "from neutron/dhcp-agent.ini.")
    return unittest.skipUnless(_dnsmasq_configured(), msg)(func)


def requires_service(service_type='http'):
    """Expect that the underlying test uses the given service metadata."""

    def factory(func):
        @functools.wraps(func)
        def wrapper(self):
            if self.service_type != service_type:
                raise unittest.SkipTest(
                    "Not the expected service type.")
            return func(self)
        return wrapper
    return factory


def get_dict(response_body):
    """Get the dict-like object from a manager response."""
    if isinstance(response_body, tuple):
        response_body = response_body[1]
    return response_body
