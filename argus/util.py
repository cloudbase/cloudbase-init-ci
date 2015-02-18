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
import subprocess
import sys

import six

from argus import config
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


class WinRemoteClient(remote_client.WinRemoteClient):
    def run_command_verbose(self, cmd):
        """Run the given command and log anything it returns."""

        LOG.info("Running command %s...", cmd)
        stdout, stderr, exit_code = self.run_remote_cmd(cmd)

        LOG.info("The command returned the output: %s", stdout)
        LOG.info("The stderr of the command was: %s", stderr)
        LOG.info("The exit code of the command was: %s", exit_code)
        return stdout


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
def run_once(func, state={}, exceptions={}):
    """A memoization decorator, whose purpose is to cache calls."""
    @six.wraps(func)
    def wrapper(*args, **kwargs):
        if func in exceptions:
            # Deliberate use of LBYL.
            six.reraise(*exceptions[func])

        try:
            return state[func]
        except KeyError:
            try:
                state[func] = result = func(*args, **kwargs)
                return result
            except Exception:
                exceptions[func] = sys.exc_info()
                raise
    return wrapper


def trap_failure(func):
    """Call pdb.set_trace when an exception occurs."""
    @six.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except BaseException:
            # TODO(cpopa): Save the original exception, since pdb will happily
            # overwrite it. This makes flake8 scream, though.
            # pylint: disable=unused-variable
            exc = sys.exc_info()  # NOQA

            LOG.exception("Exception occurred for func %s.", func)
            import pdb
            pdb.set_trace()
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
    parser.add_argument("--git-command", type=str, default=None,
                        help="Pass a git command which should be interpreted "
                             "by a recipe.")
    parser.add_argument("-p", "--pause", action="store_true",
                        help="Pause argus before doing any test.")
    parser.add_argument("--logging-format",
                        type=str, default=DEFAULT_FORMAT,
                        help="The logging format argus should use.")
    parser.add_argument("--logging-file",
                        type=str, default="argus.log",
                        help="The logging file argus should use.")
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


def get_logger(name="argus", format_string=None):
    """Obtain a new logger object.

    The `name` parameter will be the name of the logger
    and `format_string` will be the format it will
    use for logging.
    If it is not given, the the one given at command
    line will be used, otherwise the default format.
    """
    logger = logging.getLogger(name)
    opts = parse_cli()
    formatter = logging.Formatter(
        format_string or opts.logging_format or DEFAULT_FORMAT)

    if not logger.handlers:
        # If the logger wasn't obtained another time,
        # then it shouldn't have any loggers

        if opts.logging_file:
            file_handler = logging.FileHandler(opts.logging_file)
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
