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

import multiprocessing
from multiprocessing import pool
import time

import six
from winrm import protocol

from argus.action_manager.windows import get_windows_action_manager
from argus.client import base
from argus import config as argus_config
from argus import exceptions
from argus import log as argus_log
from argus import util


LOG = argus_log.LOG
CONFIG = argus_config.CONFIG
CODEPAGE_UTF8 = 65001
THREADS = 1
BUFFER_SIZE = 1024


def _encode(data):
    encoded = base64.b64encode(data)
    if six.PY3:
        encoded = encoded.decode()
    return encoded


def _base64_read_file(filepath, size=BUFFER_SIZE):
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
    def exec_with_retry(cmd):
        return util.exec_with_retry(cmd, CONFIG.argus.retry_count,
                                    CONFIG.argus.retry_delay)

    @staticmethod
    def _run_command(protocol_client, shell_id, command,
                     command_type=util.POWERSHELL,
                     upper_timeout=CONFIG.argus.upper_timeout):
        command_id = None
        bare_command = command
        thread_pool = pool.ThreadPool(processes=THREADS)

        command = util.get_command(command, command_type)

        try:
            command_id = protocol_client.run_command(shell_id, command)

            result = thread_pool.apply_async(
                protocol_client.get_command_output,
                args=(shell_id, command_id))
            stdout, stderr, exit_code = result.get(
                timeout=upper_timeout)
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
        except multiprocessing.TimeoutError:
            raise exceptions.ArgusTimeoutError(
                "The command '{cmd}' has timed out.".format(cmd=bare_command))
        finally:
            thread_pool.terminate()
            protocol_client.cleanup_command(shell_id, command_id)

    def _run_commands(self, commands, commands_type=util.POWERSHELL,
                      upper_timeout=CONFIG.argus.upper_timeout):
        protocol_client = self._get_protocol()
        shell_id = self.exec_with_retry(lambda: (protocol_client.open_shell(
            codepage=CODEPAGE_UTF8)))

        try:
            results = [self._run_command(protocol_client, shell_id, command,
                                         commands_type, upper_timeout)
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

    def run_remote_cmd(self, cmd, command_type=util.POWERSHELL,
                       upper_timeout=CONFIG.argus.upper_timeout):
        """Run the given remote command.

        The command will be executed on the remote underlying server.
        It will return a tuple of three elements, stdout, stderr
        and the return code of the command.
        """
        return self._run_commands([cmd], command_type,
                                  upper_timeout=upper_timeout)[0]

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
                "{content} >> '{remote_destination}'"
                .format(content=get_string_cmd.format(command),
                        remote_destination=remote_destination))

            commands.append(remote_command)
        self._run_commands(commands, commands_type=util.POWERSHELL)

    def write_file(self, data, remote_destination):
        """Copy the given data in the remote destination.

        The remote destination is the file name where the content
        of file-path will be written.

        .. warning::
           This will transfer binary data.
        """
        decode_command = ("([System.Convert]::FromBase64String('{}'))")
        write_command = ("Add-Content -Encoding Byte -Value {content}"
                         " -Path '{remote_destination}'")
        commands = []
        data = StringIO.StringIO(data)
        data.seek(0)
        content = data.read(BUFFER_SIZE)
        while content:
            remote_command = write_command.format(
                content=decode_command.format(_encode(content)),
                remote_destination=remote_destination)

            commands.append(remote_command)
            content = data.read(BUFFER_SIZE)
        self._run_commands(commands, commands_type=util.POWERSHELL,
                           upper_timeout=CONFIG.argus.io_upper_timeout)

    def read_file(self, filepath):
        """Get the content of the given file."""
        cmd = 'Get-Content "{}"'.format(filepath)
        return (self.run_command_with_retry(
            cmd, command_type=util.POWERSHELL,
            upper_timeout=CONFIG.argus.io_upper_timeout)[0])

    def run_command(self, cmd, command_type=util.POWERSHELL,
                    upper_timeout=CONFIG.argus.upper_timeout):
        """Run the given command and return execution details.

        :rtype: tuple
        :returns: stdout, stderr, exit_code
        """

        return self.run_remote_cmd(cmd, command_type=command_type,
                                   upper_timeout=upper_timeout)

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

    def run_command_with_retry(self, cmd, count=CONFIG.argus.retry_count,
                               delay=CONFIG.argus.retry_delay,
                               command_type=util.POWERSHELL,
                               upper_timeout=CONFIG.argus.upper_timeout):
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
                return self.run_command(cmd, command_type=command_type,
                                        upper_timeout=upper_timeout)
            except Exception as exc:  # pylint: disable=broad-except
                LOG.debug("Command failed with %r.", exc)
                # A negative `count` means no count at all.
                if count >= 0:
                    count -= 1
                if count == 0:
                    raise exceptions.ArgusTimeoutError(
                        "Command {!r} failed too many times."
                        .format(cmd))
                LOG.debug("Retrying '%s'", cmd)
                time.sleep(delay)

    def run_command_until_condition(self, cmd, cond,
                                    retry_count=CONFIG.argus.retry_count,
                                    delay=CONFIG.argus.retry_delay,
                                    command_type=util.POWERSHELL,
                                    upper_timeout=CONFIG.argus.upper_timeout):
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
                    cmd, command_type=command_type,
                    upper_timeout=upper_timeout)
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
                LOG.debug("Retrying '%s'", cmd)
                time.sleep(delay)
            else:
                raise exceptions.ArgusTimeoutError(
                    "Command {!r} failed too many times."
                    .format(cmd))
