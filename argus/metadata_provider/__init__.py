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

from argus import config as argus_config
from argus.metadata_provider import arestor_provider

CONFIG = argus_config.CONFIG


def get_provider(recipe, backend):
    """Get metadata provider."""
    if CONFIG.argus.use_arestor:
        arestor_client = arestor_provider.ArestorMetadataProvider(
            backend=backend, recipe=recipe)
        return arestor_client

    return backend
