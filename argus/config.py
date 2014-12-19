# Copyright 2014 Cloudbase-init
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

from oslo.config import cfg
from tempest import config


TEMPEST_CONF = config.CONF
CONF = cfg.CONF

CBINIT_GROUP = cfg.OptGroup(name='argus',
                            title="Argus Options")
OPTS = [
    cfg.IntOpt('replace_code',
               default=0,
               help="replace cbinit code, or use the one added by the "
                    "installer"),
    cfg.StrOpt('service_type',
               default='http',
               help="service_type should take value 'http', 'ec2', "
                    "or 'configdrive'"),
    cfg.StrOpt('default_ci_username',
               default='CiAdmin',
               help="The default CI user for the instances."),
    cfg.StrOpt('default_ci_password',
               default='Passw0rd',
               help="The default password for the CI user."),
    cfg.StrOpt('created_user',
               default='Admin',
               help='The user created by the CloudbaseInit plugins.'),
    cfg.StrOpt('resources',
               default='https://raw.githubusercontent.com/PCManticore/'
                       'argus-ci/master/argus/resources/',
               help="An URL representing the locations of the resources."),
    cfg.BoolOpt('debug',
                 default=False,
                 help="Switch to a debug behaviour. This includes "
                      "logging of command output directly to stdout "
                      "and failure hooks, using pdb."),
    cfg.IntOpt('expected_plugins_count',
               default=13,
               help="The number of plugins expected to exist after "
                    "cloudbase-init ran."),
    cfg.StrOpt('group',
               default='Administrators',
               help="The group in which the created user "
                    "is expected to be part of."),

]
config.register_opt_group(CONF, CBINIT_GROUP, OPTS)
# Done registering.
