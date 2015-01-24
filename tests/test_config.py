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

import os
import unittest
import tempfile
import textwrap

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
        tmp = self._create_file("""
        [argus]
        resources = a
        debug = False
        path_to_private_key = b
        file_log = c
        log_format = d
        dns_nameservers = a,b

        [cloudbaseinit]
        expected_plugins_count = 4

        [image_0]
        default_ci_username = Admin
        default_ci_password = Passw0rd
        service_type = configdrive
        image_ref = image_ref
        flavor_ref = flavor_ref
        group = 4
        created_user = 5

        [scenario_windows]
        scenario = 3
        test_class = 4
        recipee = 5
        userdata = 6
        metadata = 7
        image = 8
        """)

        parsed = config.parse_config(tmp)
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
        self.assertEqual('configdrive', parsed.images[0].service_type)
        self.assertEqual('image_ref', parsed.images[0].image_ref)
        self.assertEqual('flavor_ref', parsed.images[0].flavor_ref)
        self.assertEqual('4', parsed.images[0].group)
        self.assertEqual('5', parsed.images[0].created_user)

        self.assertEqual('3', parsed.scenarios[0].scenario)
        self.assertEqual('4', parsed.scenarios[0].test_class)
        self.assertEqual('5', parsed.scenarios[0].recipee)
        self.assertEqual('6', parsed.scenarios[0].userdata)
        self.assertEqual('7', parsed.scenarios[0].metadata)
        self.assertEqual('8', parsed.scenarios[0].image)
