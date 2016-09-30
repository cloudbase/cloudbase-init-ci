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

import abc

import six


@six.add_metaclass(abc.ABCMeta)
class BaseClient(object):
    """Get a remote client to a Windows instance.

    :param hostname:
        A hostname where the client should connect. This can be
        anything that the client needs (an ip, a fully qualified domain
        name etc.).
    """

    def __init__(self, hostname, username, password, cert_pem, cert_key):
        self._hostname = hostname
        self._username = username
        self._password = password
        self._cert_pem = cert_pem
        self._cert_key = cert_key

    @abc.abstractmethod
    def run_remote_cmd(self, command, command_type=None):
        """Run the given remote command.

        The command will be executed on the remote underlying server.
        It will return a tuple of three elements, stdout, stderr
        and the return code of the command.
        """
