#!/usr/bin/python

# Copyright 2014 Cloudbase Solutions Srl
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

from winrm import protocol

__all__ = (
    'WinRemoteClient',
)

WSMAN_URL = "https://{hostname}:5986/wsman"

class WinRemoteClient(object):

    def __init__(self, hostname, username, password):
        self.hostname = WSMAN_URL.format(hostname=hostname)
        self.username = username
        self.password = password

    def run_wsman_cmd(self, cmd):
        protocol.Protocol.DEFAULT_TIMEOUT = "PT3600S"

        p = protocol.Protocol(endpoint=self.hostname,
                              transport='plaintext',
                              username=self.username,
                              password=self.password)

        shell_id = p.open_shell()

        command_id = p.run_command(shell_id, cmd)
        stdout, stderr, status_code = p.get_command_output(
            shell_id, command_id)

        p.cleanup_command(shell_id, command_id)
        p.close_shell(shell_id)
        return stdout, stderr, status_code
    