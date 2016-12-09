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

import os
import logging

from argus import config as argus_config

CONFIG = argus_config.CONFIG


DEFAULT_FORMAT = ('%(scenario)s - %(os_type)s - %(asctime)s - %(name)s - '
                  '%(levelname)s - %(message)s')


def get_logger(name="argus",
               format_string=DEFAULT_FORMAT,
               logging_file=CONFIG.argus.argus_log_file):
    """Obtain a new logger object.

    The `name` parameter will be the name of the logger and `format_string`
    will be the format it will use for logging. `logging_file` is a file
    where the messages will be written.
    """
    extra = {"scenario": "unknown", "os_type": "unknown"}

    logger = logging.getLogger(name)
    formatter = logging.Formatter(format_string)

    if not logger.handlers:
        # If the logger wasn't obtained another time,
        # then it shouldn't have any loggers

        if logging_file:
            file_handler = logging.FileHandler(logging_file, delay=True)
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)

    logger.setLevel(logging.DEBUG)
    logger_adapter = logging.LoggerAdapter(logger, extra)
    return logger_adapter


def set_scenario_name(log, name):
    """Set a scenario name for a given logger object.

    :param log: A logging handler.
    """
    log.extra["scenario"] = name


def add_new_handler(log, format_string=DEFAULT_FORMAT):
    """Add a new FileHandler if it is specified in config

    :param log: A logging handler.
    """
    if CONFIG.argus.log_each_scenario:
        directory = os.path.dirname(os.path.abspath(
            CONFIG.argus.argus_log_file))
        logging_file_name = "argus-{}-{}.log".format(
            log.extra.get("scenario", ""), log.extra.get("os_type", ""))
        logging_file = os.path.join(directory, logging_file_name)

        formatter = logging.Formatter(format_string)
        file_handler = logging.FileHandler(logging_file, delay=True)
        file_handler.setFormatter(formatter)

        log.logger.addHandler(file_handler)


LOG = get_logger()
