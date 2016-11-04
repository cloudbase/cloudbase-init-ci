# Copyright 2016 Cloudbase Solutions Srl
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

"""Config options available for the Cloudbase-Init setup."""

from oslo_config import cfg

from argus.config import base as conf_base


class CloudbaseInitOptions(conf_base.Options):

    """Config options available for the Cloudbase-Init setup."""

    def __init__(self, config):
        super(CloudbaseInitOptions, self).__init__(config,
                                                   group="cloudbaseinit")
        self._options = [
            cfg.StrOpt("created_user", default="Admin", required=True,
                       help="Represents the user that will be created on the "
                            "underlying instance by Cloudbase-init."),
            cfg.StrOpt("group", default="Administrators", required=True,
                       help="Represents the group in which the 'created_user' "
                            "will be added to by Cloudbase-init."),
            cfg.BoolOpt("activate_windows", default=False, required=True,
                        help="Specifies whether Cloudbase-init will try to "
                             "run the activation plugin on the instance."),
        ]

    def register(self):
        """Register the current options to the global ConfigOpts object."""
        group = cfg.OptGroup(self.group_name, title='Cloudbase-Init Options')
        self._config.register_group(group)
        self._config.register_opts(self._options, group=group)

    def list(self):
        """Return a list which contains all the available options."""
        return self._options
