# Copyright 2016 Cloudbase Solutions Srl
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

import logging as base_logging

from argus import util


URI = "fake/uri"
URL = "fake/url"
LOCATION = "fake/location"
BASE_RESOURCE = "fake/resources/"
RESOURCE_LOCATION = "fake/resource/location"
PARAMETERS = "--parameter fake"
CBINIT_RESOURCE_LOCATION = "windows/installCBinit.ps1"
CBINIT_LOCATION = r"C:\installCBinit.ps1"
SYSPREP_RESOURCE_LOCATION = "windows/sysprep.ps1"
SEARCHED_PATHS = [r"first\fake\path", r"second\fake\path", r"third\fake\path"]
USERNAME = "fake_username"
PATH = r"fake\path"
PATH_TYPE = "FakeType"
ITEM_TYPE = "FakeType"


# This is similar with unittest.TestCase.assertLogs from Python 3.4.
class SnatchHandler(base_logging.Handler):
    def __init__(self, *args, **kwargs):
        super(SnatchHandler, self).__init__(*args, **kwargs)
        self.output = []

    def emit(self, record):
        msg = self.format(record)
        self.output.append(msg)


class LogSnatcher(object):
    """A context manager to capture emitted logged messages.

    The class can be used as following::

        with LogSnatcher('argus.util.decrypt_password') as snatcher:
            LOG.info("doing stuff")
            LOG.info("doing stuff %s", 1)
            LOG.warn("doing other stuff")
            ...
        self.assertEqual(snatcher.output,
                         ['INFO:unknown:doing stuff',
                          'INFO:unknown:doing stuff 1',
                          'WARN:unknown:doing other stuff'])
    """

    @property
    def output(self):
        return self._snatch_handler.output

    def __init__(self, logger_name):
        self._logger_name = logger_name
        self._snatch_handler = SnatchHandler()
        self._logger = util.get_logger()
        self._previous_level = self._logger.getEffectiveLevel()

    def __enter__(self):
        self._logger.setLevel(base_logging.DEBUG)
        self._logger.handlers.append(self._snatch_handler)
        return self

    def __exit__(self, *args):
        self._logger.handlers.remove(self._snatch_handler)
        self._logger.setLevel(self._previous_level)
