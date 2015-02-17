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
import time

import six

from argus import exceptions
from argus import util


LOG = util.get_logger()


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

    def _execute_with_stderr(self, cmd):
        """Execute the given command and fail when the command fails."""
        LOG.debug("Execute command:\n%s", cmd)
        stdout, stderr, return_code = self._remote_client.run_remote_cmd(cmd)
        if return_code:
            raise exceptions.ArgusError(
                "Command {command!r} failed with "
                "return code {return_code!r}."
                .format(command=cmd,
                        return_code=return_code))
        return stdout, stderr

    def _execute(self, cmd):
        """Execute and return only the stdout."""
        return self._execute_with_stderr(cmd)[0]

    def _execute_with_retry(self, cmd, retry_count=None,
                            retry_count_interval=5):
        """Run the given `cmd` until succeeds.

        :param cmd:
            A string, representing a command which needs to
            be executed on the underlying remote client.
        :param retry_count:
            The number of retries which this function has.
            If the value is ``None``, then the function will retry *forever*.
        :param retry_count_interval:
            The number of seconds to sleep when retrying a command.
        :returns: stdout, stderr
        :rtype: tuple
        """
        count = 0
        while True:
            try:
                return self._execute_with_stderr(cmd)
            except Exception as exc:  # pylint: disable=broad-except
                LOG.debug("Command failed with '%s'.\nRetrying...", exc)
                count += 1
                if retry_count and count >= retry_count:
                    raise exceptions.ArgusTimeoutError(
                        "Command {!r} failed too many times."
                        .format(cmd))
                time.sleep(retry_count_interval)

    def _run_cmd_until_condition(self, cmd, cond, retry_count=None,
                                 retry_count_interval=5):
        """Run the given `cmd` until a condition *cond* occurs.

        :param cmd:
            A string, representing a command which needs to
            be executed on the underlying remote client.
        :param cond:
            A callable which receives the stdout returned by
            executing the command. It should return a boolean value,
            which tells to this function to stop execution.
        :param retry_count:
            The number of retries which this function
            has until a successful run.
            If the value is ``None``, then the function will retry *forever*.
        :param retry_count_interval:
            The number of seconds to sleep when retrying a command.
        """
        while True:
            std_out, std_err = self._execute_with_retry(
                cmd, retry_count=retry_count,
                retry_count_interval=retry_count_interval)
            if std_err:
                raise exceptions.ArgusCLIError(
                    "executing command {!r} failed with {!r}"
                    .format(cmd, std_err))
            elif cond(std_out):
                break
            else:
                time.sleep(retry_count_interval)

    @abc.abstractmethod
    def prepare(self):
        """Call this method to provision an instance."""
