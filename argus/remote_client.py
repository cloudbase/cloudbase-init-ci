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

import base64
import functools

import six
from winrm import protocol

from argus import exceptions

__all__ = (
    'WinRemoteClient',
)

WSMAN_URL = "http://{hostname}:5985/wsman"


def _base64_read_file(filepath, size=8192):
    with open(filepath, 'rb') as stream:
        reader = functools.partial(stream.read, size)
        for data in iter(reader, b''):
            encoded = base64.b64encode(data)
            if six.PY3:
                # Get a string instead.
                encoded = encoded.decode()
            yield encoded


class WinRemoteClient(object):

    def __init__(self, hostname, username, password):
        self.hostname = WSMAN_URL.format(hostname=hostname)
        self.username = username
        self.password = password

    def _run_command(self, protocol, shell_id, command):
        try:
            command_id = protocol.run_command(shell_id, command)
            stdout, stderr, exit_code = protocol.get_command_output(
                shell_id, command_id)
            if exit_code:
                raise exceptions.CloudbaseCIError(
                    "Executing command {command!r} failed with "
                    "exit code {exit_code!r} and {output}"
                    .format(command=command,
                            exit_code=exit_code,
                            output=stdout))

            return stdout, stderr, exit_code
        finally:
            protocol.cleanup_command(shell_id, command_id)

    def _run_commands(self, commands):
        protocol = self.get_protocol()
        shell_id = protocol.open_shell()

        try:
            for command in commands:
                yield self._run_command(protocol, shell_id, command)
        finally:
            protocol.close_shell(shell_id)

    def get_protocol(self):
        protocol.Protocol.DEFAULT_TIMEOUT = "PT3600S"
        return protocol.Protocol(endpoint=self.hostname,
                              transport='plaintext',
                              username=self.username,
                              password=self.password)

    def run_wsman_cmd(self, cmd):
        """Run the given remote command.

        The command will be executed on the remote underlying server.
        It will return a tuple of three elements, stdout, stderr
        and the return code of the command.
        """
        return next(self._run_commands([cmd]))

    def copy_file(self, filepath, remote_destination):
        """Copy the given filepath in the remote destination.

        The remote destination is the file name where the content
        of filepath will be written.
        """

        # TODO(cpopa): This powershell dance is a little complicated,
        # find a simpler way to send a file over a remote server,
        # without relying on OpenStack infra.
        get_string_cmd = ("[System.Text.Encoding]::UTF8.GetString("
                          "[System.Convert]::FromBase64String('{}'))")
        commands = []
        for command in _base64_read_file(filepath):
            remote_command = (
                "powershell \"{content}\" >> {remote_destination}"
                .format(content=get_string_cmd.format(command),
                        remote_destination=remote_destination))

            commands.append(remote_command)
        self._run_commands(commands)
