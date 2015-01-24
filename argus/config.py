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

import six


def parse_config(filename):
    """Parse the given config file.

    It will return a object with three attributes, ``argus``
    for general argus options, ``cloudbaseinit`` for options
    related to cloudbaseinit and ``images``, a list of
    image objects with some attributes exported, such as ``image_ref``
    and so on.
    """
    # pylint: disable=too-many-locals
    argus = collections.namedtuple('argus',
                                   'resources debug path_to_private_key '
                                   'file_log log_format dns_nameservers')
    cloudbaseinit = collections.namedtuple('cloudbaseinit',
                                           'expected_plugins_count')
    image = collections.namedtuple('image',
                                   'service_type default_ci_username '
                                   'default_ci_password image_ref flavor_ref '
                                   'group created_user os_type')
    conf = collections.namedtuple('conf', 'argus cloudbaseinit images')

    parser = six.moves.configparser.ConfigParser()
    parser.read(filename)

    # Get the argus section
    resources = parser.get(
        'argus',
        'resources',
        'https://raw.githubusercontent.com/PCManticore/'
        'argus-ci/master/argus/resources')
    debug = parser.getboolean('argus', 'debug')
    path_to_private_key = parser.get('argus', 'path_to_private_key')
    file_log = parser.get('argus', 'file_log')
    log_format = parser.get('argus', 'log_format')
    dns_nameservers = parser.get('argus', 'dns_nameservers')
    if not dns_nameservers:
        dns_nameservers = ['8.8.8.8', '8.8.4.4']
    else:
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
        if not key.startswith("image"):
            continue
        service_type = parser.get(key, 'service_type', 'http')
        ci_user = parser.get(key, 'default_ci_username', 'CiAdmin')
        ci_password = parser.get(key, 'default_ci_password', 'Passw0rd')
        image_ref = parser.get(key, 'image_ref')
        flavor_ref = parser.get(key, 'flavor_ref')
        group = parser.get(key, 'group')
        created_user = parser.get(key, 'created_user')
        os_type = parser.get(key, 'os_type', 'windows')
        images.append(image(service_type, ci_user, ci_password,
                            image_ref, flavor_ref, group, created_user,
                            os_type))
    return conf(argus, cloudbaseinit, images)
