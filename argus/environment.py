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
import re
import shlex
import subprocess
import time

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
                 start_commands=None, stop_commands=None,
                 list_services_commands=None, filter_services_regexes=None,
                 start_service_command=None, stop_service_command=None):
        self._patcher = util.ConfigurationPatcher(config_file, **config_opts)
        self._start_commands = start_commands
        self._stop_commands = stop_commands
        self._list_services_commands = list_services_commands
        self._filter_services_regexes = filter_services_regexes
        self._start_service_command = start_service_command
        self._stop_service_command = stop_service_command

    def _run_commands(self, commands):
        for command in commands:
            self._run_command(command)

    @staticmethod
    def _run_command(command):
        """Runs a command and returns the output.

        :param str command: The command to be executed
        :return: The lines of the stdout
        :rtype: list of strings
        """
        args = shlex.split(command)
        p = subprocess.Popen(args, stdout=subprocess.PIPE)
        stdout, _ = p.communicate()
        stdout = stdout.decode()
        lines = stdout.splitlines()
        return lines

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

        while True:
            try:
                subprocess.check_call(shlex.split('openstack image list'))
                subprocess.check_call(shlex.split('openstack server list'))
                break
            except subprocess.CalledProcessError:
                time.sleep(1)

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


class RDOEnvironmentPreparer(BaseOpenstackEnvironmentPreparer):
    """An environment preparer for RDO hosts.

    This preparer knows how to patch a configuration file
    and how to start and stop the openstack services which are
    running on the host.
    """

    def _get_services(self):
        services = self._list_services()
        services = self._filter_services(services)
        return services

    def _list_services(self):
        services = []
        for list_services_command in self._list_services_commands:
            services.extend(self._run_command(list_services_command))
        services = list(set(services))
        return services

    def _filter_services(self, services):
        filtered = []
        for filter_services_regex in self._filter_services_regexes:
            regex = re.compile(filter_services_regex)
            for service in services:
                r = regex.search(service)
                if r:
                    filtered.append(r.group(1))
        filtered = list(set(filtered))
        return filtered

    def _stop_environment(self):
        services = self._get_services()
        for service in services:
            self._run_command(self._stop_service_command % service)

    def _start_environment(self):
        services = self._get_services()
        # nova-conductor needs to be started before nova-compute
        self._run_command(
            self._start_service_command % "openstack-nova-conductor")
        for service in services:
            self._run_command(self._start_service_command % service)
