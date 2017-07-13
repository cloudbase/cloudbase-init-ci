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

_OPT_PATHS = (
    'argus.config.ci.ArgusOptions',
    'argus.config.cloudbaseinit.CloudbaseInitOptions',
    'argus.config.openstack.OpenStackOptions',
    'argus.config.mock_cloudstack.MockCloudStackOptions',
    'argus.config.mock_ec2.MockEC2Options',
    'argus.config.mock_maas.MockMAASOptions',
    'argus.config.mock_openstack.MockOpenStackOptions',
    'argus.config.arestor.ArestorOptions',
    'argus.config.local.LocalOptions',
)


def _load_class(class_path):
    """Load the module and return the required class."""
    parts = class_path.rsplit('.', 1)
    module = __import__(parts[0], fromlist=parts[1])
    return getattr(module, parts[1])


def get_options():
    """Return a list of all the available `Options` subclasses."""
    return [_load_class(class_path) for class_path in _OPT_PATHS]
