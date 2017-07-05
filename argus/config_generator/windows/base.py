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

import abc
import ntpath
import six

try:
    from StringIO import StringIO
except ImportError:
    import io as StringIO

from argus.config_generator import base
from argus import log as argus_log
from argus import util


LOG = argus_log.LOG


class BaseWindowsConfig(base.BaseConfig):
    """Class that abstract the config files for windows.

    For any config type we need to know:
    :param default_config:
       Path to default config relative to `argus/resources`
    :param name:
        Name of the file in the instance
    """

    default_config = None
    config_name = None

    """An object that holds the Cloudbase-Init config."""

    def __init__(self, client):
        """Every Config Object needs a client.

        :param client:
            A client connected to the instance.
        """
        super(BaseWindowsConfig, self).__init__(client)
        self._conf = self._get_base_conf(self.default_config)
        self._config_specific_paths()

    @property
    def conf(self):
        """Return the ConfigParser object."""
        return self._conf

    @staticmethod
    def _get_base_conf(config_name):
        """Return a ConfigParser object with default values."""
        base_conf = StringIO(
            util.get_resource(config_name))
        conf = six.moves.configparser.ConfigParser()

        # NOTE(dtoncu): `readfp` is deprecated since Python 3.2,
        # but it was replaced with `read_file`.
        # pylint: disable=deprecated-method, maybe-no-member
        if six.PY2:
            conf.readfp(base_conf)
        else:
            conf.read_file(base_conf)

        return conf

    @abc.abstractmethod
    def _config_specific_paths(self):
        """Populate the ConfigParser object with instance specific values."""
        pass

    def apply_config(self, path):
        """Write the configuration values in the right place.

            Take the current state of the `self.conf` object and
            write it to the specific path.The name of the file
            will be `config_name`.

        :param path:
            Path to the directory in which the config file is created.
        """
        file_path = ntpath.join(path, self.config_name)
        if self._client.manager.is_file(file_path):
            self._client.manager.remove(file_path)

        buff = StringIO()
        self.conf.write(buff)
        buff.seek(0)
        data = buff.read()

        LOG.debug("Writing data in file '%s'.", file_path)
        for line in data.splitlines():
            self._client.write_file(data=line, remote_destination=file_path)
