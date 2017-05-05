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

"""Config options available for the Arestor metadata service."""

from oslo_config import cfg

from argus.config import base as config_base


class ArestorOptions(config_base.Options):

    """Config options available for the Arestor metadata service."""

    def __init__(self, config):
        super(ArestorOptions, self).__init__(config,
                                             group="arestor")
        self._options = [
            cfg.StrOpt(
                "base_url",
                default="http://127.0.0.1:8080",
                help="The base URL for this service"),
            cfg.StrOpt(
                "api_key", default=None,
                help="The api key for the arestor user."),
            cfg.StrOpt(
                "secret", default=None,
                help="The secret for the arestor user"),
        ]

    def register(self):
        """Register the current options to the global ConfigOpts object."""
        group = cfg.OptGroup(self.group_name, title='Arestor Options')
        self._config.register_group(group)
        self._config.register_opts(self._options, group=group)

    def list(self):
        """Return a list which contains all the available options."""
        return self._options
