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

# pylint: disable=no-name-in-module,import-error

import abc
import os
import shlex
import subprocess
import time

import novaclient.v1_1.client as nova
import six

from argus import util


LOG = util.LOG


@six.add_metaclass(abc.ABCMeta)
class BaseEnvironmentPreparer(object):
    """Base class for environment preparers.

    The environment preparers are used to modify configuration
    options on the environment where argus is executed.
    They need to know or assume location of files and also
    they are capable of restarting / stopping services.
    """

    @abc.abstractmethod
    def prepare_environment(self):
        pass

    @abc.abstractmethod
    def cleanup_environment(self):
        pass


class BaseOpenstackEnvironmentPreparer(BaseEnvironmentPreparer):
    """Base class for Openstack related environment preparers.

    This class knows how to patch a configuration file and
    how to start and stop the environment scripts / services.
    """

    def __init__(self, config_file, config_opts,
                 start_commands, stop_commands):
        self._patcher = util.ConfigurationPatcher(config_file, **config_opts)
        self._start_commands = start_commands
        self._stop_commands = stop_commands

    def _run_commands(self, commands):
        for command in commands:
            self._run_command(command)

    @staticmethod
    def _run_command(command):
        """Runs a command and returns the output.

        Params:
            command (string or list) - the command to be executed

        Return value:
            The stdout of the command as a list of string. Each string
            represents a line of the output.

        Raises:
            TypeError if type(command) not in [list, str]

        """
        if type(command) is str:
            args = shlex.split(command)
        elif type(command) is list:
            args = command
        else:
            raise TypeError(
                'Expected string or list. Got %s instead.' % type(command))
        p = subprocess.Popen(args, stdout=subprocess.PIPE)
        stdout, _ = p.communicate()
        stdout = stdout.decode()
        stdout = stdout.splitlines()
        return stdout

    @abc.abstractmethod
    def _wait_for_nova_services(self):
        pass

    @abc.abstractmethod
    def _wait_for_api(self):
        pass

    def _stop_environment(self):
        self._run_commands(self._stop_commands)

    def _start_environment(self):
        self._run_commands(self._start_commands)

    def _restart_environment(self):
        try:
            self._stop_environment()
        except Exception:
            LOG.exception("Failed stopping devstack")

        try:
            self._start_environment()
        except Exception:
            LOG.exception("Failed starting devstack")

        self._wait_for_nova_services()
        self._wait_for_api()

    def prepare_environment(self):
        LOG.info("Preparing to patch devstack configuration files.")
        self._patcher.patch()

        LOG.info("Patching done, restarting devstack services.")
        self._restart_environment()

    def cleanup_environment(self):
        LOG.info("Unpatching devstack configuration files.")
        self._patcher.unpatch()

        LOG.info("Restarting devstack.")
        self._restart_environment()


class DevstackEnvironmentPreparer(BaseOpenstackEnvironmentPreparer):
    """An environment preparer for devstack hosts.

    This preparer knows how to patch a configuration file
    and how to start and stop the devstack services which are
    running on the host.
    """
    # The following are staticmethods, disable this warning
    # since the parent methods are actual methods.
    # pylint: disable=arguments-differ

    def _wait_for_nova_services(self):
        # Wait until the nova services are up again
        LOG.info("Waiting for the services to be up again...")

        cmd = 'openstack compute service list -f csv -c State --quote none'
        while True:
            stdout = self._run_command(cmd)
            statuses = stdout[1:]
            if all(entry == "up"
                   for entry in statuses):
                break

    @staticmethod
    def _wait_for_api():
        LOG.info("Waiting for the API to be up...")

        username = os.environ['OS_USERNAME']
        password = os.environ['OS_PASSWORD']
        auth = os.environ['OS_AUTH_URL']
        tenant = os.environ['OS_TENANT_NAME']

        client = nova.Client(username, password, tenant, auth)
        while True:
            try:
                client.images.list()
                break
            except Exception:
                time.sleep(1)


class RDOEnvironmentPreparer(BaseOpenstackEnvironmentPreparer):
    """An environment preparer for RDO hosts.

    This preparer knows how to patch a configuration file
    and how to start and stop the openstack services which are
    running on the host.
    """
    # The following are staticmethods, disable this warning
    # since the parent methods are actual methods.
    # pylint: disable=arguments-differ

    def _wait_for_nova_services(self):
        # Wait until the nova services are up again
        LOG.info("Waiting for the services to be up again...")

        cmd = 'openstack compute service list -f csv -c State --quote none'
        while True:
            stdout = self._run_command(cmd)
            statuses = stdout[1:]
            if all(entry == "up"
                   for entry in statuses):
                break

    @staticmethod
    def _wait_for_api():
        LOG.info("Waiting for the API to be up...")

        username = os.environ['OS_USERNAME']
        password = os.environ['OS_PASSWORD']
        auth = os.environ['OS_AUTH_URL']
        tenant = os.environ['OS_TENANT_NAME']

        client = nova.Client(username, password, tenant, auth)
        while True:
            try:
                client.images.list()
                break
            except Exception:
                time.sleep(1)

    def _get_services(self):
        services = self._run_command("systemctl -a")
        services.extend(self._run_command("systemctl -a"))
        services = [s for s in services if s.startswith('openstack') or s.startswith('neutron')]
        services = [str(s.split()[0]) for s in services]
        return services

    def _stop_environment(self):
        services = self._get_services()
        for service in services:
            self._run_command("systemctl stop %s" % service)

    def _start_environment(self):
        services = self._get_services()
        # nova-conductor needs to be started before nova-compute
        self._run_command("systemctl start openstack-nova-conductor")
        for service in services:
            self._run_command("systemctl start %s" % service)
