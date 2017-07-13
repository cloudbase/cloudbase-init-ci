# Copyright 2017 Cloudbase Solutions Srl
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

"""Config options available for the local setup."""

from oslo_config import cfg

from argus.config import base as conf_base


class LocalOptions(conf_base.Options):

    """Config options available for the local setup."""

    def __init__(self, config):
        super(LocalOptions, self).__init__(config, group="local")
        self._options = [
            cfg.StrOpt(
                "ip", required=True,
                help="The ip of the machine that is to be used."),
            cfg.StrOpt(
                "username", default="CiAdmin", required=True,
                help="The default username existing on Argus-CI images used "
                     "for connecting and interacting with the instance."),
            cfg.StrOpt(
                "password", required=True,
                help="The password for the default username."),
        ]

    def register(self):
        """Register the current options to the global ConfigOpts object."""
        group = cfg.OptGroup(self.group_name, title='Local Options')
        self._config.register_group(group)
        self._config.register_opts(self._options, group=group)

    def list(self):
        """Return a list which contains all the available options."""
        return self._options
