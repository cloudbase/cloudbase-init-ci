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
import os

import six

from argus import util


LOG = util.get_logger()


@six.add_metaclass(abc.ABCMeta)
class BaseBackend(object):
    """Class for managing instances

    The *backend* is used for building and managing an underlying
    instance, being it an OpenStack instance, OpenNebula instance
    or a containerized OS.

    :param conf:
        A configuration object, which holds argus related info.
    :param name:
        The name of the instance that will be created.
    :param userdata:
        If any, the userdata which will be available in the
        instance to the corresponding cloud initialization
        service.
    :param metadata:
        If any, the metadata which should be available in the
        instance to the correpsonding cloud initialization
        service.
    """
    def __init__(self, conf, name=None, userdata=None, metadata=None,
                 availability_zone=None):
        self._name = name
        self._conf = conf
        self._availability_zone = availability_zone

        self.userdata = userdata
        self.metadata = metadata

    @abc.abstractmethod
    def setup_instance(self):
        """Setup an underlying instance."""

    @abc.abstractmethod
    def cleanup(self):
        """Destroy and cleanup the relevant resources created by setup_instance."""


class CloudBackend(BaseBackend):
    """Base backend for cloud related tasks"""

    @staticmethod
    def _get_log_template(suffix):
        template = "{}{}.log".format("{}", "-" + suffix if suffix else "")
        return template

    def save_instance_output(self, suffix=None):
        """Retrieve and save all data written through the COM port.

        If a `suffix` is provided, then the log name is preceded by it.
        """
        if not self._conf.argus.output_directory:
            return

        template = self._get_log_template(suffix)
        path = os.path.join(self._conf.argus.output_directory,
                            template.format(self.internal_instance_id()))
        content = self.instance_output()
        if not content.strip():
            LOG.warn("Empty console output; nothing to save.")
            return

        LOG.info("Saving instance console output to: %s", path)
        with open(path, "wb") as stream:
            stream.write(content)

    @abc.abstractmethod
    def instance_output(self, limit=None):
        """Get the underlying's instance output, if any."""

    @abc.abstractmethod
    def internal_instance_id(self):
        """Get the underlying's instance id, depending on the internals of the backend."""

    @abc.abstractmethod
    def reboot_instance(self):
        """Reboot the underlying instance."""

    @abc.abstractmethod
    def instance_password(self):
        """Get the underlying instance password, if any."""

    @abc.abstractmethod
    def private_key(self):
        """Get the underlying private key."""

    @abc.abstractmethod
    def public_key(self):
        """Get the underlying public key."""

    @abc.abstractmethod
    def floating_ip(self):
        """Get the floating ip that was attached to the underlying instance."""

    @abc.abstractmethod
    def get_remote_client(self, username=None, password=None, **kwargs):
        """Get a remote client to the underlying instance.

        This is different than :attr:`remote_client`, because that
        will always return a client with predefined credentials,
        while this method allows for a fine-grained control
        over this aspect.
        `password` can be omitted if authentication by
        SSH key is used.
        The **kwargs parameter can be used for additional options
        (currently none).
        """

    @abc.abstractproperty
    def remote_client(self):
        """An astract property which should return the default client."""
