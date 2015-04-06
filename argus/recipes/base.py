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

"""Contains base recipes functionality.

A recipe is a class which knows how to provision an instance,
by installing and configuring it with what it's necessary.
"""

import abc

import six

from argus import util


LOG = util.get_logger()
RETRY_COUNT = 15
RETRY_DELAY = 10


__all__ = (
    'BaseRecipe',
)


@six.add_metaclass(abc.ABCMeta)
class BaseRecipe(object):
    """Base class for a recipe.

    A recipe is a way in which an instance can be provisioned with
    some easy steps.
    """

    def __init__(self, instance_id, api_manager, remote_client, image,
                 service_type, output_directory=None):
        self._api_manager = api_manager
        self._instance_id = instance_id
        self._remote_client = remote_client
        self._image = image
        self._service_type = service_type
        self._output_directory = output_directory

    def _execute(self, cmd, count=RETRY_COUNT, delay=RETRY_DELAY):
        """Execute until success and return only the standard output."""

        # A positive exit code will trigger the failure
        # in the underlying methods as an `ArgusError`.
        # Also, if the retrying limit is reached, `ArgusTimeoutError`
        # will be raised.
        return self._remote_client.run_command_with_retry(
            cmd, count=count, delay=delay)[0]

    def _execute_until_condition(self, cmd, cond, count=RETRY_COUNT,
                                 delay=RETRY_DELAY):
        """Execute a command until the condition is met without returning."""
        self._remote_client.run_command_until_condition(
            cmd, cond, count=count, delay=delay)

    @abc.abstractmethod
    def prepare(self):
        """Call this method to provision an instance."""
