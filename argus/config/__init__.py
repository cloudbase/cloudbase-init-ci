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

import os

from oslo_config import cfg

from argus.config import factory
from argus import version

CONFIG = cfg.ConfigOpts()

for option_class in factory.get_options():
    option_class(CONFIG).register()

# NOTE(mmicu): Prioritize `argus.conf` configuration file
# from the current working directory
_DEFAULT_CONFIG_FILES = [
    config_file for config_file in ("/etc/argus/argus.conf",
                                    "etc/argus/argus.conf", "argus.conf")
    if os.path.isfile(config_file)
]

if _DEFAULT_CONFIG_FILES:
    CONFIG([], project='argus', version=version.get_version(),
           default_config_files=_DEFAULT_CONFIG_FILES)
