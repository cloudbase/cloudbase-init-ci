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

import collections
import os
import tempfile
import textwrap
import unittest

from argus import config


class TestConfig(unittest.TestCase):

    def _create_file(self, content):
        handle, tmp = tempfile.mkstemp()
        os.close(handle)
        self.addCleanup(os.remove, tmp)
        with open(tmp, 'w') as stream:
            stream.write(textwrap.dedent(content))
        return tmp

    # TODO(cpopa): more tests should be added here

    def test_parse_config(self):
        self._test_parse_config("""
        [argus]
        resources = a
        debug = False
        path_to_private_key = b
        file_log = c
        log_format = d
        dns_nameservers = a,b

        [cloudbaseinit]
        expected_plugins_count = 4

        [image_8]
        default_ci_username = Admin
        default_ci_password = Passw0rd
        image_ref = image_ref
        flavor_ref = flavor_ref
        group = 4
        created_user = 5

        [scenario_windows]
        type = smoke
        scenario = 3
        test_classes = 4,5, 6, 7,   8,
                       0,2
        recipe = 5
        userdata = 6
        metadata = 7
        image = 8
        service_type = configdrive
        introspection = something

        """)

    def test_parse_config_inheritance(self):
        self._test_parse_config("""
        [argus]
        resources = a
        debug = False
        path_to_private_key = b
        file_log = c
        log_format = d
        dns_nameservers = a,b

        [cloudbaseinit]
        expected_plugins_count = 4

        [image_8]
        default_ci_username = Admin
        default_ci_password = Passw0rd
        image_ref = image_ref
        flavor_ref = flavor_ref
        group = 4
        created_user = 5

        [base_scenario]

        type = smoke
        scenario = 2
        test_classes = 4,5,6,7,8,0,2
        recipe = 5
        userdata = 6
        metadata = 7
        introspection = something

        [scenario_windows : base_scenario]
        type = smoke
        scenario = 3
        image = 8
        service_type = configdrive
        """)

    def test_parse_config_environment(self):
        environment_factory = collections.namedtuple(
            'expected_environment',
            'name preparer config start_commands stop_commands')
        config_factory = collections.namedtuple('config', 'config_file values')

        environment_config = config_factory('/etc/nova/nova.conf',
                                            {'default': {'configdrive': '34',
                                                         'tempest': '24'},
                                             'nova': {'test': '24'}})
        expected_environment = environment_factory(
            'environment_nova',
            'fully.qualified:Name', environment_config,
            ['test', 'multiple', 'commands'],
            ['test', 'comma', 'commands']
        )

        self._test_parse_config("""
        [devstack_config]

        config_file = /etc/nova/nova.conf
        default.configdrive = 34
        default.tempest = 24
        nova.test = 24

        [environment_nova]

        preparer = fully.qualified:Name
        config = devstack_config
        start_commands = test
                         multiple
                         commands
        stop_commands = test,
                        comma,
                        commands

        [argus]
        resources = a
        debug = False
        path_to_private_key = b
        file_log = c
        log_format = d
        dns_nameservers = a,b

        [cloudbaseinit]
        expected_plugins_count = 4

        [image_8]
        default_ci_username = Admin
        default_ci_password = Passw0rd
        image_ref = image_ref
        flavor_ref = flavor_ref
        group = 4
        created_user = 5

        [base_scenario]

        type = smoke
        scenario = 2
        test_classes = 4,5,6,7,8,0,2
        recipe = 5
        userdata = 6
        metadata = 7
        introspection = something

        [scenario_windows : base_scenario]
        type = smoke
        scenario = 3
        image = 8
        service_type = configdrive
        environment = environment_nova
        """, environment=expected_environment)

    def _test_parse_config(self, config_text, environment=None):
        tmp = self._create_file(textwrap.dedent(config_text))

        parsed = config.ConfigurationParser(tmp).conf
        self.assertTrue({'argus',
                         'images',
                         'cloudbaseinit',
                         'scenarios'}.issubset(set(dir(parsed))))

        self.assertEqual('a', parsed.argus.resources)
        self.assertFalse(parsed.argus.debug)
        self.assertEqual('b', parsed.argus.path_to_private_key)
        self.assertEqual('c', parsed.argus.file_log)
        self.assertEqual('d', parsed.argus.log_format)
        self.assertEqual(['a', 'b'], parsed.argus.dns_nameservers)

        self.assertEqual(4, parsed.cloudbaseinit.expected_plugins_count)

        self.assertIsInstance(parsed.images, list)
        self.assertEqual('Admin', parsed.images[0].default_ci_username)
        self.assertEqual('Passw0rd', parsed.images[0].default_ci_password)
        self.assertEqual('image_ref', parsed.images[0].image_ref)
        self.assertEqual('flavor_ref', parsed.images[0].flavor_ref)
        self.assertEqual('4', parsed.images[0].group)
        self.assertEqual('5', parsed.images[0].created_user)

        self.assertEqual('3', parsed.scenarios[0].scenario)
        self.assertEqual(['4', '5', '6', '7', '8', '0', '2'],
                         parsed.scenarios[0].test_classes)
        self.assertEqual('5', parsed.scenarios[0].recipe)
        self.assertEqual('6', parsed.scenarios[0].userdata)
        self.assertEqual('7', parsed.scenarios[0].metadata)
        self.assertEqual(parsed.images[0], parsed.scenarios[0].image)
        self.assertEqual('configdrive', parsed.scenarios[0].service_type)
        self.assertEqual('something', parsed.scenarios[0].introspection)
        self.assertEqual('smoke', parsed.scenarios[0].type)

        if environment is not None:
            self.assertTrue(parsed.scenarios[0].environment)
            self.assertEqual(environment.name,
                             parsed.scenarios[0].environment.name)
            self.assertEqual(environment.start_commands,
                             parsed.scenarios[0].environment.start_commands)
            self.assertEqual(environment.stop_commands,
                             parsed.scenarios[0].environment.stop_commands)
            self.assertEqual(environment.preparer,
                             parsed.scenarios[0].environment.preparer)
            self.assertEqual(
                environment.config,
                parsed.scenarios[0].environment.config)
        else:
            self.assertFalse(parsed.scenarios[0].environment)
