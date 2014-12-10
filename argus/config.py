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
    cfg.BoolOpt('replace_code',
                default=0,
                help="replace cbinit code, or use the one added by the "
                     "installer"),
    cfg.StrOpt('service_type',
               default='http',
               help="service_type should take value 'http', 'ec2', "
                    "or 'configdrive'"),
    cfg.StrOpt('userdata_path',
               default='',
               help="path to userdata to be used"),
    cfg.StrOpt('default_ci_username',
               default='CiAdmin',
               help="The default CI user for the instances."),
    cfg.StrOpt('default_ci_password',
               default='Passw0rd',
               help="The default password for the CI user."),
    cfg.StrOpt('created_user',
               default='Admin',
               help='The user created by the CloudbaseInit plugins.'),
    cfg.StrOpt('install_script_url',
               default='https://raw.githubusercontent.com/trobert2/'
                       'windows-openstack-imaging-tools/master/'
                       'installCBinit.ps1',
               help="An URL representing the script which will install "
                    "CloudbaseInit."),
    cfg.BoolOpt('debug',
                 default=False,
                 help="Switch to a debug behaviour. This includes "
                      "logging of command output directly to stdout "
                      "and failure hooks, using pdb."),
    cfg.IntOpt('expected_plugins_count',
               default=10,
               help="The number of plugins expected to exist after "
                    "cloudbase-init ran."),

]
config.register_opt_group(CONF, CBINIT_GROUP, OPTS)
# Done registering.
