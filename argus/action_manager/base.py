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

import abc

import six


@six.add_metaclass(abc.ABCMeta)
class BaseActionManager(object):
    """Get a Action Manager that can handle basic actions.

    :param client:
        A Windows client to send command to the instance.
    :param conf:
        Argus config options.
    """

    def __init__(self, client, os_type):
        self._client = client
        self._os_type = os_type

    @abc.abstractmethod
    def download(self, uri, location):
        """Download the resource located at a specific URI in the location.

        :param uri:
            Remote URL where the data is found.

        :param location:
            Path from the instance in which we should download the
            remote resource.
        """
        pass

    @abc.abstractmethod
    def get_installation_script(self):
        """Get installation script for CloudbaseInit."""
        pass

    @abc.abstractmethod
    def install_cbinit(self):
        """Install Cloudbase-Init."""
        pass

    @abc.abstractmethod
    def sysprep(self):
        """Run the sysprep."""
        pass

    @abc.abstractmethod
    def wait_cbinit_service(self):
        """Wait if the Cloudbase-Init Service to stop."""
        pass

    @abc.abstractmethod
    def check_cbinit_service(self, searched_paths=None):
        """Check if the Cloudbase-Init service started.

        :param searched_paths:
            Paths to files that should exist if the heartbeat patch is
            applied.
        """
        pass

    @abc.abstractmethod
    def git_clone(self, repo_url, location, count, delay):
        """Clone from a remote repository to a specified location.

        :param repo_url: The remote repository URL.
        :param location: The target location for where to clone the repository.
        :param count:
            The number of tries that should be attempted in case it fails.
        :param delay: The time delay before retrying.

        :returns: True if the clone was successful, False if not.
        :raises: ArgusCLIError if the path is not valid.
        :rtype: bool
        """
        pass

    @abc.abstractmethod
    def wait_boot_completion(self):
        """Wait for the instance to be booted a reasonable period."""
        pass

    @abc.abstractmethod
    def specific_prepare(self):
        """Prepare some OS specific resources."""
        pass

    @abc.abstractmethod
    def remove(self, path):
        """Remove a file."""
        pass

    @abc.abstractmethod
    def rmdir(self, path):
        """Remove a directory."""

    @abc.abstractmethod
    def exists(self, path):
        """Check if the path exists."""
        pass

    @abc.abstractmethod
    def is_file(self, path):
        """Check if the file exists."""
        pass

    @abc.abstractmethod
    def is_dir(self, path):
        """Check if the directory exists."""
        pass

    @abc.abstractmethod
    def mkdir(self, path):
        """Create a directory in the instance if the path is valid.

        :param path:
            Remote path where the new directory should be created.
        """
        pass

    @abc.abstractmethod
    def mkfile(self, path):
        """Create a file in the instance if the path is valid.

        :param path:
            Remote path where the new file should be created.
        """
        pass

    @abc.abstractmethod
    def touch(self, path):
        """Update the access and modification time.

        If the file doesn't exist, an empty file will be created
        as side effect.
        """
        pass

    # TODO(mmicu): Make a Cloudbase-Init Action Manager and move
    # specific methods
    @abc.abstractmethod
    def prepare_config(self, cbinit_config, cbinit_unattend_conf):
        """Prepare Cloudbase-Init config for every OS.

        :param cbinit_config:
            Cloudbase-Init config file.
        :param cbinit_unattend_conf:
            Cloudbase-Init Unattend config file.
        """
        pass
