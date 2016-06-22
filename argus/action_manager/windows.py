# Copyright 2016 Cloudbase Solutions Srl
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

import socket
import urlparse


from argus.action_manager import base
from argus import exceptions
from argus import util
import requests
from winrm import exceptions as winrm_exceptions

LOG = util.LOG


class WindowsActionManager(base.BaseActionManager):

    def __init__(self, client, config, os_type=util.WINDOWS):
        super(WindowsActionManager, self).__init__(client, config, os_type)

    def download(self, uri, location):
        """Download the resource locatet at a specific uri in the location.

        :param uri:
            Remote url where the data is found.

        :param location:
            Path from the instance in which we should download the
            remote resouce.
        """
        LOG.debug("Downloading from %s to %s ", uri, location)
        cmd = ("Invoke-WebRequest -Uri {} "
               "-OutFile {}".format(uri, location))
        self._client.run_command_with_retry(cmd,
                                            count=util.RETRY_COUNT,
                                            delay=util.RETRY_DELAY,
                                            command_type=util.POWERSHELL)

    def download_resource(self, resource_location, location):
        """Download the resource in the specified location

        :param resource_script:
            Is relative to the /argus/resources/ directory.
        :param location:
            The location on the instance.
        """
        base_resource = self._conf.argus.resources
        if not base_resource.endswith("/"):
            base_resource = urlparse.urljoin(self._conf.argus.resources,
                                             "resources/")
        uri = urlparse.urljoin(base_resource, resource_location)
        self.download(uri, location)

    def _execute_resource_script(self, resource_location, parameters,
                                 script_type):
        """Run a resource script with with the specific parameters."""
        LOG.debug("Executing resource script %s with this parameters %s",
                  resource_location, parameters)

        if script_type == util.BAT_SCRIPT:
            script_type = util.CMD

        instance_location = r"C:\{}".format(resource_location.split('/')[-1])
        self.download_resource(resource_location, instance_location)
        cmd = "{} {}".format(instance_location, parameters)
        self._client.run_command_with_retry(cmd,
                                            count=util.RETRY_COUNT,
                                            delay=util.RETRY_DELAY,
                                            command_type=script_type)

    def execute_powershell_resource_script(self, resource_location,
                                           parameters=""):
        """Execute a powershell resource script."""
        self._execute_resource_script(
            resource_location=resource_location, parameters=parameters,
            script_type=util.POWERSHELL_SCRIPT_BYPASS)

    def execute_cmd_resource_script(self, resource_location,
                                    parameters=""):
        """Execute a .bat resource script."""
        self._execute_resource_script(resource_location=resource_location,
                                      parameters=parameters,
                                      script_type=util.BAT_SCRIPT)

    def get_installation_script(self):
        """Get instalation script for CloudbaseInit."""
        LOG.info("Retrieve an installation script for CloudbaseInit.")
        self.download_resource("windows/installCBinit.ps1",
                               r"C:\installCBinit.ps1")

    def install_cbinit(self, service_type):
        """Run the installation script for CloudbaseInit."""
        LOG.debug("Installing Cloudbase-Init ...")

        installer = "CloudbaseInitSetup_{build}_{arch}.msi".format(
            build=self._conf.argus.build,
            arch=self._conf.argus.arch
        )
        # TODO(cpopa): the service type is specific to each scenario,
        # find a way to pass it
        LOG.info("Run the downloaded installation script "
                 "using the installer %r with service %r.",
                 installer, service_type)

        parameters = '-serviceType {} -installer {}'.format(service_type,
                                                            installer)
        try:
            self.execute_powershell_resource_script(
                resource_location='windows/installCBinit.ps1',
                parameters=parameters)
        except exceptions.ArgusError:
            # This can happen for multiple reasons,
            # but one of them is the fact that the installer
            # can't be installed through WinRM on some OSes
            # for whatever reason. In this case, we're falling back
            # to use a scheduled task.
            LOG.debug("Cannot install, deploying using a scheduled task.")
            self._deploy_using_scheduled_task(installer, service_type)

    def _deploy_using_scheduled_task(self, installer, service_type):
        resource_script = 'windows/schedule_installer.bat'
        parameters = '-serviceeType {} -installer {}'.format(service_type,
                                                             installer)
        self.execute_cmd_resource_script(resource_script, parameters)

    def sysprep(self):
        resource_location = "windows/sysprep.ps1"

        cmd = r"C:\{}".format(resource_location.split('/')[-1])
        self.download_resource(resource_location, cmd)
        LOG.debug("Running %s ", cmd)
        try:
            self._client.run_remote_cmd(
                cmd, command_type=util.POWERSHELL_SCRIPT_BYPASS)
        except (socket.error, winrm_exceptions.WinRMTransportError,
                winrm_exceptions.InvalidCredentialsError,
                requests.ConnectionError, requests.Timeout):
            # After executing sysprep.ps1 the instance will reboot and
            # it is normal to have conectivity issues during that time.
            # Knowing this we have to except this kind of errors.
            # This fixes errors that stops scenarios from getting
            # created on different windows images.
            LOG.debug("Currently rebooting...")
        LOG.info("Wait for the machine to finish rebooting ...")
        self.wait_boot_completion()

    def git_clone(self, repo_url, location):
        """Clone from an remote repo to a specific location on the instance.

        :param repo_url:
            The remote repo url.
        :param location:
            Specific location on the instance.
        """
        LOG.info("Cloning from %s to %s", repo_url, location)
        cmd = "git clone {} {}".format(repo_url, location)
        self._client.run_command_with_retry(cmd,
                                            count=util.RETRY_COUNT,
                                            delay=util.RETRY_DELAY,
                                            command_type=util.CMD)

    def wait_cbinit_service(self):
        """Wait if the CloudBase Init Service to stop."""
        wait_cmd = ('(Get-Service | where -Property Name '
                    '-match cloudbase-init).Status')

        self._client.run_command_until_condition(
            wait_cmd,
            lambda out: out.strip() == 'Stopped',
            retry_count=util.RETRY_COUNT, delay=util.RETRY_DELAY,
            command_type=util.POWERSHELL)

    def check_cbinit_service(self, searched_paths=None):
        """Check if the CloudBase Init service started.

        :param searched_paths:
            Paths to files that should exist if the hearbeat patch is
            aplied.
        """
        test_cmd = 'Test-Path {}'
        check_cmds = [test_cmd.format(path) for path in searched_paths or []]
        for check_cmd in check_cmds:
            self._client.run_command_until_condition(
                check_cmd,
                lambda out: out.strip() == 'True',
                retry_count=util.RETRY_COUNT, delay=util.RETRY_DELAY,
                command_type=util.POWERSHELL)

    def wait_boot_completion(self):
        """Wait for a resonable amount of time the instance to boot."""
        LOG.info("Waiting for boot completion...")

        username = self._conf.openstack.image_username
        wait_cmd = ('(Get-WmiObject Win32_Account | '
                    'where -Property Name -contains {0}).Name'
                    .format(username))
        self._client.run_command_until_condition(
            wait_cmd,
            lambda stdout: stdout.strip() == username,
            retry_count=util.RETRY_COUNT, delay=util.RETRY_DELAY,
            command_type=util.POWERSHELL)

    def specific_prepare(self):
        """Prepare some OS specific resources."""
        # We don't have anythong specific for the base
        LOG.debug("Prepare something specific for OS Type %s", self._os_type)
