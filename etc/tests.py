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

from argus.backends.tempest import cloud as tempest_cloud_backend
from argus.backends.tempest import tempest_backend
from argus.introspection.cloud import windows as introspection
from argus.recipes.cloud import windows as recipe
from argus.scenarios import base
from argus.scenarios import windows as windows_scenarios
from argus.tests.cloud import smoke
from argus.tests.cloud.windows import test_smoke
from argus import util


class BaseWindowsScenario(base.BaseScenario):

    backend_type = tempest_backend.BaseWindowsTempestBackend
    introspection_type = introspection.InstanceIntrospection
    recipe_type = recipe.CloudbaseinitRecipe
    service_type = 'http'
    userdata = None
    metadata = {}


class ScenarioSmoke(BaseWindowsScenario):

    test_classes = (test_smoke.TestSmoke, )


class ScenarioMultipartSmoke(BaseWindowsScenario):

    test_classes = (test_smoke.TestScriptsUserdataSmoke,
                    smoke.TestSetTimezone)
    recipe_type = recipe.CloudbaseinitScriptRecipe
    userdata = util.get_resource('windows/multipart_userdata')


class ScenarioUserAlreadyCreated(BaseWindowsScenario):

    test_classes = (test_smoke.TestSmoke, )
    recipe_type = recipe.CloudbaseinitCreateUserRecipe


class ScenarioGenericSmoke(BaseWindowsScenario):

    test_classes = (test_smoke.TestEC2Userdata, test_smoke.TestSmoke)
    userdata = util.get_resource('windows/ec2script')
    metadata = {"admin_pass": "PASsw0r4&!="}


class ScenarioSmokeRescue(BaseWindowsScenario):

    backend_type = tempest_cloud_backend.RescueWindowsBackend
    test_classes = (smoke.TestPasswordPostedRescueSmoke,
                    smoke.TestNoError)
    metadata = {"admin_pass": "PASsw0r4&!="}


class ScenarioCloudstackSmokeUpdatePassword(
        BaseWindowsScenario,
        windows_scenarios.CloudstackWindowsScenario):

    test_classes = (smoke.TestCloudstackUpdatePasswordSmoke,
                    smoke.TestNoError)
    recipe_type = recipe.CloudbaseinitCloudstackRecipe
    service_type = 'cloudstack'
    metadata = {"admin_pass": "PASsw0r4&!="}


class ScenarioCloudstackMetadata(
        BaseWindowsScenario,
        windows_scenarios.CloudstackWindowsScenario):

    test_classes = (test_smoke.TestSmoke, )
    recipe_type = recipe.CloudbaseinitCloudstackRecipe
    service_type = 'cloudstack'


class ScenarioEC2Metadata(BaseWindowsScenario,
                          windows_scenarios.EC2WindowsScenario):
    test_classes = (test_smoke.TestSmoke, )
    recipe_type = recipe.CloudbaseinitEC2Recipe
    service_type = 'ec2'


class ScenarioMaasMetadata(BaseWindowsScenario,
                           windows_scenarios.MaasWindowsScenario):

    test_classes = (test_smoke.TestSmoke, )
    recipe_type = recipe.CloudbaseinitMaasRecipe
    service_type = 'maas'


class ScenarioWinRMPlugin(BaseWindowsScenario):
    # Test for for checking that a fix for
    # https://bugs.launchpad.net/cloudbase-init/+bug/1433174 works.

    test_classes = (smoke.TestPasswordMetadataSmoke,
                    smoke.TestNoError,
                    test_smoke.TestCertificateWinRM)
    recipe_type = recipe.CloudbaseinitWinrmRecipe
    metadata = {"admin_pass": "PASsw0r4&!="}
    userdata = util.get_certificate()


class ScenarioX509PublicKeys(BaseWindowsScenario,
                             windows_scenarios.HTTPKeysWindowsScenario):

    test_classes = (smoke.TestNoError,
                    smoke.TestPublicKeys,
                    test_smoke.TestCertificateWinRM)
    recipe_type = recipe.CloudbaseinitKeysRecipe
    metadata = {"admin_pass": "PASsw0r4&!="}
    service_type = 'http'


class ScenarioNextLogonAlwaysChange(BaseWindowsScenario):

    recipe_type = recipe.AlwaysChangeLogonPasswordRecipe
    test_classes = (test_smoke.TestNextLogonPassword,
                    smoke.TestNoError)


class ScenarioNextLogonOnMetadataOnly(BaseWindowsScenario):

    recipe_type = recipe.ClearPasswordLogonRecipe
    test_classes = (test_smoke.TestNextLogonPassword,
                    smoke.TestNoError)
    metadata = {"admin_pass": "PASsw0r4&!="}


class ScenarioLocalScripts(BaseWindowsScenario):

    test_classes = (test_smoke.TestSmoke,
                    test_smoke.TestLocalScripts)
    recipe_type = recipe.CloudbaseinitLocalScriptsRecipe

# TODO(cpopa): Can't convert these yet.
# VFAT ConfigDrive tests, with drive and cdrom
# [scenario_smoke_configdrive_vfat_drive_windows : base_smoke_windows]

# test_classes = argus.tests.cloud.windows.test_smoke:TestSmoke
# service_type = configdrive
# environment = environment_devstack_configdrive_vfat_drive
#
#
# [scenario_smoke_configdrive_vfat_cdrom_windows : base_smoke_windows]
#
# test_classes = argus.tests.cloud.windows.test_smoke:TestSmoke
# service_type = configdrive
# environment = environment_devstack_configdrive_vfat_cdrom
#
#
# ISO9660 ConfigDrive tests, with drive and cdrom
#
# [scenario_smoke_configdrive_iso9660_drive_windows : base_smoke_windows]
#
# test_classes = argus.tests.cloud.windows.test_smoke:TestSmoke
# service_type = configdrive
# environment = environment_devstack_configdrive_iso9660_drive
#
#
# [scenario_smoke_configdrive_iso9660_cdrom_windows : base_smoke_windows]
#
# test_classes = argus.tests.cloud.windows.test_smoke:TestSmoke
# service_type = configdrive
# environment = environment_devstack_configdrive_iso9660_cdrom

# class ScenarioNetworkConfig(BaseWindowsScenario):

# backend_type = tempest_cloud_backend.NetworkWindowsScenario
# test_classes = argus.tests.cloud.smoke:TestStaticNetwork
# environment = environment_devstack_static_network
