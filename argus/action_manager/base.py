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

    def __init__(self, client, conf, os_type):
        self._client = client
        self._os_type = os_type
        self._conf = conf

    @abc.abstractmethod
    def download(self, uri, location):
        """Download the resource locatet at a specific uri in the location.

        :param uri:
            Remote url where the data is found.

        :param location:
            Path from the instance in which we should download the
            remote resouce.
        """
        pass

    @abc.abstractmethod
    def get_installation_script(self):
        """Get instalation script for CloudbaseInit."""
        pass

    @abc.abstractmethod
    def install_cbinit(self, service_type):
        """Install CloudBase-Init.

        :param service_type:
            The metadata service type. It can be:
            http, ec2, configdrive, opennebula, cloudstack and  mass.
            This parameter will dictate what config option is put in
            cloubase-init.conf.
        """
        pass

    @abc.abstractmethod
    def sysprep(self):
        """Run the sysprep."""
        pass

    @abc.abstractmethod
    def wait_cbinit_service(self):
        """Wait if the CloudBase Init Service to stop."""
        pass

    @abc.abstractmethod
    def check_cbinit_service(self, searched_paths=None):
        """Check if the CloudBase Init service started.

        :param searched_paths:
            Paths to files that should exist if the hearbeat patch is
            aplied.
        """
        pass

    @abc.abstractmethod
    def git_clone(self, repo_url, location):
        """Clone from an remote repo to a specific location on the instance.

        :param repo_url:
            The remote repo url.
        :param location:
            Specific location on the instance.
        """
        pass

    @abc.abstractmethod
    def wait_boot_completion(self):
        """Wait for the instance to be booted a resonable period."""
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
