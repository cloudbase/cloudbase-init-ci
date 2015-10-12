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
import collections
import contextlib
import logging
import os
import pkgutil
import random
import socket
import struct
import subprocess
import sys
import time

import six

from argus import config
from argus import exceptions
from argus import remote_client


RETRY_COUNT = 15
RETRY_DELAY = 10

__all__ = (
    'WinRemoteClient',
    'decrypt_password',
    'get_config',
    'get_logger',
    'get_resource',
    'cached_property',
    'run_once',
    'rand_name',
    'get_public_keys',
    'get_certificate',
)

DEFAULT_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
DEFAULT_LOG_FILE = 'argus.log'

NETWORK_KEYS = [
    "mac",
    "address",
    "address6",
    "gateway",
    "gateway6",
    "netmask",
    "netmask6",
    "dns",
    "dns6",
    "dhcp"
]


class WinRemoteClient(remote_client.WinRemoteClient):

    def run_command(self, cmd):
        """Run the given command and return execution details.

        :rtype: tuple
        :returns: stdout, stderr, exit_code
        """

        LOG.info("Running command %s...", cmd)
        return self.run_remote_cmd(cmd)

    def run_command_verbose(self, cmd):
        """Run the given command and log anything it returns.

        Do this with retrying support.

        :rtype: string
        :returns: stdout
        """
        stdout, stderr, exit_code = self.run_command_with_retry(cmd)
        LOG.info("The command returned the output: %s", stdout)
        LOG.info("The stderr of the command was: %s", stderr)
        LOG.info("The exit code of the command was: %s", exit_code)
        return stdout

    def run_command_with_retry(self, cmd, count=RETRY_COUNT,
                               delay=RETRY_DELAY):
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
                return self.run_command(cmd)
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

    def run_command_until_condition(self, cmd, cond, retry_count=RETRY_COUNT,
                                    delay=RETRY_DELAY):
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
                stdout, stderr, _ = self.run_command(cmd)
            except Exception as exc:  # pylint: disable=broad-except
                LOG.debug("Command failed with %r.", exc)
            else:
                if stderr:
                    raise exceptions.ArgusCLIError(
                        "Executing command {!r} failed with {!r}."
                        .format(cmd, stderr))
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


def get_local_ip():
    """Get the current machine's IP."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.connect(("google.com", 0))
    return sock.getsockname()[0]


def next_ip(ip, step=1):
    """Return the next IP address of the given one.

    :type step: int
    :param step: offset adjustment value
    """
    # Convert IP address to unsigned long.
    data_type = "!L"
    number = struct.unpack(data_type, socket.inet_aton(ip))[0]
    # Get the next one.
    number += step
    # Convert it back and return the ascii value.
    return socket.inet_ntoa(struct.pack(data_type, number))


def cidr2netmask(cidr):
    """Return the net mask deduced from the CIDR format network address."""
    mask_length = int(cidr.split("/")[1])
    mask_bits = "1" * mask_length + "0" * (32 - mask_length)
    mask_number = int(mask_bits, 2)
    mask_bytes = struct.pack("!L", mask_number)
    return socket.inet_ntoa(mask_bytes)


def decrypt_password(private_key, password):
    """Decode password and unencrypts it with private key.

    Requires openssl binary available in the path.
    """
    unencoded = base64.b64decode(password)
    cmd = ['openssl', 'rsautl', '-decrypt', '-inkey', private_key]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE)
    out, err = proc.communicate(unencoded)
    proc.stdin.close()
    if proc.returncode:
        raise Exception("Failed calling openssl with error: {!r}."
                        .format(err))
    return out


# pylint: disable=dangerous-default-value
def run_once(func, state={}, errors={}):
    """A memoization decorator, whose purpose is to cache calls."""
    @six.wraps(func)
    def wrapper(*args, **kwargs):
        if func in errors:
            # Deliberate use of LBYL.
            six.reraise(*errors[func])

        try:
            return state[func]
        except KeyError:
            try:
                state[func] = result = func(*args, **kwargs)
                return result
            except Exception:
                errors[func] = sys.exc_info()
                raise
    return wrapper


def get_resource(resource):
    """Get the given resource from the list of known resources."""
    return pkgutil.get_data('argus.resources', resource)


class cached_property(object):  # pylint: disable=invalid-name
    """A property which caches the result on access."""

    def __init__(self, func, name=None):
        self.func = func
        self.name = name or func.__name__

    def __get__(self, instance, klass=None):
        if instance is None:
            return self
        instance.__dict__[self.name] = result = self.func(instance)
        return result


@run_once
def get_config():
    """Get the argus config object.

    Looks for a file called argus.conf in the working directory.
    If the file is not found it looks for it in /etc/argus/
    """
    if os.path.isfile('argus.conf'):
        config_file = 'argus.conf'
    else:
        config_file = '/etc/argus/argus.conf'
    return config.ConfigurationParser(config_file).conf


def get_logger(name="argus",
               format_string=DEFAULT_FORMAT,
               logging_file=DEFAULT_LOG_FILE):
    """Obtain a new logger object.

    The `name` parameter will be the name of the logger and `format_string`
    will be the format it will use for logging. `logging_file` is a file
    where the messages will be written.
    """
    logger = logging.getLogger(name)
    formatter = logging.Formatter(format_string)

    if not logger.handlers:
        # If the logger wasn't obtained another time,
        # then it shouldn't have any loggers

        if logging_file:
            file_handler = logging.FileHandler(logging_file, delay=True)
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)

    logger.setLevel(logging.DEBUG)
    return logger


def rand_name(name=''):
    randbits = str(random.randint(1, 0x7fffffff))
    if name:
        return name + '-' + randbits
    else:
        return randbits


@contextlib.contextmanager
def restore_excepthook():
    """Context manager used to preserve the original except hook.

    *tempest* sets its own except hook, which will log the error
    using the tempest logger. Unfortunately, we are not using
    the tempest logger, so any uncaught error goes into nothingness.
    So just reset the excepthook to the original.
    """
    # pylint: disable=redefined-outer-name,reimported
    import sys
    original = sys.excepthook
    try:
        yield
    finally:
        sys.excepthook = original


def get_namedtuple(name, members, values):
    nt_class = collections.namedtuple(name, members)
    return nt_class(*values)


def get_public_keys():
    return get_resource("public_keys").splitlines()


def get_certificate():
    return get_resource("certificate")


LOG = get_logger()

_BUILDS = ["Beta", "Stable", "test"]
_ARCHES = ["x64", "x86"]
BUILDS = get_namedtuple("BUILDS", _BUILDS, _BUILDS)
ARCHES = get_namedtuple("ARCHES", _ARCHES, _ARCHES)
