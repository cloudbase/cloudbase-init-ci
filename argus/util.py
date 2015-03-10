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

import argparse
import base64
import importlib
import itertools
import logging
import pkgutil
import socket
import subprocess
import sys
import time

import six

from argus import config
from argus import exceptions
from argus import remote_client


__all__ = (
    'WinRemoteClient',
    'decrypt_password',
    'run_once',
    'get_resource',
    'cached_property',
    'load_qualified_object',
)

DEFAULT_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
DEFAULT_LOG_FILE = 'argus.log'


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

        :rtype: string
        :returns: stdout
        """
        stdout, stderr, exit_code = self.run_command(cmd)
        LOG.info("The command returned the output: %s", stdout)
        LOG.info("The stderr of the command was: %s", stderr)
        LOG.info("The exit code of the command was: %s", exit_code)
        return stdout

    def run_command_with_retry(self, cmd, retry_count=None,
                               retry_count_interval=5):
        """Run the given `cmd` until succeeds.

        :param cmd:
            A string, representing a command which needs to
            be executed on the underlying remote client.
        :param retry_count:
            The number of retries which this function has.
            If the value is ``None``, then the function will retry *forever*.
        :param retry_count_interval:
            The number of seconds to sleep when retrying a command.

        :returns: stdout, stderr, exit_code
        :rtype: tuple
        """
        count = 0
        while True:
            try:
                return self.run_command(cmd)
            except Exception as exc:  # pylint: disable=broad-except
                LOG.debug("Command failed with '%s'.\nRetrying...", exc)
                count += 1
                if retry_count and count >= retry_count:
                    raise exceptions.ArgusTimeoutError(
                        "Command {!r} failed too many times."
                        .format(cmd))
                time.sleep(retry_count_interval)

    def run_command_until_condition(self, cmd, cond, retry_count=None,
                                    retry_count_interval=5):
        """Run the given `cmd` until a condition *cond* occurs.

        :param cmd:
            A string, representing a command which needs to
            be executed on the underlying remote client.
        :param cond:
            A callable which receives the standard output returned by
            executing the command. It should return a boolean value,
            which tells to this function to stop execution.
        :param retry_count:
            The number of retries which this function
            has until a successful run.
            If the value is ``None``, then the function will retry *forever*.
        :param retry_count_interval:
            The number of seconds to sleep when retrying a command.
        """
        while True:
            stdout, stderr, _ = self.run_command_with_retry(
                cmd, retry_count=retry_count,
                retry_count_interval=retry_count_interval)
            if stderr:
                raise exceptions.ArgusCLIError(
                    "Executing command {!r} failed with {!r}."
                    .format(cmd, stderr))
            elif cond(stdout):
                break
            else:
                LOG.debug("Condition not met.")
                time.sleep(retry_count_interval)


def get_local_ip():
    """Get the current machine's IP."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.connect(("google.com", 0))
    return sock.getsockname()[0]


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


class with_retry(object):  # pylint: disable=invalid-name
    """A decorator that will retry function calls until success."""

    def __init__(self, tries=5, delay=1):
        self.tries = tries
        self.delay = delay

    def __call__(self, func):
        @six.wraps(func)
        def wrapper(*args, **kwargs):
            while True:
                try:
                    return func(*args, **kwargs)
                except Exception as exc:
                    self.tries -= 1
                    if self.tries <= 0:
                        raise
                    LOG.error("%s while calling %s", exc, func)
                    time.sleep(self.delay)
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
        instance.__dict__[self.name] = result = self.func(instance)
        return result


def parse_cli():
    """Parse the command line and return an object with the given options."""
    parser = argparse.ArgumentParser()
    parser.add_argument('--failfast', action='store_true',
                        default=False,
                        help='Fail the tests on the first failure.')
    parser.add_argument('--conf', type=str, required=True,
                        help="Give a path to the argus conf. "
                             "It should be an .ini file format "
                             "with a section called [argus].")
    parser.add_argument("--patch-install", metavar="URL",
                        help='Pass a link that points *directly* to a '
                             'zip file containing the installed version. '
                             'The content will just replace the files.')
    parser.add_argument("--git-command", type=str, default=None,
                        help="Pass a git command which should be interpreted "
                             "by a recipe.")
    parser.add_argument("-p", "--pause", action="store_true",
                        help="Pause argus before doing any test.")
    parser.add_argument("--test-os-types",
                        type=str, nargs="*",
                        help="Test only those scenarios with these OS types. "
                             "By default, all scenarios are executed. "
                             "For instance, to run only the Windows and "
                             "FreeBSD scenarios, use "
                             "`--test-os-types Windows,FreeBSD`")
    parser.add_argument("--test-scenario-type",
                        type=str,
                        help="Test only the scenarios with this type. "
                             "The type can be `smoke` or `deep`. By default, "
                             "all scenarios types are executed.")
    parser.add_argument("-o", "--instance-output",
                        metavar="DIRECTORY",
                        help="Save the instance console output "
                             "content in this path. If this is given, "
                             "it can be reused for other files as well.")
    opts = parser.parse_args()
    return opts


@run_once
def get_config():
    """Get the argus config object."""
    opts = parse_cli()
    return config.ConfigurationParser(opts.conf).conf


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

        stdout_handler = logging.StreamHandler(sys.stdout)
        stdout_handler.setFormatter(formatter)
        logger.addHandler(stdout_handler)

    logger.setLevel(logging.DEBUG)
    return logger


def load_qualified_object(obj):
    """Load a qualified object name.

    The name must be in the format module:qualname syntax.
    """
    mod_name, has_attrs, attrs = obj.partition(":")
    obj = module = importlib.import_module(mod_name)

    if has_attrs:
        parts = attrs.split(".")
        obj = module
        for part in parts:
            obj = getattr(obj, part)
    return obj


class ProxyLogger(object):
    """Proxy class for the logging object.

    This comes in hand when using argus as a library,
    so there is no need to provide required CLI arguments,
    just to import argus.util.
    """

    def __init__(self):
        self._logger = None

    def __getattr__(self, attr):
        # single instantiation on access only
        if not self._logger:
            self._logger = get_logger()
        obj = getattr(self._logger, attr)
        self.__dict__[attr] = obj
        return obj


class ConfigurationPatcher(object):
    """Simple configuration patcher for .ini style configs.

    This class can be used to modify values of a configuration
    file with other predefined options. It also has support
    for reverting the changes.

    >>> patcher = ConfigurationPatcher('a.ini', DEFAULT={'a': '1'})
    >>> patcher.patch() # the file was modified
    >>> patcher.unpatch() # the file is as the original

    It also supports context management protocol:

    >>> with patcher: # the file is modified
        ...
    # the file was unpatched
    >>>
    """

    def __init__(self, config_file, **opts):
        self._config_file = config_file
        self._opts = opts
        self._original_content = None

    def patch(self):
        with open(self._config_file) as stream:
            self._original_content = stream.read()

        parser = six.moves.configparser.ConfigParser()
        parser.read(self._config_file)
        for section in itertools.chain(parser.sections(), ['DEFAULT']):
            if section in self._opts:
                # Needs to be patched
                opts = self._opts[section]
                for opt, value in opts.items():
                    LOG.info("Patching file %s on section %r, with "
                             "entry %s=%s",
                             self._config_file, section, opt, value)

                    parser.set(section, opt, str(value))
        with open(self._config_file, 'w') as stream:
            parser.write(stream)

    def unpatch(self):
        with open(self._config_file, 'w') as stream:
            stream.write(self._original_content)

    def __enter__(self):
        self.patch()
        return self

    def __exit__(self, exc_type, exc_value, exc_tb):
        self.unpatch()


LOG = ProxyLogger()
