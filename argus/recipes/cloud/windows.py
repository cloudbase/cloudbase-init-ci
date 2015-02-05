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

"""Windows cloudbaseinit recipes."""

import contextlib
import ntpath
import os

import bs4
import six
from six.moves import urllib  # pylint: disable=import-error

from argus import exceptions
from argus.introspection.cloud import windows as introspection
from argus.recipes.cloud import base
from argus import util

CONF = util.get_config()
LOG = util.get_logger()

__all__ = (
    'CloudbaseinitRecipe',
    'CloudbaseinitScriptRecipe',
    'CloudbaseinitCreateUserRecipe',
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


class CloudbaseinitRecipe(base.BaseCloudbaseinitRecipe):
    """Recipe for preparing a Windows instance."""

    def wait_for_boot_completion(self):
        LOG.info("Waiting for boot completion...")

        wait_cmd = ('powershell "(Get-WmiObject Win32_Account | '
                    'where -Property Name -contains {0}).Name"'
                    .format(self._image.default_ci_username))
        return self._run_cmd_until_condition(
            wait_cmd,
            lambda stdout: stdout.strip() == self._image.default_ci_username)

    def get_installation_script(self):
        """Get an insallation script for CloudbaseInit."""
        LOG.info("Retrieve an installation script for CloudbaseInit.")

        cmd = ("powershell Invoke-webrequest -uri "
               "{}/windows/installCBinit.ps1 -outfile C:\\installcbinit.ps1"
               .format(CONF.argus.resources))
        self._execute(cmd)

    def install_cbinit(self):
        """Run the installation script for CloudbaseInit."""
        LOG.info("Run the downloaded installation script.")

        cmd = ('powershell "C:\\\\installcbinit.ps1 -serviceType {}"'
               .format(self._service_type))
        self._execute(cmd)

    def install_git(self):
        """Install git in the instance."""
        LOG.info("Installing git...")

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

        LOG.info("Replacing cloudbaseinit's code...")

        LOG.info("Getting cloudbase-init location...")
        # Get cb-init python location.
        python_dir = introspection.get_python_dir(self._execute)

        # Remove everything from the cloudbaseinit installation.
        LOG.info("Removing recursively cloudbaseinit...")
        cloudbaseinit = ntpath.join(
            python_dir,
            "Lib",
            "site-packages",
            "cloudbaseinit")
        self._execute('rmdir "{}" /S /q'.format(cloudbaseinit))

        # Clone the repo
        LOG.info("Cloning the cloudbaseinit repo...")
        self._execute("git clone https://github.com/stackforge/"
                      "cloudbase-init C:\\cloudbaseinit")

        # Run the command provided at cli.
        LOG.info("Applying cli patch...")
        self._execute("cd C:\\cloudbaseinit && {}".format(opts.git_command))

        # Replace the code, by moving the code from cloudbaseinit
        # to the installed location.
        LOG.info("Replacing code...")
        self._execute('powershell "Copy-Item C:\\cloudbaseinit\\cloudbaseinit '
                      '\'{}\' -Recurse"'.format(cloudbaseinit))

    def sysprep(self):
        """Prepare the instance for the actual tests, by running sysprep."""
        LOG.info("Running sysprep...")

        cmd = ("powershell Invoke-webrequest -uri "
               "{}/windows/sysprep.ps1 -outfile 'C:\\sysprep.ps1'"
               .format(CONF.argus.resources))
        self._execute(cmd)
        self._execute('powershell C:\\sysprep.ps1')

    def wait_cbinit_finalization(self):
        """Wait for the finalization of CloudbaseInit.

        The function waits until all the plugins have been executed.
        """
        LOG.info("Waiting for the finalization of CloudbaseInit execution...")

        # Test that this instance's cloudbaseinit run exists.
        self._run_cmd_until_condition(
            "echo 1",
            lambda out: out.strip() == "1"
        )
        head = introspection.get_cbinit_key(self._execute)
        key = "{0}\\{1}".format(head, self._instance_id)
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

        LOG.info('Waiting for server status SHUTOFF because of sysprep...')
        self._api_manager.servers_client.wait_for_server_status(
            server_id=self._instance_id,
            status='SHUTOFF',
            extra_timeout=600)

        self._api_manager.servers_client.start(self._instance_id)

        LOG.info('Waiting for server status ACTIVE...')
        self._api_manager.servers_client.wait_for_server_status(
            server_id=self._instance_id,
            status='ACTIVE')


class CloudbaseinitScriptRecipe(CloudbaseinitRecipe):
    """A recipe which adds support for testing .exe scripts."""

    def pre_sysprep(self):
        LOG.info("Doing last step before sysprepping.")

        cmd = ("powershell Invoke-WebRequest -uri "
               "{}/windows/test_exe.exe -outfile "
               "'C:\\Scripts\\test_exe.exe'".format(CONF.argus.resources))
        self._execute(cmd)


class CloudbaseinitCreateUserRecipe(CloudbaseinitRecipe):
    """A recipe for creating the user created by cloudbaseinit.

    The purpose is to use this recipe for testing that cloudbaseinit
    works, even when the user which should be created already exists.
    """

    def pre_sysprep(self):
        LOG.info("Creating the user %s...", self._image.created_user)
        cmd = ("powershell Invoke-webrequest -uri "
               "{}/windows/create_user.ps1 -outfile C:\\\\create_user.ps1"
               .format(CONF.argus.resources))
        self._execute(cmd)

        self._execute('powershell "C:\\\\create_user.ps1 -user {}"'.format(
            self._image.created_user))
