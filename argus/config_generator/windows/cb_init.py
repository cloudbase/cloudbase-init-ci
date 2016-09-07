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
import ntpath

import six

from argus.config_generator.windows import base
from argus.introspection.cloud import windows as introspect
from argus import util


class BasePopulatedCBInitConfig(base.BaseWindowsConfig):
    """An object that holds the cloudbaseinit config."""

    SERVICES = {
        util.HTTP_SERVICE:         "httpservice.HttpService",
        util.CONFIG_DRIVE_SERVICE: "configdrive.ConfigDriveService",
        util.EC2_SERVICE:          "ec2service.EC2Service",
        util.OPEN_NEBULA_SERVICE:  "opennebulaservice.OpenNebulaService",
        util.CLOUD_STACK_SERVICE:  "cloudstack.CloudStack",
        util.MAAS_SERVICE:         "maasservice.MaaSHttpService"
    }

    def __init__(self, client):
        super(BasePopulatedCBInitConfig, self).__init__(client)

    def set_conf_value(self, name, value="", section="DEFAULT"):
        """Set a config value in the specified section."""
        if section == "DEFAULT":
            self.conf.set(section, name, value)
            return
        elif self.conf.has_section(section):
            self.conf.set(section, name, value)
            return
        else:
            self.conf.add_section(section)
            self.conf.set(section, name, value)

    def _execute(self, cmd, count=util.RETRY_COUNT, delay=util.RETRY_DELAY,
                 command_type=None):
        """Execute until success and return only the standard output

        A positive exit code will trigger the failure
        in the underlying methods as an `ArgusError`.
        Also, if the retrying limit is reached, `ArgusTimeoutError`
        will be raised.
        """
        return self._client.run_command_with_retry(
            cmd, count=count, delay=delay, command_type=command_type)[0]

    def _config_specific_paths(self):
        """Populate the ConfigParser object with instance specific values."""
        cbinit_dir = introspect.get_cbinit_dir(self._execute)

        self.set_conf_value("bsdtar_path",
                            ntpath.join(cbinit_dir, r'bin\bsdtar.exe'))
        self.set_conf_value("local_scripts_path",
                            ntpath.join(cbinit_dir, 'LocalScripts\\'))
        self.set_conf_value("logdir",
                            ntpath.join(cbinit_dir, "log\\"))
        self.set_conf_value("mtools_path",
                            ntpath.join(cbinit_dir, "bin\\"))

    def _get_service(self, service_type):
        """Returns the Cloudbase-init config value.

        :param service_type:
            This can be http, configdrive, ec2, opennebula,
            cloudstack or maas.
        """
        return '.'.join([util.SERVICES_PREFIX, self.SERVICES[service_type]])

    def set_service_type(self, service_type):
        """Set the service type config.

        :param service_type:
            This can be a string like http, configdrive, ec2, opennebula,
            cloudstack, MAAS or it can be a list with the required service
            types. The order is important.!

        ::
        Example:
        ::
            [uti.MAAS_SERVICE, util.EC2_SERVICE]
        """
        service_type = service_type or util.HTTP_SERVICE
        if isinstance(service_type, six.string_types):
            service_type = [service_type]

        service_type = [self._get_service(serv) for serv in service_type]
        conf_value = ",".join(service_type)
        self.set_conf_value("metadata_services", conf_value)

    def apply_config(self, path):
        """Write the configuration values in the right place.

            Take the curent state of the `self.conf` object and
            write it to the specific path.The name of the file
            will be `config_name`.

        :param path:
            Path to the directory in which the config file is created.
        """
        super(BasePopulatedCBInitConfig, self).apply_config(path)

        # NOTE(mmicu): Because python2.x does not support UTF-8 we need to
        #              convert the config file.
        file_path = ntpath.join(path, self.config_name)
        cmd = ("(get-content '{filename}')| "
               "out-file '{filename}' -encoding ascii")
        self._client.run_command_with_retry(cmd.format(filename=file_path),
                                            command_type=util.POWERSHELL)


class CBInitConfig(BasePopulatedCBInitConfig):
    """Config object for cloudbase-init.conf."""

    default_config = "cloudbase-init.conf-template"
    config_name = "cloudbase-init.conf"


class UnattendCBInitConfig(BasePopulatedCBInitConfig):
    """Config object for cloudbase-init-unattend.conf."""

    default_config = "cloudbase-init-unattend.conf-template"
    config_name = "cloudbase-init-unattend.conf"
