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

import abc
import contextlib
import logging
import ntpath
import os
import time

import bs4
import six
from six.moves import urllib

from argus import exceptions
from argus import util

CONF = util.get_config()
LOG = util.get_logger()

__all__ = (
    'InstancePreparer',
    'WindowsInstancePreparer',
)


def _read_url(url):
    request = urllib.request.urlopen(url)
    with contextlib.closing(request) as stream:
        content = stream.read()
        if six.PY3:
            content = content.decode(errors='replace')
        return content


def _get_git_link():
    content = _read_url("http://git-scm.com/download/win")
    soup = bs4.BeautifulSoup(content)
    download_div = soup.find('div', {'class': 'callout downloading'})
    if not download_div:
        raise exceptions.CloudbaseCIError(
            "Could not find callout_downloading div.")

    for a_object in download_div.find_all('a'):
        href = a_object.get('href', '')
        if not href.endswith('.exe'):
            continue
        return href
    raise exceptions.CloudbaseCIError("git download link not found.")


@six.add_metaclass(abc.ABCMeta)
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
        stdout, stderr, return_code = self._remote_client.run_remote_cmd(cmd)
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
                LOG.error("Command %r failed while waiting for condition",
                          cmd)
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

    @abc.abstractmethod
    def wait_for_boot_completion(self):
        """Wait for the instance to finish up booting."""

    @abc.abstractmethod
    def get_installation_script(self):
        """Get the installation script for cloudbaseinit."""

    @abc.abstractmethod
    def install_cbinit(self):
        """Install the cloudbaseinit code."""

    @abc.abstractmethod
    def wait_cbinit_finalization(self):
        """Wait for the finalization of cloudbaseinit."""

    @abc.abstractmethod
    def wait_reboot(self):
        """Do a reboot and wait for the instance to be up."""

    @abc.abstractmethod
    def install_git(self):
        """Install git in the instance."""

    @abc.abstractmethod
    def sysprep(self):
        """Do the final steps after installing cloudbaseinit.

        This requires running sysprep on Windows, but on other
        platforms there might be no need for calling it.
        """

    @abc.abstractmethod
    def replace_code(self):
        """Do whatever is necessary to replace the code for cloudbaseinit."""

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
        self.install_git()

        if CONF.argus.replace_code:
            self.replace_code()

        self.sysprep()
        self.wait_reboot()
        self.wait_cbinit_finalization()
        LOG.info("Finished preparing instance %s", self._instance_id)

    if CONF.argus.debug:
        prepare = util.trap_failure(prepare)


class WindowsInstancePreparer(InstancePreparer):
    """Instance preparer for Windows machines."""

    def get_program_files(self):
        """Get the location of program files from the instance."""
        stdout, _ = self._execute('powershell "(Get-WmiObject  Win32_OperatingSystem).'
                                  'OSArchitecture"')
        architecture = stdout.strip()

        # Next, get the location.
        if architecture == '64-bit':
            location, _ = self._execute('powershell "${ENV:ProgramFiles(x86)}"')
        else:
            location, _ = self._execute('powershell "$ENV:ProgramFiles"')
        return location.strip()

    def wait_for_boot_completion(self):
        LOG.info("Waiting for boot completion")

        wait_cmd = ('powershell "(Get-WmiObject Win32_Account | '
                    'where -Property Name -contains {0}).Name"'
                    .format(CONF.argus.default_ci_username))
        return self._run_cmd_until_condition(
            wait_cmd,
            lambda stdout: stdout.strip() == CONF.argus.default_ci_username)

    def get_installation_script(self):
        """Get an insallation script for CloudbaseInit."""
        LOG.info("Retrieve an installation script for CloudbaseInit")

        cmd = ("powershell Invoke-webrequest -uri "
               "{}/installCBinit.ps1 -outfile C:\\installcbinit.ps1"
               .format(CONF.argus.resources))
        self._execute(cmd)

    def install_cbinit(self):
        """Run the installation script for CloudbaseInit."""
        LOG.info("Run the downloaded installation script")

        cmd = ('powershell "C:\\\\installcbinit.ps1 -serviceType {}"'
               .format(CONF.argus.service_type))
        self._execute(cmd)

    def install_git(self):
        """Install git in the instance."""
        LOG.info("Installing git.")

        cmd = ("powershell Invoke-webrequest -uri "
               "{}/install_git.ps1 -outfile C:\\\\install_git.ps1"
               .format(CONF.argus.resources))
        self._execute(cmd)

        git_link = _get_git_link()
        git_base = os.path.basename(git_link)
        cmd = ('powershell "C:\\install_git.ps1 {} {}"'
               .format(git_link, git_base))
        self._execute(cmd)

    def replace_code(self):
        """Replace the code of cloudbaseinit."""
        LOG.info("Replacing cloudbaseinit's code.")

        # Get the program files location.
        program_files = self.get_program_files()

        # Remove everything from the cloudbaseinit installation.
        cloudbaseinit = ntpath.join(
            program_files, "Cloudbase Solutions",
            "Cloudbase-Init",
            # TODO(cpopa): take care of this when testing Python 3.
            "Python27",
            "Lib",
            "site-packages",
            "CLOUDB~1")
        self._execute("rm -Force -Recurse {}".format(cloudbaseinit))

        # Clone the repo
        self._execute("git clone https://github.com/stackforge/"
                      "cloudbase-init C:\\cloudbaseinit")

        # Run the command provided at cli.
        opts = util.parse_cli()
        self._execute("cd C:\\cloudbaseinit; {}".format(opts.git_command))

        # Replace the code, by moving the code from cloudbaseinit
        # to the installed location.
        self._execute('powershell "Copy-Item C:\\cloudbaseinit\\cloudbaseinit '
                      '{} -Recurse"'.format(cloudbaseinit))

    def sysprep(self):
        """Prepare the instance for the actual tests, by running sysprep."""
        LOG.info("Running sysprep.")

        cmd = ("powershell Invoke-webrequest -uri "
               "{}/sysprep.ps1 -outfile 'C:\\sysprep.ps1'"
               .format(CONF.argus.resources))
        self._execute(cmd)
        self._execute('powershell C:\\sysprep.ps1')

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
            lambda out: int(out) >= int(CONF.argus.expected_plugins_count))

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

