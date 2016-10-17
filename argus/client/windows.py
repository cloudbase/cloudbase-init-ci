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

try:
    import StringIO
except ImportError:
    import io as StringIO

import time

import six
from winrm import protocol

from argus.action_manager.windows import get_windows_action_manager
from argus.client import base
from argus import exceptions
from argus import util


LOG = util.get_logger()
CODEPAGE_UTF8 = 65001


def _encode(data):
    encoded = base64.b64encode(data)
    if six.PY3:
        encoded = encoded.decode()
    return encoded


def _base64_read_file(filepath, size=8192):
    with open(filepath, 'rb') as stream:
        reader = functools.partial(stream.read, size)
        for data in iter(reader, b''):
            encoded = _encode(data)
            yield encoded


class WinRemoteClient(base.BaseClient):
    """Get a remote client to a Windows instance.

    :param hostname: The IP where the client should be connected.
    :param username: The username of the client.
    :param password: The password of the remote client.
    :param transport_protocol:
        The transport for the WinRM protocol. Only HTTP and HTTPS makes
        sense.
    :param cert_pem:
        Client authentication certificate file path in PEM format.
    :param cert_key:
        Client authentication certificate key file path in PEM format.
    """
    def __init__(self, hostname, username, password,
                 transport_protocol='http',
                 cert_pem=None, cert_key=None):
        super(WinRemoteClient, self).__init__(hostname, username, password,
                                              cert_pem, cert_key)
        self._hostname = "{protocol}://{hostname}:{port}/wsman".format(
            protocol=transport_protocol,
            hostname=hostname,
            port=5985 if transport_protocol == 'http' else 5986)
        self.manager = get_windows_action_manager(self)

    @staticmethod
    def _run_command(protocol_client, shell_id, command,
                     command_type=util.POWERSHELL):
        command_id = None
        bare_command = command

        command = util.get_command(command, command_type)

        try:
            command_id = protocol_client.run_command(shell_id, command)
            stdout, stderr, exit_code = protocol_client.get_command_output(
                shell_id, command_id)
            if exit_code:
                output = "\n\n".join([out for out in (stdout, stderr) if out])
                raise exceptions.ArgusError(
                    "Executing command {command!r} with encoded Command"
                    "{encoded_command!r} failed with exit code {exit_code!r}"
                    " and output {output!r}."
                    .format(command=bare_command,
                            encoded_command=command,
                            exit_code=exit_code,
                            output=output))

            return util.sanitize_command_output(stdout), stderr, exit_code
        finally:
            protocol_client.cleanup_command(shell_id, command_id)

    def _run_commands(self, commands, commands_type=util.POWERSHELL):
        protocol_client = self._get_protocol()
        shell_id = protocol_client.open_shell(codepage=CODEPAGE_UTF8)
        try:
            results = [self._run_command(protocol_client, shell_id, command,
                                         command_type=commands_type)
                       for command in commands]
        finally:
            protocol_client.close_shell(shell_id)
        return results

    def _get_protocol(self):
        protocol.Protocol.DEFAULT_TIMEOUT = "PT3600S"
        return protocol.Protocol(endpoint=self._hostname,
                                 transport='plaintext',
                                 username=self._username,
                                 password=self._password,
                                 server_cert_validation='ignore',
                                 cert_pem=self._cert_pem,
                                 cert_key_pem=self._cert_key)

    def run_remote_cmd(self, cmd, command_type=util.POWERSHELL):
        """Run the given remote command.

        The command will be executed on the remote underlying server.
        It will return a tuple of three elements, stdout, stderr
        and the return code of the command.
        """
        return self._run_commands([cmd], command_type)[0]

    def copy_file(self, filepath, remote_destination):
        """Copy the given file-path in the remote destination.

        The remote destination is the file name where the content
        of file-path will be written.
        """

        # TODO(cpopa): This powershell dance is a little complicated,
        # find a simpler way to send a file over a remote server,
        # without relying on OpenStack infra.
        get_string_cmd = ("[System.Text.Encoding]::UTF8.GetString("
                          "[System.Convert]::FromBase64String('{}'))")
        commands = []
        for command in _base64_read_file(filepath):
            remote_command = (
                r'powershell "{content}" >> "{remote_destination}"'
                .format(content=get_string_cmd.format(command),
                        remote_destination=remote_destination))

            commands.append(remote_command)
        # NOTE(mmicu): If the command would be POWERSHELL type
        #              it will get over the 8191 char limit.
        self._run_commands(commands, commands_type=util.CMD)

    def write_file(self, data, remote_destination):
        """Copy the given data in the remote destination.

        The remote destination is the file name where the content
        of file-path will be written.
        """
        # TODO(mmicu): This powershell dance is a little complicated,
        # find a simpler way to send a file over a remote server,
        # without relying on OpenStack infra.
        get_string_cmd = ("[System.Text.Encoding]::UTF8.GetString("
                          "[System.Convert]::FromBase64String('{}'))")
        commands = []
        data = StringIO.StringIO(data)
        data.seek(0)
        content = data.read(1024)
        while content:
            remote_command = (
                "{content} >> '{remote_destination}'"
                .format(content=get_string_cmd.format(_encode(content)),
                        remote_destination=remote_destination))

            commands.append(remote_command)
            content = data.read(1024)
        self._run_commands(commands, commands_type=util.POWERSHELL)

    def read_file(self, filepath):
        """Get the content of the given file."""
        cmd = 'Get-Content "{}"'.format(filepath)
        return (self.run_command_with_retry(
            cmd, command_type=util.POWERSHELL)[0])

    def run_command(self, cmd, command_type=util.POWERSHELL):
        """Run the given command and return execution details.

        :rtype: tuple
        :returns: stdout, stderr, exit_code
        """

        return self.run_remote_cmd(cmd, command_type=command_type)

    def run_command_verbose(self, cmd, command_type=util.POWERSHELL):
        """Run the given command and log anything it returns.

        Do this with retrying support.

        :rtype: string
        :returns: stdout
        """
        result = self.run_command_with_retry(cmd, command_type=command_type)
        stdout, stderr, exit_code = result
        LOG.info("The command returned the output: %s", stdout)
        LOG.info("The stderr of the command was: %s", stderr)
        LOG.info("The exit code of the command was: %s", exit_code)
        return stdout

    def run_command_with_retry(self, cmd, count=util.RETRY_COUNT,
                               delay=util.RETRY_DELAY,
                               command_type=util.POWERSHELL):
        """Run the given `cmd` until succeeds.

        :param cmd:
            A string, representing a command which needs to
            be executed on the underlying remote client.
        :param count:
            The number of retries which this function has.
            If the value is ``None``, then the function will retry *forever*.
        :param delay:
            The number of seconds to sleep when retrying a command.

        :rtype: tuple
        :returns: stdout, stderr, exit_code
        """

        # Countdown normalization.
        if not count or count < 0:
            count = 0

        while True:
            try:
                return self.run_command(cmd, command_type=command_type)
            except Exception as exc:  # pylint: disable=broad-except
                LOG.debug("Command failed with %r.", exc)
                # A negative `count` means no count at all.
                if count >= 0:
                    count -= 1
                if count == 0:
                    raise exceptions.ArgusTimeoutError(
                        "Command {!r} failed too many times."
                        .format(cmd))
                LOG.debug("Retrying...")
                time.sleep(delay)

    def run_command_until_condition(self, cmd, cond,
                                    retry_count=util.RETRY_COUNT,
                                    delay=util.RETRY_DELAY,
                                    command_type=util.POWERSHELL):
        """Run the given `cmd` until a condition `cond` occurs.

        :param cond:
            A callable which receives the standard output returned by
            executing the command. It should return a boolean value,
            which tells to this function to stop execution.
        :raises:
            `ArgusCLIError` if there is output found in the standard error.

        This method uses and behaves like `run_command_with_retry` but
        with an additional condition parameter.
        """

        # countdown normalization
        if not retry_count or retry_count < 0:
            retry_count = 0

        while True:
            try:
                stdout, stderr, exit_code = self.run_command(
                    cmd, command_type=command_type)
            except Exception as exc:  # pylint: disable=broad-except
                LOG.debug("Command failed with %r.", exc)
            else:
                if stderr and exit_code:
                    raise exceptions.ArgusCLIError(
                        ("Executing command {!r} failed with {!r}"
                         " and exit code {}.")
                        .format(cmd, stderr, exit_code))
                elif cond(stdout):
                    return
                else:
                    LOG.debug("Condition not met, retrying...")

            if retry_count > 0:
                retry_count -= 1
                LOG.debug("Retrying...")
                time.sleep(delay)
            else:
                raise exceptions.ArgusTimeoutError(
                    "Command {!r} failed too many times."
                    .format(cmd))
