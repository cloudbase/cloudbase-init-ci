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

"""Base recipee for preparing instances for cloudbaseinit testing."""

import abc

import six

from argus.recipees import base
from argus import util


__all__ = ('BaseCloudbaseinitRecipee', )


CONF = util.get_config()
LOG = util.get_logger()


@six.add_metaclass(abc.ABCMeta)
class BaseCloudbaseinitRecipee(base.BaseRecipee):
    """Base recipee for testing an instance with Cloudbaseinit.

    The method :meth:`~prepare` does all the necessary work for
    preparing a new instance. The executed steps are:

    * wait for boot completion.
    * get an install script for CloudbaseInit
    * installs CloudbaseInit
    * waits for the finalization of the installation.
    """

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
        self.replace_code()
        self.sysprep()
        self.wait_reboot()
        self.wait_cbinit_finalization()
        LOG.info("Finished preparing instance %s", self._instance_id)

    if CONF.argus.debug:
        prepare = util.trap_failure(prepare)
