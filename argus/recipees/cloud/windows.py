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

"""Windows cloudbaseinit recipees."""

import contextlib
import ntpath
import os

import bs4
import six
from six.moves import urllib  # pylint: disable=import-error

from argus import exceptions
from argus.recipees.cloud import base
from argus import util

CONF = util.get_config()
LOG = util.get_logger()
# escaped characters for powershell paths
ESC = "( )"

__all__ = (
    'WindowsCloudbaseinitRecipee',
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
        raise exceptions.ArgusError(
            "Could not find callout_downloading div.")

    for a_object in download_div.find_all('a'):
        href = a_object.get('href', '')
        if not href.endswith('.exe'):
            continue
        return href
    raise exceptions.ArgusError("git download link not found.")


class WindowsCloudbaseinitRecipee(base.BaseCloudbaseinitRecipee):
    """Recipee for preparing a Windows instance."""

    def get_cbinit_dir(self):
        """Get the location of cloudbase-init from the instance."""
        stdout, _ = self._execute(
            'powershell "(Get-WmiObject  Win32_OperatingSystem).'
            'OSArchitecture"')
        architecture = stdout.strip()

        # Next, get the location.
        locations = [self._execute('powershell "$ENV:ProgramFiles"')[0]]
        if architecture == '64-bit':
            location, _ = self._execute(
                'powershell "${ENV:ProgramFiles(x86)}"')
            locations.append(location)

        for location in locations:
            # preprocess the path
            location = _location = location.strip()
            for char in ESC:
                _location = _location.replace(char, "`{}".format(char))
            # test its existence
            status = self._execute(
                'powershell Test-Path "{}\\Cloudbase` Solutions"'.format(
                    _location))[0].strip().lower()
            # return the path to the cloudbase-init installation
            if status == "true":
                return ntpath.join(
                    location,
                    "Cloudbase Solutions",
                    "Cloudbase-Init"
                )

    def wait_for_boot_completion(self):
        LOG.info("Waiting for boot completion")

        wait_cmd = ('powershell "(Get-WmiObject Win32_Account | '
                    'where -Property Name -contains {0}).Name"'
                    .format(self._image.default_ci_username))
        return self._run_cmd_until_condition(
            wait_cmd,
            lambda stdout: stdout.strip() == self._image.default_ci_username)

    def get_installation_script(self):
        """Get an insallation script for CloudbaseInit."""
        LOG.info("Retrieve an installation script for CloudbaseInit")

        cmd = ("powershell Invoke-webrequest -uri "
               "{}/windows/installCBinit.ps1 -outfile C:\\installcbinit.ps1"
               .format(CONF.argus.resources))
        self._execute(cmd)

    def install_cbinit(self):
        """Run the installation script for CloudbaseInit."""
        LOG.info("Run the downloaded installation script")

        cmd = ('powershell "C:\\\\installcbinit.ps1 -serviceType {}"'
               .format(self._service_type))
        self._execute(cmd)

    def install_git(self):
        """Install git in the instance."""
        LOG.info("Installing git.")

        cmd = ("powershell Invoke-webrequest -uri "
               "{}/windows/install_git.ps1 -outfile C:\\\\install_git.ps1"
               .format(CONF.argus.resources))
        self._execute(cmd)

        git_link = _get_git_link()
        git_base = os.path.basename(git_link)
        cmd = ('powershell "C:\\install_git.ps1 {} {}"'
               .format(git_link, git_base))
        self._execute(cmd)

    def replace_code(self):
        """Replace the code of cloudbaseinit."""
        opts = util.parse_cli()
        if not opts.git_command:
            # Nothing to replace.
            return

        LOG.info("Replacing cloudbaseinit's code.")

        LOG.info("Getting cloudbase-init location.")
        # Get the program files location.
        cbinit_dir = self.get_cbinit_dir()

        # Remove everything from the cloudbaseinit installation.
        LOG.info("Removing recursively cloudbaseinit.")
        cloudbaseinit = ntpath.join(
            cbinit_dir,
            # TODO(cpoieana): Take care of this when testing Python 3.
            # Handle it with the switching between Python versions patch.
            "Python27",
            "Lib",
            "site-packages",
            "cloudbaseinit")
        self._execute('rmdir "{}" /S /q'.format(cloudbaseinit))

        # Clone the repo
        LOG.info("cloning the cloudbaseinit repo.")
        self._execute("git clone https://github.com/stackforge/"
                      "cloudbase-init C:\\cloudbaseinit")

        # Run the command provided at cli.
        LOG.info("Applying cli patch.")
        self._execute("cd C:\\cloudbaseinit && {}".format(opts.git_command))

        # Replace the code, by moving the code from cloudbaseinit
        # to the installed location.
        LOG.info("Replacing code.")
        self._execute('powershell "Copy-Item C:\\cloudbaseinit\\cloudbaseinit '
                      '\'{}\' -Recurse"'.format(cloudbaseinit))

    def sysprep(self):
        """Prepare the instance for the actual tests, by running sysprep."""
        LOG.info("Running sysprep.")

        cmd = ("powershell Invoke-webrequest -uri "
               "{}/windows/sysprep.ps1 -outfile 'C:\\sysprep.ps1'"
               .format(CONF.argus.resources))
        self._execute(cmd)
        self._execute('powershell C:\\sysprep.ps1')

    def wait_cbinit_finalization(self):
        """Wait for the finalization of CloudbaseInit.

        The function waits until all the plugins have been executed.
        """
        LOG.info("Waiting for the finalization of CloudbaseInit execution")

        # Test that this instance's cloudbaseinit run exists.
        key = ('HKLM:SOFTWARE\\Wow6432Node\\Cloudbase` '
               'Solutions\\Cloudbase-init\\{0}'
               .format(self._instance_id))
        self._run_cmd_until_condition(
            'powershell Test-Path "{0}"'.format(key),
            lambda out: out.strip() == 'True')

        # Test the number of executed cloudbaseinit plugins.
        wait_cmd = ('powershell (Get-Service "| where -Property Name '
                    '-match cloudbase-init").Status')
        self._run_cmd_until_condition(
            wait_cmd,
            lambda out: out.strip() == 'Stopped')

    def wait_reboot(self):
        """Do a reboot and wait until the instance is up."""

        LOG.info('Waiting for server status SHUTOFF because of sysprep')
        self._api_manager.servers_client.wait_for_server_status(
            server_id=self._instance_id,
            status='SHUTOFF',
            extra_timeout=600)

        self._api_manager.servers_client.start(self._instance_id)

        LOG.info('Waiting for server status ACTIVE')
        self._api_manager.servers_client.wait_for_server_status(
            server_id=self._instance_id,
            status='ACTIVE')
