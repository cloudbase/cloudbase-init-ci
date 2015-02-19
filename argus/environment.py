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

import abc
import shlex
import subprocess

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


class DevstackEnvironmentPreparer(BaseEnvironmentPreparer):
    """An environment preparer for devstack hosts.

    This preparer knows how to patch a configuration file
    and how to start and stop the devstack services which are
    running on the host.
    """

    def __init__(self, config_file, config_opts,
                 start_commands, stop_commands):
        self._patcher = util.ConfigurationPatcher(config_file, **config_opts)
        self._start_commands = start_commands
        self._stop_commands = stop_commands

    @staticmethod
    def _run_commands(commands):
        for command in commands:
            args = shlex.split(command)
            subprocess.call(args, shell=False)

    @staticmethod
    def _wait_for_services():
        # Wait until the services are up again
        LOG.info("Waiting for the services to be up again...")

        command = [
            "openstack", "compute", "service", "list",
            "-f", "csv", "-c", "State", "--quote", "none"
        ]
        while True:
            popen = subprocess.Popen(command, stdout=subprocess.PIPE)
            stdout, _ = popen.communicate()
            stdout = stdout.decode()
            # The first one is the column
            statuses = stdout.splitlines()[1:]
            if all(entry == "up"
                   for entry in statuses):
                break

    def _stop_devstack(self):
        self._run_commands(self._stop_commands)

    def _start_devstack(self):
        self._run_commands(self._start_commands)

    def _restart_devstack(self):
        try:
            self._stop_devstack()
        except Exception:
            LOG.exception("Failed stopping devstack")

        try:
            self._start_devstack()
        except Exception:
            LOG.exception("Failed starting devstack")

        self._wait_for_services()

    def prepare_environment(self):
        LOG.info("Preparing to patch devstack configuration files.")
        self._patcher.patch()

        LOG.info("Patching done, restarting devstack services.")
        self._restart_devstack()

    def cleanup_environment(self):
        LOG.info("Unpatching devstack configuration files.")
        self._patcher.unpatch()

        LOG.info("Restarting devstack.")
        self._restart_devstack()
