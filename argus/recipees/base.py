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

"""Contains base recipees functionality.

A recipee is a class which knows how to provision an instance,
by installing and configuring it with what it's necessary.
"""

import abc
import time

import six

from argus import exceptions
from argus import util


LOG = util.get_logger()


__all__ = (
    'BaseRecipee',
)


@six.add_metaclass(abc.ABCMeta)
class BaseRecipee(object):
    """Base class for a recipee.

    A recipee is a way in which an instance can be provisioned with
    some easy steps.
    """

    def __init__(self, instance_id, api_manager, remote_client, image,
                 service_type):
        self._api_manager = api_manager
        self._instance_id = instance_id
        self._remote_client = remote_client
        self._image = image
        self._service_type = service_type

    def _execute(self, cmd):
        """Execute the given command and fail when the command fails."""
        stdout, stderr, return_code = self._remote_client.run_remote_cmd(cmd)
        if return_code:
            raise exceptions.ArgusError(
                "Command {command!r} failed with "
                "return code {return_code!r}"
                .format(command=cmd,
                        return_code=return_code))
        return stdout, stderr

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
            The number of retries which this function has.
            If the value is ``None``, then the function will run *forever*.
        :param retry_count_interval:
            The number of seconds to sleep when retrying a command.
        """
        count = 0
        while True:
            try:
                std_out, std_err = self._execute(cmd)
            except Exception:  # pylint: disable=broad-except
                LOG.debug("Command %r failed while waiting for condition",
                          cmd)
                count += 1
                if retry_count and count >= retry_count:
                    raise exceptions.ArgusTimeoutError(
                        "Command {!r} failed too many times."
                        .format(cmd))
                time.sleep(retry_count_interval)
            else:
                if std_err:
                    raise exceptions.ArgusCLIError(
                        "Executing command {!r} failed with {!r}"
                        .format(cmd, std_err))
                elif cond(std_out):
                    break
                else:
                    time.sleep(retry_count_interval)

    @abc.abstractmethod
    def prepare(self):
        """Call this method to provision an instance."""
