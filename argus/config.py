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


_SENTINEL = object()


class _ConfigParser(six.moves.configparser.ConfigParser):
    def getlist(self, section, option):
        value = self.get(section, option)
        values = value.splitlines()
        iters = (map(str.strip, filter(None, value.split(",")))
                 for value in values)
        return list(itertools.chain.from_iterable(iters))

    # Don't lowercase.
    optionxform = str


def _get_default(parser, section, option, default=None):
    try:
        return parser.get(section, option)
    except six.moves.configparser.NoOptionError:
        return default


class _Option(object):
    def __init__(self, option, method='get', default=_SENTINEL):
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

       [scenario : base_scenario]
    """

    def __init__(self, section_key, parser):
        self._parser = parser
        self._parent = None
        self._key = section_key
        self.scenario_name = None

        name, attr, parent = section_key.partition(":")
        if attr:
            self._parent = parent.strip()
        self.scenario_name = name.strip().partition("scenario_")[2]

    def _get_option(self, option, method='get', default=_SENTINEL):
        local_getter = operator.methodcaller(method, self._key, option)
        parent_getter = operator.methodcaller(method, self._parent, option)
        try:
            return local_getter(self._parser)
        except six.moves.configparser.NoOptionError:
            if self._parent:
                try:
                    return parent_getter(self._parser)
                except six.moves.configparser.NoOptionError:
                    pass
            if default is not _SENTINEL:
                return default
            raise

    scenario_class = _Option(option='scenario')
    test_classes = _Option(option='test_classes',
                           method='getlist')
    recipe = _Option(option='recipe')
    userdata = _Option(option='userdata')
    metadata = _Option(option='metadata')
    scenario_type = _Option(option='type')
    service_type = _Option(option='service_type', default='http')
    introspection = _Option(option='introspection')
    environment = _Option(option='environment', default=None)
    images = _Option(option='images', method='getlist')


class ConfigurationParser(object):
    """A parser class which knows how to parse argus configurations."""

    def __init__(self, filename):
        self._filename = filename
        self._parser = _ConfigParser()
        self._parser.read(self._filename)

    def _parse_environment(self, key):
        values_factory = collections.namedtuple(
            'values_factory',
            'config_file values')
        config_name = self._parser.get(key, 'config')
        preparer = self._parser.get(key, 'preparer')

        # The config is in fact another section.
        config = dict(self._parser.items(config_name))
        # Collect namespaces sections a la default.test.value=3
        values = collections.defaultdict(dict)
        config_file = config.pop('config_file')
        for opt_name, opt_value in config.items():
            section, subkey = opt_name.split(".", 1)
            values[section][subkey] = opt_value
        values = values_factory(config_file, values)

        start_commands = self._load_commands(key, 'start_commands')
        stop_commands = self._load_commands(key, 'stop_commands')
        list_services_commands = self._load_commands(
            key, 'list_services_commands')
        filter_services_regexes = self._load_commands(
            key, 'filter_services_regexes')
        start_service_command = self._load_commands(
            key, 'start_service_command')
        if start_service_command:
            start_service_command = start_service_command[0]
        stop_service_command = self._load_commands(
            key, 'stop_service_command')
        if stop_service_command:
            stop_service_command = stop_service_command[0]

        environment = collections.namedtuple(
            'environment',
            'name config preparer start_commands stop_commands '
            'list_services_commands filter_services_regexes '
            'start_service_command stop_service_command')

        return environment(key, values, preparer, start_commands,
                           stop_commands, list_services_commands,
                           filter_services_regexes, start_service_command,
                           stop_service_command)

    def _load_commands(self, key, command):
        try:
            return self._parser.getlist(key, command)
        except six.moves.configparser.NoOptionError:
            return None

    @property
    def environments(self):
        """Get a list of environments.

        An environment configuration should
        look like this::

           [devstack_config]

           config_file = /etc/nova/nova.conf
           default.configdrive = 34
           nova.test = 24

           [environment_1]

           preparer = fully.qualified:Name
           config = devstack_config
           start_commands = ...
                            ...
                            ...
           stop_commands = ...
                           ...
           list_services_commands = ...
                                     ...
           filter_services_regexes = ...
                                      ...
           start_service_command = ...
           stop_service_command = ...
        """
        environments = []
        for key in self._parser.sections():
            if not key.startswith("environment_"):
                continue
            environ_obj = self._parse_environment(key)
            environments.append(environ_obj)
        return environments

    @property
    def argus(self):
        # Get the argus section
        argus = collections.namedtuple('argus',
                                       'resources debug path_to_private_key '
                                       'file_log log_format dns_nameservers')
        resources = _get_default(
            self._parser, 'argus', 'resources',
            'https://raw.githubusercontent.com/PCManticore/'
            'argus-ci/master/argus/resources')
        debug = self._parser.getboolean('argus', 'debug')
        path_to_private_key = self._parser.get('argus', 'path_to_private_key')
        file_log = _get_default(self._parser, 'argus', 'file_log')
        log_format = _get_default(self._parser, 'argus', 'log_format')
        dns_nameservers = _get_default(
            self._parser, 'argus', 'dns_nameservers',
            ['8.8.8.8', '8.8.4.4'])
        if not isinstance(dns_nameservers, list):
            # pylint: disable=no-member
            dns_nameservers = dns_nameservers.split(",")

        return argus(resources, debug, path_to_private_key,
                     file_log, log_format, dns_nameservers)

    @property
    def cloudbaseinit(self):
        cloudbaseinit = collections.namedtuple(
            'cloudbaseinit',
            'created_user group')

        group = self._parser.get('cloudbaseinit', 'group')
        created_user = self._parser.get('cloudbaseinit', 'created_user')

        return cloudbaseinit(created_user, group)

    @property
    def images(self):
        image = collections.namedtuple(
            'image',
            'name default_ci_username '
            'default_ci_password image_ref flavor_ref os_type')

        # Get the images section
        images = []
        for key in self._parser.sections():
            if not key.startswith("image_"):
                continue
            image_name = key.partition("image_")[2]
            ci_user = _get_default(
                self._parser, key, 'default_ci_username', 'CiAdmin')
            ci_password = _get_default(self._parser, key,
                                       'default_ci_password',
                                       'Passw0rd')
            image_ref = self._parser.get(key, 'image_ref')
            flavor_ref = self._parser.get(key, 'flavor_ref')
            os_type = _get_default(self._parser, key, 'os_type', 'Windows')
            images.append(image(image_name, ci_user, ci_password,
                                image_ref, flavor_ref, os_type))
        return images

    @property
    def scenarios(self):
        # Get the scenarios section
        scenario = collections.namedtuple('scenario',
                                          'name scenario test_classes recipe '
                                          'userdata metadata images type '
                                          'service_type introspection '
                                          'environment')
        images_names = {image.name: image for image in self.images}
        environment_names = {
            environment.name: environment
            for environment in self.environments
        }
        scenarios = []
        for key in self._parser.sections():
            if not key.startswith("scenario_"):
                continue
            section = _ScenarioSection(key, self._parser)
            images = [images_names[image] for image in section.images]
            environment = environment_names.get(section.environment)
            scenarios.append(scenario(section.scenario_name,
                                      section.scenario_class,
                                      section.test_classes,
                                      section.recipe,
                                      section.userdata,
                                      section.metadata,
                                      images,
                                      section.scenario_type,
                                      section.service_type,
                                      section.introspection,
                                      environment))
        return scenarios

    @property
    def conf(self):
        conf = collections.namedtuple(
            'conf', 'argus cloudbaseinit images scenarios')
        return conf(self.argus, self.cloudbaseinit,
                    self.images, self.scenarios)
