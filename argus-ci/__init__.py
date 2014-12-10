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

import sys

if 'argus' not in sys.modules:
    # TODO(cpopa): use this hack until argus can be a real package.
    # Since we don't know how the test discovery will load us,
    # we inject the current module as 'argus' into sys.modules, so we can
    # import our files as if we were an installed package.
    sys.modules['argus'] = sys.modules[__name__]
