# Copyright 2015 Cloudbase Solutions Srl
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

"""Base recipe for preparing instances for Cloudbase-Init testing."""

import abc

import six

from argus import config as argus_config
from argus import log as argus_log
from argus.recipes import base

__all__ = ('BaseCloudbaseinitRecipe', )

CONFIG = argus_config.CONFIG
LOG = argus_log.LOG


@six.add_metaclass(abc.ABCMeta)
class BaseCloudbaseinitRecipe(base.BaseRecipe):
    """Base recipe for testing an instance with Cloudbase-Init.

    The method :meth:`~prepare` does all the necessary work for
    preparing a new instance. The executed steps are:

    * wait for boot completion.
    * get an install script for CloudbaseInit
    * installs CloudbaseInit
    * waits for the finalization of the installation.
    """

    def __init__(self, backend):
        super(BaseCloudbaseinitRecipe, self).__init__(backend)
        self._cbinit_conf = None
        self._cbinit_unattend_conf = None

    @abc.abstractmethod
    def wait_for_boot_completion(self):
        """Wait for the instance to finish up booting."""

    def set_mtu(self, interface=None, subinterface_name=None,
                mtu_value=None, store_type=None):
        """Sets the MTU value for the underlying instance.

        Sets the MTU value in order to avoid packet loss.
        More details about the parameters can be found below:
        https://technet.microsoft.com/en-us/library/cc731521(v=ws.10).aspx
        """
        pass

    def execution_prologue(self):
        """Executed before any downloaded script.

        Do extra things to assure a successful
        remote powershell (and others) script execution.
        """

    @abc.abstractmethod
    def get_installation_script(self):
        """Get the installation script for Cloudbase-Init."""

    @abc.abstractmethod
    def install_cbinit(self):
        """Install the Cloudbase-Init code."""

    @abc.abstractmethod
    def wait_cbinit_finalization(self):
        """Wait for the finalization of Cloudbase-Init."""

    def pre_sysprep(self):
        """Run finalization code before sysprepping."""

    @abc.abstractmethod
    def sysprep(self):
        """Do the final steps after installing Cloudbase-Init.

        This requires running sysprep on Windows, but on other
        platforms there might be no need for calling it.
        """

    @abc.abstractmethod
    def replace_install(self):
        """Do whatever is necessary to replace the installation."""

    @abc.abstractmethod
    def replace_code(self):
        """Do whatever is necessary to replace the code for Cloudbase-Init."""

    @abc.abstractmethod
    def prepare_cbinit_config(self, service_type):
        """Prepare the config objects.

        Prepare `self._cbinit_config` and `self._cbinit_unattend_conf
        ` objects.
        """
        self._cbinit_conf = None
        self._cbinit_unattend_conf = None

    @abc.abstractmethod
    def inject_cbinit_config(self):
        """Inject the config in the instance."""
        pass

    @abc.abstractmethod
    def get_cb_init_logs(self):
        """Get the Cloudbase-Init logs from the instance."""
        pass

    @abc.abstractmethod
    def get_cb_init_confs(self):
        """Get the Cloudbase-Init configs from the instance."""
        pass

    def prepare(self, service_type=None, **kwargs):
        """Prepare the underlying instance.

        The following operations will be executed:

        * wait for boot completion
        * get an installation script for CloudbaseInit
        * install CloudbaseInit by running the previously downloaded file.
        * wait until the instance is up and running.
        """
        LOG.info("Preparing instance...")
        self.wait_for_boot_completion()
        self.set_mtu()
        self.execution_prologue()
        self.get_installation_script()
        self.install_cbinit()
        self.replace_install()
        self.replace_code()
        self.prepare_cbinit_config(service_type)
        self.inject_cbinit_config()
        self.pre_sysprep()
        if CONFIG.argus.pause:
            six.moves.input("Press Enter to continue...")

        self.sysprep()
        self.wait_cbinit_finalization()
        LOG.info("Finished preparing instance.")
        self.get_cb_init_logs()
        self.get_cb_init_confs()
