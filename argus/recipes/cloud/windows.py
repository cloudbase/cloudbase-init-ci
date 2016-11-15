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

"""Windows Cloudbase-Init recipes."""

import ntpath
import os

import six

from argus import config as argus_config
from argus.config_generator.windows import cb_init as cbinit_config
from argus import exceptions
from argus.introspection.cloud import windows as introspection
from argus.recipes.cloud import base
from argus import util

CONFIG = argus_config.CONFIG
LOG = util.get_logger()

# Default values for an instance under booting step.
COUNT = 20
DELAY = 20
_CBINIT_REPO = "https://github.com/openstack/cloudbase-init"
_CBINIT_TARGET_LOCATION = r"C:\cloudbaseinit"


class CloudbaseinitRecipe(base.BaseCloudbaseinitRecipe):
    """Recipe for preparing a Windows instance."""

    def wait_for_boot_completion(self):
        LOG.info("Waiting for first boot completion...")
        self._backend.remote_client.manager.wait_boot_completion()

    def set_mtu(self, interface="ipv4", subinterface_name="Ethernet",
                mtu_value=1400, store_type='active'):
        cmd = 'netsh interface ipv4 show subinterfaces level=verbose'
        stdout = self._backend.remote_client.run_command_verbose(
            cmd, command_type=util.CMD)
        subinterfaces = introspection.parse_netsh_output(stdout)
        for subinterface in subinterfaces:
            try:
                LOG.debug("Setting the MTU for %r", subinterface.name)
                set_mtu_cmd = ('netsh interface {interface_type} set '
                               'subinterface "{name}" mtu={value} store={type}'
                               .format(interface_type=interface,
                                       value=mtu_value, type=store_type,
                                       name=subinterface.name.strip('\r\n')))
                self._backend.remote_client.run_command_with_retry(set_mtu_cmd)
            except exceptions.ArgusTimeoutError as exc:
                LOG.debug('Setting MTU failed with %r.', exc)

    def execution_prologue(self):
        # Prepare Something specific for the OS
        self._backend.remote_client.manager.specific_prepare()

        LOG.info("Retrieve common module for proper script execution.")
        resource_location = "windows/common.psm1"
        self._backend.remote_client.manager.download_resource(
            resource_location=resource_location, location=r'C:\common.psm1')

    def get_installation_script(self):
        """Get installation script for CloudbaseInit."""
        self._backend.remote_client.manager.get_installation_script()

    def install_cbinit(self):
        """Proceed on checking if Cloudbase-Init should be installed."""
        try:
            introspection.get_cbinit_dir(self._execute)
        except exceptions.ArgusError:
            self._backend.remote_client.manager.install_cbinit()
            self._grab_cbinit_installation_log()
        else:
            # If the directory already exists,
            # we won't be installing Cloudbase-Init.
            LOG.info("Cloudbase-Init is already installed, "
                     "skipping installation.")

    def _grab_cbinit_installation_log(self):
        """Obtain the installation logs."""
        LOG.info("Obtaining the installation logs.")
        if not CONFIG.argus.output_directory:
            LOG.warning("The output directory wasn't given, "
                        "the log will not be grabbed.")
            return

        content = self._backend.remote_client.read_file("C:\\installation.log")
        log_template = "installation-{}.log".format(
            self._backend.instance_server()['id'])

        path = os.path.join(CONFIG.argus.output_directory, log_template)
        with open(path, 'w') as stream:
            stream.write(content)

    def replace_install(self):
        """Replace the Cloudbase-Init installed files with the downloaded ones.

        For the same file names, there will be a replace. The new ones
        will just be added and the other files will be left there.
        So it's more like an update.
        """
        link = CONFIG.argus.patch_install
        if not link:
            return

        LOG.info("Replacing Cloudbase-Init's files...")

        LOG.debug("Download and extract installation bundle.")
        if link.startswith("\\\\"):
            cmd = 'copy "{}" "C:\\install.zip"'.format(link)
            self._execute(cmd, command_type=util.CMD)
        else:
            location = r'C:\install.zip'
            self._backend.remote_client.manager.download(
                uri=link, location=location)
        cmds = [
            "Add-Type -A System.IO.Compression.FileSystem",
            "[IO.Compression.ZipFile]::ExtractToDirectory("
            "'C:\\install.zip', 'C:\\install')"
        ]
        cmd = '{}'.format("; ".join(cmds))
        self._execute(cmd, command_type=util.POWERSHELL)

        LOG.debug("Replace old files with the new ones.")
        cbdir = introspection.get_cbinit_dir(self._execute)
        self._execute('xcopy /y /e /q "C:\\install"'
                      ' "{}"'.format(cbdir), command_type=util.CMD)

        # Update the new changes
        resource_location = "windows/updateCbinit.ps1"
        self._backend.remote_client.manager.execute_powershell_resource_script(
            resource_location=resource_location)

    def replace_code(self):
        """Replace the code of Cloudbase-Init."""
        if not CONFIG.argus.git_command:
            # Nothing to replace.
            return

        LOG.info("Replacing Cloudbase-Init's code...")

        LOG.debug("Getting Cloudbase-Init location...")
        # Get Cloudbase-Init python location.
        python_dir = introspection.get_python_dir(self._execute)

        # Remove everything from the Cloudbase-Init installation.
        LOG.debug("Recursively removing Cloudbase-Init...")
        cloudbaseinit = ntpath.join(
            python_dir,
            "Lib",
            "site-packages",
            "cloudbaseinit")
        self._execute('rmdir "{}" /S /q'.format(cloudbaseinit),
                      command_type=util.CMD)

        # Clone the repository
        clone_res = self._backend.remote_client.manager.git_clone(
            repo_url=_CBINIT_REPO, location=_CBINIT_TARGET_LOCATION)
        if not clone_res:
            raise exceptions.ArgusError('Code repository could not '
                                        'be cloned.')
        # Run the command provided at cli.
        LOG.debug("Applying cli patch...")
        self._execute("cd {location} && {command}".format(
            location=_CBINIT_TARGET_LOCATION,
            command=CONFIG.argus.git_command), command_type=util.CMD)

        # Replace the code, by moving the code from Cloudbase-Init
        # to the installed location.
        LOG.debug("Replacing code...")
        self._execute('Copy-Item {location}\\cloudbaseinit \'{folder}\''
                      '-Recurse'.format(location=_CBINIT_TARGET_LOCATION,
                                        folder=cloudbaseinit),
                      command_type=util.POWERSHELL)

        # Auto-install packages from the new requirements.txt
        python = ntpath.join(python_dir, "python.exe")
        command = '"{folder}" -m pip install -r {location}\\requirements.txt'
        self._execute(command.format(folder=python,
                                     location=_CBINIT_TARGET_LOCATION),
                      command_type=util.CMD)

    def pre_sysprep(self):
        # Patch the installation of Cloudbase-Init in order to create
        # a file when the execution ends. We're doing this instead of
        # monitoring the service, because on some OSes, just checking
        # if the service is stopped leads to errors, due to the
        # fact that the service starts later on.
        python_dir = introspection.get_python_dir(self._execute)
        cbinit = ntpath.join(python_dir, 'Lib', 'site-packages',
                             'cloudbaseinit')

        # Get the shell patching script and patch the installation.
        resource_location = "windows/patch_shell.ps1"
        params = r' "{}"'.format(cbinit)
        self._backend.remote_client.manager.execute_powershell_resource_script(
            resource_location=resource_location, parameters=params)

    def sysprep(self):
        """Prepare the instance for the actual tests, by running sysprep."""
        LOG.info("Running sysprep...")

        self._backend.remote_client.manager.sysprep()

    def wait_cbinit_finalization(self):
        paths = [
            r"C:\cloudbaseinit_unattended",
            r"C:\cloudbaseinit_normal"]

        LOG.debug("Check the heartbeat patch ...")
        self._backend.remote_client.manager.check_cbinit_service(
            searched_paths=paths)

        LOG.debug("Wait for the Cloudbase-Init service to stop ...")
        self._backend.remote_client.manager.wait_cbinit_service()

    def prepare_cbinit_config(self, service_type):
        """Prepare the Cloudbase-Init config."""
        self._cbinit_conf = cbinit_config.CBInitConfig(
            client=self._backend.remote_client)

        self._cbinit_unattend_conf = cbinit_config.UnattendCBInitConfig(
            client=self._backend.remote_client)

        # NOTE(mmicu): Because first_logon_behaviour will control
        #              how the password should work on next logon,
        #              we could have failing tests due to
        #              authentication failures.

        self._cbinit_conf.set_service_type(service_type)

        self._cbinit_conf.set_conf_value(name="first_logon_behaviour",
                                         value="no")
        self._cbinit_conf.set_conf_value(
            name="activate_windows",
            value=CONFIG.cloudbaseinit.activate_windows)
        scripts_path = "C:\\Scripts"
        self._make_dir_if_needed(scripts_path)
        self._cbinit_conf.set_conf_value(name="local_scripts_path",
                                         value=scripts_path)

        self._cbinit_conf.set_conf_value(
            name="activate_windows",
            value=CONFIG.cloudbaseinit.activate_windows)

        self._backend.remote_client.manager.prepare_config(
            self._cbinit_conf, self._cbinit_unattend_conf)

    def _make_dir_if_needed(self, path):
        """Check if the directory exists, if it doesn't create it."""
        if not self._backend.remote_client.manager.is_dir(path):
            cmd = 'mkdir "{}"'.format(path)
            self._backend.remote_client.run_remote_cmd(cmd, util.POWERSHELL)

    def inject_cbinit_config(self):
        """Inject the Cloudbase-Init config in the right place."""
        cbinit_dir = introspection.get_cbinit_dir(self._execute)

        conf_dir = ntpath.join(cbinit_dir, "conf")
        needed_directories = [
            ntpath.join(cbinit_dir, "log"),
            conf_dir,
        ]

        for directory in needed_directories:
            self._make_dir_if_needed(directory)

        self._cbinit_conf.apply_config(conf_dir)
        self._cbinit_unattend_conf.apply_config(conf_dir)


class CloudbaseinitScriptRecipe(CloudbaseinitRecipe):
    """A recipe which adds support for testing .exe scripts."""

    def pre_sysprep(self):
        super(CloudbaseinitScriptRecipe, self).pre_sysprep()
        LOG.info("Doing last step before sysprepping.")

        resource_location = "windows/test_exe.exe"
        location = r"C:\Scripts\test_exe.exe"
        self._backend.remote_client.manager.download_resource(
            resource_location=resource_location, location=location)


class CloudbaseinitCreateUserRecipe(CloudbaseinitRecipe):
    """A recipe for creating the user created by Cloudbase-Init.

    The purpose is to use this recipe for testing that Cloudbase-Init
    works, even when the user which should be created already exists.
    """

    def pre_sysprep(self):
        super(CloudbaseinitCreateUserRecipe, self).pre_sysprep()
        LOG.info("Creating the user %s...",
                 CONFIG.cloudbaseinit.created_user)

        resource_location = "windows/create_user.ps1"
        params = r" -user {}".format(CONFIG.cloudbaseinit.created_user)
        self._backend.remote_client.manager.execute_powershell_resource_script(
            resource_location=resource_location, parameters=params)


class BaseNextLogonRecipe(CloudbaseinitRecipe):
    """Useful for testing the next logon behaviour."""

    behaviour = None

    def prepare_cbinit_config(self, service_type):
        super(BaseNextLogonRecipe, self).prepare_cbinit_config(service_type)
        self._cbinit_conf.set_conf_value(
            name="first_logon_behaviour",
            value=self.behaviour)


class AlwaysChangeLogonPasswordRecipe(BaseNextLogonRecipe):
    """Always change the password at next logon."""

    behaviour = 'always'


class ClearPasswordLogonRecipe(BaseNextLogonRecipe):
    """Change the password at next logon if the password is from metadata."""

    behaviour = 'clear_text_injected_only'


class CloudbaseinitMockServiceRecipe(CloudbaseinitRecipe):
    """A recipe for patching the Cloudbase-Init conf with a custom server.

    Attributes:
        config_group: The group name specific to the metadata provider.
        config_entry: Field containing the metadata url name for the
                      specified provider.
        metadata_address: The address for where to access the metadata service.
    """

    config_group = "DEFAULT"
    config_entry = "metadata_base_url"
    metadata_address = "metadata_url_value"

    def prepare_cbinit_config(self, service_type):
        super(CloudbaseinitMockServiceRecipe,
              self).prepare_cbinit_config(service_type)
        LOG.info("Inject guest IP for mocked service access.")

        # TODO(mmicu): The service type is specific to each scenario,
        # find a way to pass it.
        self._cbinit_conf.set_conf_value(name=self.config_entry,
                                         value=self.metadata_address,
                                         section=self.config_group)


class CloudbaseinitEC2Recipe(CloudbaseinitMockServiceRecipe):
    """Recipe for EC2 metadata service mocking."""

    config_group = util.EC2_SERVICE
    metadata_address = CONFIG.ec2_mock.metadata_base_url


class CloudbaseinitCloudstackRecipe(CloudbaseinitMockServiceRecipe):
    """Recipe for Cloudstack metadata service mocking."""

    config_group = util.CLOUD_STACK_SERVICE
    metadata_address = CONFIG.cloudstack_mock.metadata_base_url

    def prepare_cbinit_config(self, service_type):
        super(CloudbaseinitCloudstackRecipe,
              self).prepare_cbinit_config(service_type)

        field = 'password_server_port'
        port_value = CONFIG.cloudstack_mock.password_server_port
        self._cbinit_conf.set_conf_value(name=field, value=port_value,
                                         section=self.config_group)


class CloudbaseinitMaasRecipe(CloudbaseinitMockServiceRecipe):
    """Recipe for Maas metadata service mocking."""

    config_group = util.MAAS_SERVICE
    metadata_address = CONFIG.maas_mock.metadata_base_url

    def prepare_cbinit_config(self, service_type):
        super(CloudbaseinitMaasRecipe,
              self).prepare_cbinit_config(service_type)

        required_fields = (
            "maas_oauth_consumer_key",
            "maas_oauth_consumer_secret",
            "maas_oauth_token_key",
            "maas_oauth_token_secret",
        )

        for field in required_fields:
            self._cbinit_conf.set_conf_value(name=field, value="secret")


class CloudbaseinitWinrmRecipe(CloudbaseinitCreateUserRecipe):
    """A recipe for testing the WinRM configuration plugin."""

    def prepare_cbinit_config(self, service_type):
        super(CloudbaseinitWinrmRecipe,
              self).prepare_cbinit_config(service_type)
        self._cbinit_conf.set_conf_value(
            name="plugins",
            value="cloudbaseinit.plugins.windows.winrmcertificateauth."
                  "ConfigWinRMCertificateAuthPlugin,"
                  "cloudbaseinit.plugins.windows.winrmlistener."
                  "ConfigWinRMListenerPlugin")


class CloudbaseinitHTTPRecipe(CloudbaseinitMockServiceRecipe):
    """Recipe for http metadata service mocking."""

    metadata_address = CONFIG.openstack_mock.metadata_base_url


class CloudbaseinitKeysRecipe(CloudbaseinitHTTPRecipe,
                              CloudbaseinitCreateUserRecipe):
    """Recipe that facilitates x509 certificates and public keys testing."""

    def prepare_cbinit_config(self, service_type):
        super(CloudbaseinitKeysRecipe,
              self).prepare_cbinit_config(service_type)
        self._cbinit_conf.set_conf_value(
            name="plugins",
            value="cloudbaseinit.plugins.windows.createuser."
                  "CreateUserPlugin,"
                  "cloudbaseinit.plugins.windows.setuserpassword."
                  "SetUserPasswordPlugin,"
                  "cloudbaseinit.plugins.common.sshpublickeys."
                  "SetUserSSHPublicKeysPlugin,"
                  "cloudbaseinit.plugins.windows.winrmlistener."
                  "ConfigWinRMListenerPlugin,"
                  "cloudbaseinit.plugins.windows.winrmcertificateauth."
                  "ConfigWinRMCertificateAuthPlugin")


class CloudbaseinitLongHostname(CloudbaseinitRecipe):
    """Recipe for testing the netbios long hostname compatibility option."""

    def prepare_cbinit_config(self, service_type):
        super(CloudbaseinitLongHostname, self).prepare_cbinit_config(
            service_type)
        LOG.info("Injecting netbios option in conf file.")
        self._cbinit_conf.set_conf_value(
            name='netbios_host_name_compatibility', value='False')


class CloudbaseinitLocalScriptsRecipe(CloudbaseinitRecipe):
    """Recipe for testing local scripts return codes."""

    def pre_sysprep(self):
        super(CloudbaseinitLocalScriptsRecipe, self).pre_sysprep()
        LOG.debug("Downloading reboot-required local script.")

        resource_location = "windows/reboot.cmd"
        self._backend.remote_client.manager.download_resource(
            resource_location=resource_location,
            location=r'C:\Scripts\reboot.cmd')


class CloudbaseinitImageRecipe(CloudbaseinitRecipe):
    """Calibrate already sys-prepared Cloudbase-Init images."""

    def wait_cbinit_finalization(self):
        cbdir = introspection.get_cbinit_dir(self._execute)
        paths = [ntpath.join(cbdir, "log", name)
                 for name in ["cloudbase-init-unattend.log",
                              "cloudbase-init.log"]]

        LOG.debug("Check the heartbeat patch ...")
        self._backend.remote_client.manager.check_cbinit_service(
            searched_paths=paths)

        LOG.debug("Wait for the Cloudbase-Init service to stop ...")
        self._backend.remote_client.manager.wait_cbinit_service()

    def prepare(self, service_type=None, **kwargs):
        LOG.info("Preparing already sysprepped instance...")
        self.execution_prologue()

        if CONFIG.argus.pause:
            six.moves.input("Press Enter to continue...")

        self.wait_cbinit_finalization()
        LOG.info("Finished preparing instance.")
