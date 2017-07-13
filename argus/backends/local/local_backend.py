# Copyright 2017 Cloudbase Solutions Srl
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

from argus.backends import base as base_backend
from argus.backends import windows as windows_backend
from argus import config as argus_config

CONFIG = argus_config.CONFIG


class LocalBackend(windows_backend.WindowsBackendMixin,
                   windows_backend.BaseMetadataProviderMixin,
                   base_backend.BaseBackend):
    """Local Backend for testing Windows machines
        that are running, have git installed and winrm configured"""
    def __init__(self, name=None, userdata=None, metadata=None,
                 availability_zone=None):
        super(LocalBackend, self).__init__(name=name, userdata=userdata,
                                           metadata=metadata,
                                           availability_zone=availability_zone)
        self._username = CONFIG.local.username
        self._password = CONFIG.local.password
        self._ip = CONFIG.local.ip

    def get_remote_client(self, protocol='http', **kwargs):
        super(LocalBackend, self).get_remote_client(self._username,
                                                    self._password,
                                                    protocol, **kwargs)

    def setup_instance(self):
        pass

    def cleanup(self):
        pass

    def save_instance_output(self):
        pass

    def get_password(self):
        return lambda: self._password

    def get_username(self):
        return lambda: self._username

    def floating_ip(self):
        return self._ip
