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

import base64
import ntpath
import os
import zipfile

from argus import config as argus_config
from argus.config_generator.windows import cb_init as cbinit_config
from argus import exceptions
from argus.introspection.cloud import windows as introspection
from argus import log as argus_log
from argus.recipes.cloud import base
from argus import util
from argus import metadata_provider

CONFIG = argus_config.CONFIG
LOG = argus_log.LOG

# Default values for an instance under booting step.
COUNT = 20
DELAY = 20
_CBINIT_REPO = CONFIG.argus.cbinit_git_repository
_CBINIT_TARGET_LOCATION = r"C:\cloudbaseinit"


class CloudbaseinitRecipe(base.BaseCloudbaseinitRecipe):
    """Recipe for preparing a Windows instance."""

    def __init__(self, backend):
        super(CloudbaseinitRecipe, self).__init__(backend)
        self.metadata_provider = None

    def wait_for_boot_completion(self):
        LOG.info("Waiting for first boot completion...")
        self._backend.remote_client.manager.wait_boot_completion()

    def get_os_type(self):
        """Get the os type."""
        return self._backend.remote_client.manager.os_type

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

    @staticmethod
    def extract_files_from_archive(archive_path, destination_path):
        with zipfile.ZipFile(archive_path, "r") as zip_ref:
            zip_ref.extractall(destination_path)
        os.remove(archive_path)

    def transfer_encoded_file_b64(self, file_source, destination_path,
                                  archive=False):
        """Creates a new file to the path by decoding a base64 string."""
        encoded_content = (self._backend.remote_client.manager.
                           encode_file_to_base64_str(
                               file_path=file_source))
        file_64_decoded = base64.standard_b64decode(encoded_content[0])
        with open(destination_path, 'wb') as file_result:
            file_result.write(file_64_decoded)
        if archive:
            self.extract_files_from_archive(destination_path,
                                            CONFIG.argus.output_directory)

    def _grab_cbinit_installation_log(self):
        """Obtain the installation logs."""
        LOG.info("Obtaining the installation logs.")
        if not CONFIG.argus.output_directory:
            LOG.warning("The output directory wasn't given, "
                        "the log will not be grabbed.")
            return
        # Rename the installation log and archive it.
        installation_log = r"C:\installation.log"
        renamed_log = (r"C:\{0}-installation-{1}.log".format(
            argus_log.get_log_extra_item(LOG, 'scenario'),
            self._backend.instance_server()['id']))
        self._backend.remote_client.manager.copy_file(installation_log,
                                                      renamed_log)
        zip_source = r"C:\installation.zip"
        self._backend.remote_client.manager.archive_file(
            file_path=renamed_log,
            destination_path=zip_source)
        log_template = "installation-{}.zip".format(
            self._backend.instance_server()['id'])
        path = os.path.join(CONFIG.argus.output_directory, log_template)
        self.transfer_encoded_file_b64(zip_source, path, archive=True)

    def replace_install(self):
        """Replace the Cloudbase-Init installed files with the downloaded ones.

        For the same file names, there will be a replace. The new ones
        will just be added and the other files will be left there.
        So it's more like an update.
        """
        link = CONFIG.argus.patch_install
        if not link:
            return

        LOG.info("Replacing Cloudbase-Init's files with %s", link)

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

        LOG.info("Replacing Cloudbase-Init's code "
                 "with %s", CONFIG.argus.git_command)

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

        command = '"{folder}" -m pip install {location}'
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

    @staticmethod
    def _get_namespace(service_type):
        """Return the metadata namespace."""
        # NOTE(mmicu): for Openstack we have the service_type set to http
        return service_type if service_type != "http" else "openstack"

    def create_mock_metadata(self, service_type):
        """Create the mocked metadata."""
        self.metadata_provider = metadata_provider.get_provider(
            self, self._backend)

        self.metadata_provider.prepare_metadata(service_type)

    def delete_mock_metadata(self):
        """Delete the mocked metadata."""
        if self.metadata_provider:
            self.metadata_provider.delete_all_data()

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
        self._cbinit_unattend_conf.set_service_type(service_type)

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
            name="check_latest_version",
            value=CONFIG.cloudbaseinit.check_latest_version)

        self._backend.remote_client.manager.prepare_config(
            self._cbinit_conf, self._cbinit_unattend_conf)

        metadata_url = self.metadata_provider.get_url(service_type)
        LOG.info("Injecting metadata URL %s option in conf file.",
                 metadata_url)
        if service_type and metadata_url:
            for conf in (self._cbinit_conf, self._cbinit_unattend_conf):
                conf.set_conf_value(
                    name="metadata_base_url", value=metadata_url,
                    section=self._get_namespace(service_type))

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

    def get_cb_init_files(self, location, files):
        LOG.info("Obtaining Cloudbase-Init files from %s" % location)
        if not CONFIG.argus.output_directory:
            LOG.warning("The output directory wasn't given, "
                        "the files will not be grabbed.")
            return

        instance_id = self._backend.instance_server()['id']
        scenario_name = argus_log.get_log_extra_item(LOG, 'scenario')
        cbdir = introspection.get_cbinit_dir(self._execute)
        cb_files = files
        renamed_cb_files = []
        cb_files_path = []
        renamed_cb_files_path = []
        for cb_file in cb_files:
            renamed_cb_files.append(scenario_name + "-" + instance_id +
                                    "-" + cb_file)

        for cb_file in cb_files:
            file_path = os.path.join(cbdir, r"{location}\{file}".format(
                location=location, file=cb_file))
            renamed_path = (os.path.join(cbdir,
                                         (r"{location}\{scenario}-{instance}-"
                                          "-{file}".
                                          format(location=location,
                                                 scenario=scenario_name,
                                                 instance=instance_id,
                                                 file=cb_file))))
            cb_files_path.append(file_path)
            renamed_cb_files_path.append(renamed_path)

        files_to_rename = list(zip(cb_files_path,
                                   renamed_cb_files_path))
        for current_name, renamed in files_to_rename:
            self._backend.remote_client.manager.copy_file(current_name,
                                                          renamed)

        source_destination = list(zip(renamed_cb_files_path,
                                      renamed_cb_files))
        for source, destination in source_destination:
            path = os.path.join(CONFIG.argus.output_directory, destination)
            self.transfer_encoded_file_b64(source, path)

    def get_cb_init_logs(self):
        self.get_cb_init_files(
            location="log",
            files=["cloudbase-init.log", "cloudbase-init-unattend.log"])

    def get_cb_init_confs(self):
        self.get_cb_init_files(
            location="conf",
            files=["cloudbase-init.conf", "cloudbase-init-unattend.conf"])


class CloudbaseinitScriptRecipe(CloudbaseinitRecipe):
    """A recipe which adds support for testing .exe scripts."""

    def pre_sysprep(self):
        super(CloudbaseinitScriptRecipe, self).pre_sysprep()
        LOG.info("Doing last step before sysprepping.")

        cmd = '$ENV:PROCESSOR_ARCHITECTURE'
        stdout = self._backend.remote_client.run_command_verbose(cmd)
        architecture = stdout.strip()
        resource_location = ("windows/test_exe{0}.exe".format(
            "64" if architecture == 'AMD64' else "32"))

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
            value="cloudbaseinit.plugins.windows.createuser."
                  "CreateUserPlugin,"
                  "cloudbaseinit.plugins.windows.setuserpassword."
                  "SetUserPasswordPlugin,"
                  "cloudbaseinit.plugins.windows.winrmlistener."
                  "ConfigWinRMListenerPlugin,"
                  "cloudbaseinit.plugins.windows.winrmcertificateauth."
                  "ConfigWinRMCertificateAuthPlugin")


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


class CloudbaseinitAddUserdata(CloudbaseinitRecipe):
    """Recipe for testing that the userdata is being saved on the disk."""

    def prepare_cbinit_config(self, service_type):
        super(CloudbaseinitAddUserdata, self).prepare_cbinit_config(
            service_type)

        # NOTE(mmicu): add a post_config method for the
        # prepare_cbinit_config
        if self._backend.remote_client.manager.os_type != util.WINDOWS_NANO:
            LOG.info("Injecting userdata_path option in conf file.")
            self._cbinit_conf.set_conf_value(
                name='userdata_save_path', value=r'C:\userdatafile')


class CloudbaseinitLongHostname(CloudbaseinitRecipe):
    """Recipe for testing the netbios long hostname compatibility option."""

    def prepare_cbinit_config(self, service_type):
        super(CloudbaseinitLongHostname, self).prepare_cbinit_config(
            service_type)
        LOG.info("Injecting netbios option in conf file.")
        self._cbinit_conf.set_conf_value(
            name='netbios_host_name_compatibility', value='False')


class CloudbaseinitEnableTrim(CloudbaseinitRecipe):
    """Recipe for testing TRIM configuration."""

    def pre_sysprep(self):
        command = "fsutil.exe behavior set disabledeletenotify 1"
        self._backend.remote_client.run_command_with_retry(
            command, command_type=util.CMD)

    def prepare_cbinit_config(self, service_type):
        LOG.info("Injecting trim_enabled option in conf file.")
        self._cbinit_unattend_conf.append_conf_value(
            name='trim_enabled', value='True')

        self._cbinit_unattend_conf.append_conf_value(
            name="plugins",
            value="cloudbaseinit.plugins.common.trim"
                  ".TrimConfigPlugin")


class CloudbaseinitSANPolicy(CloudbaseinitRecipe):
    """Recipe for testing SAN Policy plugin."""
    def pre_sysprep(self):
        self._backend.remote_client.manager.set_san_policy(
            util.SAN_POLICY_OFFLINE_STR)

    def prepare_cbinit_config(self, service_type):
        LOG.info("Injecting SAN Policy option in conf file.")
        self._cbinit_unattend_conf.append_conf_value(
            name='san_policy', value=util.SAN_POLICY_ONLINE_STR)

        self._cbinit_unattend_conf.append_conf_value(
            name="plugins",
            value="cloudbaseinit.plugins.windows.sanpolicy"
                  ".SANPolicyPlugin")


class CloudbaseinitPageFilePlugin(CloudbaseinitRecipe):
    """Recipe for testing the PageFile plugin"""

    def prepare_cbinit_config(self, service_type):
        LOG.info("Injecting page file options in the config file.")

        self._cbinit_unattend_conf.set_conf_value(
            name="page_file_volume_labels", value="Temporary Storage")
        self._cbinit_unattend_conf.set_conf_value(
            name="page_file_volume_mount_points", value="C:\\")
        self._cbinit_unattend_conf.append_conf_value(
            name="plugins",
            value="cloudbaseinit.plugins.windows.pagefiles.PageFilesPlugin")


class CloudbaseinitDisplayTimeoutPlugin(CloudbaseinitPageFilePlugin):
    """Recipe for testing the DisplayIdleTimeout plugin"""

    @util.skip_on_os(
        [util.WINDOWS_NANO, util.WINDOWS_SERVER_2008,
         util.WINDOWS_SERVER_2008_R2, util.WINDOWS7],
        "OS Version not supported")
    def prepare_cbinit_config(self, service_type):
        LOG.info("Injecting idle display options in the config file.")
        self._cbinit_conf.set_conf_value(
            name="display_idle_timeout", value="123")
        self._cbinit_conf.append_conf_value(
            name="plugins",
            value="cloudbaseinit.plugins.windows.displayidletimeout."
                  "DisplayIdleTimeoutConfigPlugin")


class CloudbaseinitKMSHostPlugin(CloudbaseinitRecipe):
    """Recipe for testing the kms_host option."""

    @util.skip_on_os([util.WINDOWS_NANO], "OS Version not supported")
    def prepare_cbinit_config(self, service_type):
        LOG.info("Injecting kms_host options in the config file.")
        self._cbinit_conf.set_conf_value(
            name="activate_windows", value="True")
        self._cbinit_conf.set_conf_value(
            name="kms_host", value="127.0.0.1:1688")
        self._cbinit_conf.append_conf_value(
            name="plugins",
            value="cloudbaseinit.plugins.windows.licensing."
                  "WindowsLicensingPlugin")


class CloudbaseinitSetRealClock(CloudbaseinitRecipe):

    def pre_sysprep(self):
        cmd = ("New-ItemProperty -Path '{}' -Name '{}' -Value '{}' "
               "-PropertyType DWORD -Force".format(
                   (r'HKLM:\SYSTEM\CurrentControlSet\Control'
                    r'\TimeZoneInformation'), 'RealTimeIsUniversal', 0))
        self._backend.remote_client.run_command_verbose(cmd)

    def prepare_cbinit_config(self, service_type):
        LOG.info("Injecting real_time_clock_utc option in config file.")
        self._cbinit_unattend_conf.set_conf_value(
            name="real_time_clock_utc",
            value="true")
        self._cbinit_unattend_conf.append_conf_value(
            name="plugins",
            value="cloudbaseinit.plugins.common.ntpclient."
                  "NTPClientPlugin")


class CloudbaseinitBootConfigPlugin(CloudbaseinitRecipe):
    """Recipe for testing the BootStatusPolicyPlugin and BCDConfigPlugin."""

    @util.skip_on_os([util.WINDOWS_NANO], "OS Version not supported")
    def pre_sysprep(self):
        resource_location = "windows/get_uniquediskid.ps1"
        (self._backend.remote_client.
         manager.execute_powershell_resource_script(
             resource_location=resource_location))

    @util.skip_on_os([util.WINDOWS_NANO], "OS Version not supported")
    def prepare_cbinit_config(self, service_type):
        LOG.info("Injecting Boot config options in the config file.")
        self._cbinit_conf.append_conf_value(
            name="bcd_enable_auto_recovery", value="True")
        self._cbinit_conf.append_conf_value(
            name="set_unique_boot_disk_id", value="True")
        self._cbinit_conf.append_conf_value(
            name="bcd_boot_status_policy", value="ignoreallfailures")
        self._cbinit_conf.append_conf_value(
            name="plugins",
            value="cloudbaseinit.plugins.windows.bootconfig."
                  "BootStatusPolicyPlugin,"
                  "cloudbaseinit.plugins.windows.bootconfig."
                  "BCDConfigPlugin")


class CloudbaseinitRDPSettingsPlugin(CloudbaseinitRecipe):
    """Recipe for testing the RDPSettingsPlugin plugin"""

    @util.skip_on_os([util.WINDOWS_NANO], "OS Version not supported")
    def prepare_cbinit_config(self, service_type):
        LOG.info("Injecting rdp setting options in the config file.")
        self._cbinit_unattend_conf.append_conf_value(
            name="rdp_set_keepalive", value="true")
        self._cbinit_unattend_conf.append_conf_value(
            name="plugins",
            value="cloudbaseinit.plugins.windows.rdp."
                  "RDPSettingsPlugin")


class CloudbaseinitIndependentPlugins(CloudbaseinitRecipe):
    """Recipe for independent plugins."""
    METHODS = ('prepare_cbinit_config',
               'pre_sysprep')
    RECIPES = (CloudbaseinitEnableTrim, CloudbaseinitSANPolicy,
               CloudbaseinitPageFilePlugin, CloudbaseinitDisplayTimeoutPlugin,
               CloudbaseinitKMSHostPlugin, CloudbaseinitSetRealClock,
               CloudbaseinitBootConfigPlugin, CloudbaseinitRDPSettingsPlugin)

    def prepare_cbinit_config(self, service_type):
        super(CloudbaseinitIndependentPlugins, self).prepare_cbinit_config(
            service_type)
        self._cbinit_conf.set_conf_value(name="plugins", value="")

    def pre_sysprep(self):
        super(CloudbaseinitIndependentPlugins, self).pre_sysprep()


class CloudbaseinitRenameAdminUserPlugin(CloudbaseinitRecipe):

    def prepare_cbinit_config(self, service_type):
        super(CloudbaseinitRenameAdminUserPlugin, self).prepare_cbinit_config(
            service_type)
        LOG.info("Injecting guest rename_admin_user.")

        self._cbinit_conf.set_conf_value(name='rename_admin_user',
                                         value="True")
        LOG.info("Injecting new username value.")
        self._cbinit_conf.set_conf_value(name='username',
                                         value="RenamedAdminUser")
        self._cbinit_conf.append_conf_value(
            name="plugins",
            value="cloudbaseinit.plugins.windows.createuser."
                  "CreateUserPlugin")


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

        self.wait_cbinit_finalization()
        LOG.info("Finished preparing instance.")


class CloudbaseinitPasswordRecipe(CloudbaseinitWinrmRecipe):
    """A recipe for testing the WinRM configuration plugin."""

    def prepare_cbinit_config(self, service_type):
        super(CloudbaseinitPasswordRecipe,
              self).prepare_cbinit_config(service_type)
        self._cbinit_conf.set_conf_value(
            name="user_password_length",
            value="3")
