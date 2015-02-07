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
import operator

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


class _Option(object):
    def __init__(self, option, method='get', default=None):
        self._option = option
        self._method = method
        self._default = default

    def __get__(self, instance, owner=None):
        # pylint: disable=protected-access
        return instance._get_option(self._option,
                                    self._method,
                                    self._default)


class _ScenarioSection(object):
    """Parser for a scenario section.

    This parser handles the parsing of scenario sections,
    taking in account their parents, if any.
    To specify a parent for a scenario, use this syntax:

       [scenario inherits base_scenario]
    """

    def __init__(self, section_key, parser):
        self._parser = parser
        self._parent = None
        self._key = section_key
        self.scenario_name = None

        name, attr, parent = section_key.partition(" inherits ")
        if attr:
            self._parent = parent.strip()
        self.scenario_name = name.strip().partition("scenario_")[2]

    def _get_option(self, option, method='get', default=None):
        local_getter = operator.methodcaller(method, self._key, option)
        parent_getter = operator.methodcaller(method, self._parent, option)
        try:
            return local_getter(self._parser)
        except six.moves.configparser.NoOptionError:
            if self._parent:
                try:
                    return parent_getter(self._parser)
                except six.moves.configparser.NoOptionError:
                    if default:
                        return default
            raise

    scenario_class = _Option(option='scenario')
    test_classes = _Option(option='test_classes',
                           method='getlist')
    recipe = _Option(option='recipe')
    userdata = _Option(option='userdata')
    metadata = _Option(option='metadata')
    image = _Option(option='image')
    scenario_type = _Option(option='type')
    service_type = _Option(option='service_type', default='http')
    introspection = _Option(option='introspection')


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
                                   'name default_ci_username '
                                   'default_ci_password image_ref flavor_ref '
                                   'group created_user os_type')
    scenario = collections.namedtuple('scenario',
                                      'name scenario test_classes recipe '
                                      'userdata metadata image type '
                                      'service_type introspection')
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
        ci_user = _get_default(parser, key, 'default_ci_username', 'CiAdmin')
        ci_password = _get_default(parser, key, 'default_ci_password',
                                   'Passw0rd')
        image_ref = parser.get(key, 'image_ref')
        flavor_ref = parser.get(key, 'flavor_ref')
        group = parser.get(key, 'group')
        created_user = parser.get(key, 'created_user')
        os_type = _get_default(parser, key, 'os_type', 'Windows')
        images.append(image(image_name, ci_user, ci_password,
                            image_ref, flavor_ref, group, created_user,
                            os_type))

    # Get the scenarios section
    images_names = {image.name: image for image in images}
    scenarios = []
    for key in parser.sections():
        if not key.startswith("scenario_"):
            continue
        section = _ScenarioSection(key, parser)
        image = images_names[section.image]

        scenarios.append(scenario(section.scenario_name,
                                  section.scenario_class,
                                  section.test_classes,
                                  section.recipe,
                                  section.userdata,
                                  section.metadata,
                                  image,
                                  section.scenario_type,
                                  section.service_type,
                                  section.introspection))

    return conf(argus, cloudbaseinit, images, scenarios)
