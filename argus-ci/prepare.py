# Copyright 2014 Cloudbase-init
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
"""Instance preparing utilities."""

import time

from tempest import config
from tempest.openstack.common import log as logging

from argus import exceptions

CONF = config.CONF
LOG = logging.getLogger('cbinit')

__all__ = ('InstancePreparer', )


class InstancePreparer(object):
    """Handle instance preparing.

    The method :meth:`~prepare` does all the necessary work for
    preparing a new instance. The executed steps are:

    * wait for boot completion.
    * get an install script for CloudbaseInit
    * installs CloudbaseInit
    * waits for the finalization of the installation.
    """

    def __init__(self, instance_id, servers_client, remote_client):
        self._servers_client = servers_client
        self._instance_id = instance_id
        self._remote_client = remote_client

    def _execute(self, cmd):
        """Execute the given command and fail when the command fails."""
        stdout, stderr, return_code = self._remote_client.run_wsman_cmd(cmd)
        if return_code:
            raise exceptions.CloudbaseCIError(
                "Command {command!r} failed with "
                "return code {return_code!r}"
                .format(command=cmd,
                        return_code=return_code))
        return stdout, stderr

    def _run_cmd_until_condition(self, cmd, cond, retry_count=None,
                                 retry_count_interval=5):
        """Run the given `cmd` until a condition *cond* occurs.

        :param cmd:
            A string, representing a command which needs to
            be executed on the underlying remote client.
        :param cond:
            A callable which receives the stdout returned by
            executing the command. It should return a boolean value,
            which tells to this function to stop execution.
        :param retry_count:
            The number of retries which this function has.
            If the value is ``None``, then the function will run *forever*.
        :param retry_count_interval:
            The number of seconds to sleep when retrying a command.
        """
        count = 0
        while True:
            try:
                std_out, std_err = self._execute(cmd)
            except Exception:
                LOG.exception("Command {!r} failed while waiting for condition"
                              .format(cmd))
                count += 1
                if retry_count and count >= retry_count:
                    raise exceptions.CloudbaseTimeoutError(
                        "Command {!r} failed too many times."
                        .format(cmd))
                time.sleep(retry_count_interval)
            else:
                if std_err:
                    raise exceptions.CloudbaseCLIError(
                        "Executing command {!r} failed with {!r}"
                        .format(cmd, std_err))
                elif cond(std_out):
                    break
                else:
                    time.sleep(retry_count_interval)


    def wait_for_boot_completion(self):
        LOG.info("Waiting for boot completion")

        wait_cmd = ('powershell "(Get-WmiObject Win32_Account | '
                    'where -Property Name -contains {0}).FullName"'
                    .format(CONF.cbinit.created_user))
        return self._run_cmd_until_condition(
            wait_cmd,
            lambda stdout: stdout.strip() == CONF.cbinit.default_ci_username)

    def get_installation_script(self):
        """Get an insallation script for CloudbaseInit."""
        LOG.info("Retrieve an installation script for CloudbaseInit")

        cmd = ("powershell Invoke-webrequest -uri "
               "{!r}-outfile 'C:\\\\installcbinit.ps1'"
               .format(CONF.cbinit.install_script_url))
        self._execute(cmd)

    def install_cbinit(self):
        """Run the installation script for CloudbaseInit."""
        LOG.info("Run the downloaded installation script")

        cmd = ('powershell "C:\\\\installcbinit.ps1 -newCode %s '
               '-serviceType %s"' % (CONF.cbinit.replace_code,
                                     CONF.cbinit.service_type))
        self._execute(cmd)

    def wait_cbinit_finalization(self):
        """Wait for the finalization of CloudbaseInit.

        The function waits until all the plugins have been executed.
        """
        LOG.info("Waiting for the finalization of CloudbaseInit execution")

        key = ('HKLM:SOFTWARE\\Wow6432Node\\Cloudbase` '
               'Solutions\\Cloudbase-init\\{0}\\Plugins'
               .format(self._instance_id))
        wait_cmd = 'powershell (Get-Item %s).ValueCount' % key

        self._run_cmd_until_condition(
            wait_cmd,
            lambda out: int(out) >= int(CONF.cb_init.expected_plugins_count))

    def wait_reboot(self):
        """Do a reboot and wait until the instance is up."""

        LOG.info('Waiting for server status SHUTOFF because of sysprep')
        self._servers_client.wait_for_server_status(
            server_id=self._instance_id,
            status='SHUTOFF',
            extra_timeout=600)

        self._servers_client.start(self._instance_id)

        LOG.info('Waiting for server status ACTIVE')
        self._servers_client.wait_for_server_status(
            server_id=self._instance_id,
            status='ACTIVE')

    def prepare(self):
        """Prepare the underlying instance.

        The following operations will be executed:

        * wait for boot completion
        * get an installation script for CloudbaseInit
        * install CloudbaseInit by running the previously downloaded file.
        * wait until the instance is up and running.
        """
        LOG.info("Preparing instance %s", self._instance_id)
        self.wait_for_boot_completion()
        self.get_installation_script()
        self.install_cbinit()
        self.wait_reboot()
        self.wait_cbinit_finalization()
        LOG.info("Finished preparing instance %s", self._instance_id)
