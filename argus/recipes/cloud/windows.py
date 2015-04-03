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

# Default values for an instance under booting step.
COUNT = 20
DELAY = 20

__all__ = (
    'CloudbaseinitRecipe',
    'CloudbaseinitScriptRecipe',
    'CloudbaseinitCreateUserRecipe',
    'CloudbaseinitSpecializeRecipe',
)


def _read_url(url):
    request = urllib.request.urlopen(url)
    with contextlib.closing(request) as stream:
        content = stream.read()
        if six.PY3:
            content = content.decode(errors='replace')
        return content


@util.with_retry()
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
    raise exceptions.ArgusError("Git download link not found.")


class CloudbaseinitRecipe(base.BaseCloudbaseinitRecipe):
    """Recipe for preparing a Windows instance."""

    def wait_for_boot_completion(self):
        LOG.info("Waiting for boot completion...")

        wait_cmd = ('powershell "(Get-WmiObject Win32_Account | '
                    'where -Property Name -contains {0}).Name"'
                    .format(self._image.default_ci_username))
        self._execute_until_condition(
            wait_cmd,
            lambda stdout: stdout.strip() == self._image.default_ci_username,
            count=COUNT, delay=DELAY)

    def execution_prologue(self):
        LOG.info("Retrieve common module for proper script execution.")

        cmd = ("powershell Invoke-webrequest -uri "
               "{}/windows/common.psm1 -outfile C:\\common.psm1"
               .format(CONF.argus.resources))
        self._execute(cmd)

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

        self._grab_cbinit_installation_log()

    def _grab_cbinit_installation_log(self):
        """Obtain the installation logs."""
        LOG.info("Obtaining the installation logs.")
        if not self._output_directory:
            LOG.warning("The output directory wasn't given, "
                        "the log will not be grabbed.")
            return

        content = self._remote_client.read_file("C:\\installation.log")
        path = os.path.join(self._output_directory,
                            "installation-{}.log".format(self._instance_id))
        with open(path, 'w') as stream:
            stream.write(content)

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

    def replace_install(self):
        """Replace the cb-init installed files with the downloaded ones.

        For the same file names, there will be a replace. The new ones
        will just be added and the other files will be left there.
        So it's more like an update.
        """
        opts = util.parse_cli()
        link = opts.patch_install
        if not link:
            return

        LOG.info("Replacing cloudbaseinit's files...")

        LOG.debug("Download and extract installation bundle.")
        if link.startswith("\\\\"):
            cmd = 'copy "{}" "C:\\install.zip"'.format(link)
        else:
            cmd = ("powershell Invoke-webrequest -uri "
                   "{} -outfile 'C:\\install.zip'"
                   .format(link))
        self._execute(cmd)
        cmds = [
            "Add-Type -A System.IO.Compression.FileSystem",
            "[IO.Compression.ZipFile]::ExtractToDirectory("
            "'C:\\install.zip', 'C:\\install')"
        ]
        cmd = 'powershell {}'.format("; ".join(cmds))
        self._execute(cmd)

        LOG.debug("Replace old files with the new ones.")
        cbdir = introspection.get_cbinit_dir(self._execute)
        self._execute('xcopy /y /e /q "C:\\install\\Cloudbase-Init"'
                      ' "{}"'.format(cbdir))

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
        try:
            self._execute('powershell C:\\sysprep.ps1', count=1)
        except Exception:
            # This will fail, since it's blocking until the
            # restart occurs, so there will be transport issues.
            pass

    def wait_cbinit_finalization(self):
        """Wait for the finalization of CloudbaseInit.

        The function waits until cloudbaseinit finished.
        """
        LOG.info("Waiting for the finalization of CloudbaseInit execution...")
        wait_cmd = ('powershell (Get-Service "| where -Property Name '
                    '-match cloudbase-init").Status')
        self._execute_until_condition(
            wait_cmd,
            lambda out: out.strip() == 'Stopped',
            count=COUNT, delay=DELAY)


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
        LOG.info("Creating the user %s...", CONF.cloudbaseinit.created_user)
        cmd = ("powershell Invoke-webrequest -uri "
               "{}/windows/create_user.ps1 -outfile C:\\\\create_user.ps1"
               .format(CONF.argus.resources))
        self._execute(cmd)

        self._execute('powershell "C:\\\\create_user.ps1 -user {}"'.format(
            CONF.cloudbaseinit.created_user))


class CloudbaseinitSpecializeRecipe(CloudbaseinitRecipe):
    """A recipe for testing errors in specialize part.

    We'll need to test the specialize part as well and
    this recipe ensures us that something will fail there,
    in order to see if argus catches that error.
    """

    def pre_sysprep(self):
        LOG.info("Preparing cloudbaseinit for failure.")
        python_dir = introspection.get_python_dir(self._execute)
        path = ntpath.join(python_dir, "Lib", "site-packages",
                           "cloudbaseinit", "plugins", "common",
                           "mtu.py")
        self._execute('del "{}"'.format(path))
        # *.pyc
        self._execute('del "{}c"'.format(path))


class CloudbaseinitMockServiceRecipe(CloudbaseinitRecipe):
    """A recipe for patching the cloudbaseinit's conf with a custom server."""

    config_entry = None
    pattern = "{}"

    def pre_sysprep(self):
        LOG.info("Inject guest IP for mocked service access.")
        cbdir = introspection.get_cbinit_dir(self._execute)
        conf = ntpath.join(cbdir, "conf", "cloudbase-init.conf")

        # Append service IP as a config option.
        address = self.pattern.format(util.get_local_ip())
        line = "{} = {}".format(self.config_entry, address)
        cmd = ('powershell "((Get-Content {0!r}) + {1!r}) |'
               ' Set-Content {0!r}"'.format(conf, line))
        self._execute(cmd)


class CloudbaseinitEC2Recipe(CloudbaseinitMockServiceRecipe):
    """Recipe for EC2 metadata service mocking."""

    config_entry = "ec2_metadata_base_url"
    pattern = "http://{}:2000/"


class CloudbaseinitCloudstackRecipe(CloudbaseinitMockServiceRecipe):
    """Recipe for Cloudstack metadata service mocking."""

    config_entry = "cloudstack_metadata_ip"
    pattern = "{}:2001"

    def pre_sysprep(self):
        super(CloudbaseinitCloudstackRecipe, self).pre_sysprep()

        # CloudStack uses the metadata service on port 80 and
        # uses the passed metadata IP on port 8080 for the password manager.
        # Since we need to mock the service, we'll have to provide
        # a service on a custom port (apache is started on 80),
        # so this code does what it's necessary to make this work.
        cmd = ("powershell Invoke-Webrequest -uri "
               "{}/windows/patch_cloudstack.ps1 -outfile "
               "C:\\patch_cloudstack.ps1"
               .format(CONF.argus.resources))
        self._execute(cmd)

        self._execute("powershell C:\\\\patch_cloudstack.ps1")


class CloudbaseinitMaasRecipe(CloudbaseinitMockServiceRecipe):
    """Recipe for Maas metadata service mocking."""

    config_entry = "maas_metadata_url"
    pattern = "http://{}:2002"

    def pre_sysprep(self):
        super(CloudbaseinitMaasRecipe, self).pre_sysprep()

        # We'll have to send a couple of other config options as well.
        cbdir = introspection.get_cbinit_dir(self._execute)
        conf = ntpath.join(cbdir, "conf", "cloudbase-init.conf")

        required_fields = (
            "maas_oauth_consumer_key",
            "maas_oauth_consumer_secret",
            "maas_oauth_token_key",
            "maas_oauth_token_secret",
        )

        for field in required_fields:
            line = "{} = secret".format(field)
            cmd = ('powershell "((Get-Content {0!r}) + {1!r}) |'
                   ' Set-Content {0!r}"'.format(conf, line))
            self._execute(cmd)
