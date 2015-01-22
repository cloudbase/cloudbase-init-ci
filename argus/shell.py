# Copyright 2014 Cloudbase Solutions Srl
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

from argus import runner
from argus import util
from argus import scenario
from argus.recipees.cloud import windows
from argus.tests.cloud import test_smoke_windows

def main():
    metadata = {'network_config': str({'content_path':'random_value_test_random'})}
    userdata = util.get_resource('multipart_metadata')

    scenarios = [
        scenario.BaseWindowsScenario(
            test_class=test_smoke_windows.TestWindowsSmoke,
            recipee=windows.WindowsCloudbaseinitRecipee,
            userdata=userdata,
            metadata=metadata),
    ]
    runner.Runner(scenarios).run()

if __name__ == "__main__":
    main()
