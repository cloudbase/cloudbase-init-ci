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

import ntpath
import os

from argus import exceptions
from argus.introspection.cloud import windows as introspection
from argus.recipes.cloud import base
from argus import util

CONF = util.get_config()
LOG = util.get_logger()

# Default values for an instance under booting step.
COUNT = 20
DELAY = 20


class CloudbaseinitRecipe(base.BaseCloudbaseinitRecipe):
    """Recipe for preparing a Windows instance."""

    def wait_for_boot_completion(self):
        LOG.info("Waiting for boot completion...")

        # TODO (ionuthulub) remove hardcoded username
        wait_cmd = ('powershell "(Get-WmiObject Win32_Account | '
                    'where -Property Name -contains {0}).Name"'
                    .format('CiAdmin'))
        self._execute_until_condition(
            wait_cmd,
            lambda stdout: stdout.strip() == 'CiAdmin',
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
        opts = util.parse_cli()
        installer = opts.installer_template.format(
            build=self.build,
            arch=self.arch
        )
        LOG.info("Run the downloaded installation script "
                 "using the installer %r with service %r.",
                 installer, self._service_type)

        cmd = ('powershell "C:\\\\installcbinit.ps1 -serviceType {} '
               '-installer {}"'.format(self._service_type, installer))
        try:
            self._execute(cmd, count=5, delay=5)
        except exceptions.ArgusError:
            # This can happen for multiple reasons,
            # but one of them is the fact that the installer
            # can't be installed through WinRM on some OSes
            # for whatever reason. In this case, we're falling back
            # to use a scheduled task.
            self._deploy_using_scheduled_task(installer)

        self._grab_cbinit_installation_log()

    def _deploy_using_scheduled_task(self, installer):
        cmd = ("powershell Invoke-webrequest -uri "
               "{}/windows/schedule_installer.bat -outfile "
               "C:\\schedule_installer.bat"
               .format(CONF.argus.resources))
        self._execute(cmd)

        # Now run it.
        cmd = ("C:\\\\schedule_installer.bat {0} {1}"
               .format(self._service_type, installer))
        self._execute(cmd)

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

        # Autoinstall packages from the new requirements.txt
        python = ntpath.join(python_dir, "python.exe")
        command = '"{}" -m pip install -r C:\\cloudbaseinit\\requirements.txt'
        self._execute(command.format(python))

    def pre_sysprep(self):
        """Disable first_logon_behaviour for testing purposes.

        Because first_logon_behaviour will control how the password
        should work on next logon, we could have troubles in tests,
        so this is always disabled, excepting tests which sets
        it manual to whatever they want.
        """
        introspection.set_config_option(
            option="first_logon_behaviour", value="no",
            execute_function=self._execute)

        # Patch the installation of cloudbaseinit in order to create
        # a file when the execution ends. We're doing this instead of
        # monitoring the service, because on some OSes, just checking the
        # that the service is stopped leads to errors, due to the
        # fact that the service starts later on.
        python_dir = introspection.get_python_dir(self._execute)
        cbinit = ntpath.join(python_dir, 'Lib', 'site-packages',
                             'cloudbaseinit')

        # Get the shell patching script and patch the installation.
        cmd = ("powershell Invoke-Webrequest -uri "
               "{}/windows/patch_shell.ps1 -outfile "
               "C:\\patch_shell.ps1"
               .format(CONF.argus.resources))
        self._execute(cmd)

        escaped = introspection._escape_path(cbinit)
        self._execute('powershell "C:\\\\patch_shell.ps1 \"{}\""'
                      .format(escaped))

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

        # Check if the service actually started.
        unattended_cmd = 'powershell Test-Path C:\\cloudbaseinit_unattended'
        normal_cmd = 'powershell Test-Path C:\\cloudbaseinit_normal'
        for check_cmd in (unattended_cmd, normal_cmd):
            self._execute_until_condition(
                check_cmd,
                lambda out: out.strip() == 'True',
                count=COUNT, delay=DELAY)

        # Check if the service finished
        wait_cmd = ('powershell (Get-Service "| where -Property Name '
                    '-match cloudbase-init").Status')
        self._execute_until_condition(
            wait_cmd,
            lambda out: out.strip() == 'Stopped',
            count=COUNT, delay=DELAY)


class CloudbaseinitScriptRecipe(CloudbaseinitRecipe):
    """A recipe which adds support for testing .exe scripts."""

    def pre_sysprep(self):
        super(CloudbaseinitScriptRecipe, self).pre_sysprep()
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
        super(CloudbaseinitCreateUserRecipe, self).pre_sysprep()
        LOG.info("Creating the user %s...", CONF.cloudbaseinit.created_user)
        cmd = ("powershell Invoke-webrequest -uri "
               "{}/windows/create_user.ps1 -outfile C:\\\\create_user.ps1"
               .format(CONF.argus.resources))
        self._execute(cmd)

        self._execute('powershell "C:\\\\create_user.ps1 -user {}"'.format(
            CONF.cloudbaseinit.created_user))


class BaseNextLogonRecipe(CloudbaseinitRecipe):
    """Useful for testing the next logon behaviour."""

    behaviour = None

    def pre_sysprep(self):
        super(BaseNextLogonRecipe, self).pre_sysprep()

        introspection.set_config_option(
            option="first_logon_behaviour",
            value=self.behaviour,
            execute_function=self._execute)


class AlwaysChangeLogonPasswordRecipe(BaseNextLogonRecipe):
    """Always change the password at next logon."""

    behaviour = 'always'


class ClearPasswordLogonRecipe(BaseNextLogonRecipe):
    """Change the password at next logon if the password is from metadata."""

    behaviour = 'clear_text_injected_only'


class CloudbaseinitMockServiceRecipe(CloudbaseinitRecipe):
    """A recipe for patching the cloudbaseinit's conf with a custom server."""

    config_entry = None
    pattern = "{}"

    def pre_sysprep(self):
        super(CloudbaseinitMockServiceRecipe, self).pre_sysprep()
        LOG.info("Inject guest IP for mocked service access.")

        # Append service IP as a config option.
        address = self.pattern.format(util.get_local_ip())
        introspection.set_config_option(option=self.config_entry,
                                        value=address,
                                        execute_function=self._execute)


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

        python_dir = introspection.get_python_dir(self._execute)
        cbinit = ntpath.join(python_dir, 'Lib', 'site-packages',
                             'cloudbaseinit')

        # Install mock
        python = ntpath.join(python_dir, "python.exe")
        command = '"{}" -m pip install mock'
        self._execute(command.format(python))

        # Get the cloudstack patching script and patch the installation.
        cmd = ("powershell Invoke-Webrequest -uri "
               "{}/windows/patch_cloudstack.ps1 -outfile "
               "C:\\patch_cloudstack.ps1"
               .format(CONF.argus.resources))
        self._execute(cmd)

        escaped = introspection._escape_path(cbinit)
        self._execute('powershell "C:\\\\patch_cloudstack.ps1 \"{}\""'
                      .format(escaped))


class CloudbaseinitMaasRecipe(CloudbaseinitMockServiceRecipe):
    """Recipe for Maas metadata service mocking."""

    config_entry = "maas_metadata_url"
    pattern = "http://{}:2002"

    def pre_sysprep(self):
        super(CloudbaseinitMaasRecipe, self).pre_sysprep()

        required_fields = (
            "maas_oauth_consumer_key",
            "maas_oauth_consumer_secret",
            "maas_oauth_token_key",
            "maas_oauth_token_secret",
        )

        for field in required_fields:
            introspection.set_config_option(option=field, value="secret",
                                            execute_function=self._execute)


class CloudbaseinitWinrmRecipe(CloudbaseinitCreateUserRecipe):
    """A recipe for testing the WinRM configuration plugin."""

    def pre_sysprep(self):
        super(CloudbaseinitWinrmRecipe, self).pre_sysprep()
        introspection.set_config_option(
            option="plugins",
            value="cloudbaseinit.plugins.windows.winrmcertificateauth."
                  "ConfigWinRMCertificateAuthPlugin,"
                  "cloudbaseinit.plugins.windows.winrmlistener."
                  "ConfigWinRMListenerPlugin",
            execute_function=self._execute)


class CloudbaseinitMissingPlugin(CloudbaseinitRecipe):
    """
    A recipe which modifies the list of plugins, by adding
    a plugin which doesn't exist.
    """

    def pre_sysprep(self):
        super(CloudbaseinitMissingPlugin, self).pre_sysprep()
        introspection.set_config_option(
            option="plugins",
            value="nanana.batman",
            execute_function=self._execute)


class CloudbaseinitHTTPRecipe(CloudbaseinitMockServiceRecipe):
    """Recipe for http metadata service mocking."""

    config_entry = "metadata_base_url"
    pattern = "http://{}:2003/"


class CloudbaseinitKeysRecipe(CloudbaseinitHTTPRecipe,
                              CloudbaseinitCreateUserRecipe):
    """Recipe that facilitates x509 certificates and public keys testing."""

    def pre_sysprep(self):
        super(CloudbaseinitKeysRecipe, self).pre_sysprep()
        introspection.set_config_option(
            option="plugins",
            value="cloudbaseinit.plugins.windows.createuser."
                  "CreateUserPlugin,"
                  "cloudbaseinit.plugins.windows.setuserpassword."
                  "SetUserPasswordPlugin,"
                  "cloudbaseinit.plugins.common.sshpublickeys."
                  "SetUserSSHPublicKeysPlugin,"
                  "cloudbaseinit.plugins.windows.winrmcertificateauth."
                  "ConfigWinRMCertificateAuthPlugin,"
                  "cloudbaseinit.plugins.windows.winrmlistener."
                  "ConfigWinRMListenerPlugin",
            execute_function=self._execute)


class CloudbaseinitLocalScriptsRecipe(CloudbaseinitRecipe):
    """Recipe for testing local scripts return codes."""

    def pre_sysprep(self):
        super(CloudbaseinitLocalScriptsRecipe, self).pre_sysprep()
        LOG.info("Download reboot-required local script.")

        cbdir = introspection.get_cbinit_dir(self._execute)
        cmd = ("powershell Invoke-WebRequest -uri "
               "{}/windows/reboot.cmd -outfile "
               "'C:\\Scripts\\reboot.cmd'")
        cmd = cmd.format(CONF.argus.resources, cbdir)
        self._execute(cmd)
