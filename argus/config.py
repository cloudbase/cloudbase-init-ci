# Copyright 2014 Cloudbase Solutions Srl
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

import collections
import itertools

import six


class _ConfigParser(six.moves.configparser.ConfigParser):
    def getlist(self, section, option):
        value = self.get(section, option)
        values = value.splitlines()
        iters = (map(str.strip, filter(None, value.split(",")))
                 for value in values)
        return list(itertools.chain.from_iterable(iters))


def _get_default(parser, section, option, default=None):
    try:
        return parser.get(section, option)
    except six.moves.configparser.NoOptionError:
        return default


def parse_config(filename):
    """Parse the given config file.

    It will return a object with four attributes, ``argus``
    for general argus options, ``cloudbaseinit`` for options
    related to cloudbaseinit, scenarios for the list of scenarios
    and ``images``, a list of image objects with some attributes
    exported, such as ``image_ref`` and so on.
    """
    # pylint: disable=too-many-locals
    argus = collections.namedtuple('argus',
                                   'resources debug path_to_private_key '
                                   'file_log log_format dns_nameservers')
    cloudbaseinit = collections.namedtuple('cloudbaseinit',
                                           'expected_plugins_count')
    image = collections.namedtuple('image',
                                   'name service_type default_ci_username '
                                   'default_ci_password image_ref flavor_ref '
                                   'group created_user os_type')
    scenario = collections.namedtuple('scenario',
                                      'name scenario test_classes recipee '
                                      'userdata metadata image')
    conf = collections.namedtuple('conf',
                                  'argus cloudbaseinit images scenarios')

    parser = _ConfigParser()
    parser.read(filename)

    # Get the argus section
    resources = _get_default(
        parser, 'argus', 'resources',
        'https://raw.githubusercontent.com/PCManticore/'
        'argus-ci/master/argus/resources')
    debug = parser.getboolean('argus', 'debug')
    path_to_private_key = parser.get('argus', 'path_to_private_key')
    file_log = _get_default(parser, 'argus', 'file_log')
    log_format = _get_default(parser, 'argus', 'log_format')
    dns_nameservers = _get_default(
        parser, 'argus', 'dns_nameservers',
        ['8.8.8.8', '8.8.4.4'])
    if not isinstance(dns_nameservers, list):
        # pylint: disable=no-member
        dns_nameservers = dns_nameservers.split(",")

    argus = argus(resources, debug, path_to_private_key,
                  file_log, log_format, dns_nameservers)

    # Get the cloudbaseinit section
    try:
        expected_plugins_count = parser.getint(
            'cloudbaseinit',
            'expected_plugins_count')
    except (six.moves.configparser.NoOptionError, ValueError):
        expected_plugins_count = 13

    cloudbaseinit = cloudbaseinit(expected_plugins_count)

    # Get the images section
    images = []
    for key in parser.sections():
        if not key.startswith("image_"):
            continue
        image_name = key.partition("image_")[2]
        service_type = _get_default(parser, key, 'service_type', 'http')
        ci_user = _get_default(parser, key, 'default_ci_username', 'CiAdmin')
        ci_password = _get_default(parser, key, 'default_ci_password',
                                   'Passw0rd')
        image_ref = parser.get(key, 'image_ref')
        flavor_ref = parser.get(key, 'flavor_ref')
        group = parser.get(key, 'group')
        created_user = parser.get(key, 'created_user')
        os_type = _get_default(parser, key, 'os_type', 'Windows')
        images.append(image(image_name, service_type, ci_user, ci_password,
                            image_ref, flavor_ref, group, created_user,
                            os_type))

    # Get the scenarios section
    scenarios = []
    for key in parser.sections():
        if not key.startswith("scenario_"):
            continue

        scenario_class = parser.get(key, 'scenario')
        scenario_name = key.partition("scenario_")[2]
        test_classes = parser.get(key, 'test_classes')

        test_classes = parser.getlist(key, 'test_classes')
        recipee = parser.get(key, 'recipee')
        userdata = parser.get(key, 'userdata')
        metadata = parser.get(key, 'metadata')
        image = parser.get(key, 'image')
        scenarios.append(scenario(scenario_name, scenario_class, test_classes,
                                  recipee, userdata, metadata, image))

    return conf(argus, cloudbaseinit, images, scenarios)
