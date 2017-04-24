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

from argus import util


# pylint: disable=unused-argument
def _get_provider_map(recipe, backend):
    """Get a map with all metadata providers."""
    # NOTE(mmicu): The `backend` is the class responsible for creating
    # the cloud infrastructure (instance, security group, networks, ...)
    return {
        util.HTTP_SERVICE: backend,
        util.CONFIG_DRIVE_SERVICE: backend,
        util.EC2_SERVICE: backend,
        util.OPEN_NEBULA_SERVICE: backend,
        util.CLOUD_STACK_SERVICE: backend,
        util.MAAS_SERVICE: backend
    }


def get_provider(recipe, backend, service_type):
    """Get metadata provider."""
    provider_list = _get_provider_map(recipe, backend)
    return provider_list.get(service_type, backend)
