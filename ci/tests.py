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

import unittest

from argus.backends.heat import heat_backend
from argus.backends.tempest import cloud as tempest_cloud_backend
from argus.backends.tempest import tempest_backend
from argus import config as argus_config
from argus.introspection.cloud import windows as introspection
from argus.recipes.cloud import windows as recipe
from argus.scenarios.cloud import base as scenarios
from argus.scenarios.cloud import windows as windows_scenarios
from argus.tests.cloud import smoke
from argus.tests.cloud.windows import test_smoke
from argus import util


CONFIG = argus_config.CONFIG

class BaseWindowsScenario(scenarios.CloudScenario):

    backend_type = tempest_backend.BaseWindowsTempestBackend
    introspection_type = introspection.InstanceIntrospection
    recipe_type = recipe.CloudbaseinitRecipe


class ScenarioBaseSmoke(BaseWindowsScenario):

    test_classes = (test_smoke.TestSmoke, )


class ScenarioHeatSmoke(BaseWindowsScenario):

    test_classes = (test_smoke.TestSmoke, test_smoke.TestHeatUserdata)
    backend_type = heat_backend.WindowsHeatBackend
    userdata = util.get_resource('windows/test_heat.ps1')


class ScenarioMultipartSmoke(BaseWindowsScenario):

    test_classes = (test_smoke.TestScriptsUserdataSmoke,
                    smoke.TestSetTimezone)
    recipe_type = recipe.CloudbaseinitScriptRecipe
    userdata = util.get_resource('windows/multipart_userdata')


class ScenarioMultipartAdvancedSmoke(BaseWindowsScenario):

    recipe_type = recipe.CloudbaseinitAddUserdata
    test_classes = (smoke.TestSetHostname,
                    smoke.TestSetTimezone,
                    smoke.TestPowershellMultipartX86TxtExists,
                    smoke.TestUserdataFileExists,
                    smoke.TestNoError)
    userdata = util.get_resource('windows/multipart_userdata_part_two')


class ScenarioMultipartGzipAdvancedSmoke(ScenarioMultipartAdvancedSmoke):
    userdata = util.gzip_data(
        util.get_resource('windows/multipart_userdata_part_two'))


class ScenarioMultipartB64Smoke(ScenarioMultipartSmoke):

    userdata = util.get_resource('windows/multipart_userdata_b64')


class ScenarioMultipartB64GzipSmoke(ScenarioMultipartSmoke):
    userdata = util.gzip_data(
        util.get_resource('windows/multipart_userdata_b64'))


class ScenarioLongHostnameSmoke(BaseWindowsScenario):

    test_classes = (smoke.TestLongHostname, )
    recipe_type = recipe.CloudbaseinitLongHostname
    userdata = util.get_resource('windows/netbios_hostname')


class ScenarioIndependentPlugins(BaseWindowsScenario):

    test_classes = (test_smoke.TestTrimPlugin,
                    test_smoke.TestSANPolicyPlugin,
                    test_smoke.TestPageFilePlugin,
                    test_smoke.TestDisplayTimeoutPlugin,
                    test_smoke.TestKMSHost,
                    test_smoke.TestNTPClientPlugin,
                    test_smoke.TestBCDPlugin,
                    test_smoke.TestRDPPlugin)
    recipe_type = recipe.CloudbaseinitIndependentPlugins
    service_type = util.HTTP_SERVICE


class ScenarioRenameBuiltinAdministrator(BaseWindowsScenario):
    test_classes = (test_smoke.TestRenameUserAdminPlugin, )
    recipe_type = recipe.CloudbaseinitRenameAdminUserPlugin


class ScenarioUserAlreadyCreated(BaseWindowsScenario):

    test_classes = (test_smoke.TestSmoke, )
    recipe_type = recipe.CloudbaseinitCreateUserRecipe


class ScenarioGenericSmoke(BaseWindowsScenario):

    test_classes = (test_smoke.TestEC2Userdata, test_smoke.TestSmoke)
    userdata = util.get_resource('windows/ec2script')
    metadata = {"admin_pass": "PASsw0r4&!="}


class ScenarioRescueSmoke(BaseWindowsScenario):

    backend_type = tempest_cloud_backend.RescueWindowsBackend
    test_classes = (smoke.TestPasswordPostedRescueSmoke,
                    smoke.TestNoError)
    metadata = {"admin_pass": "PASsw0r4&!="}


class ScenarioCloudstackUpdatePasswordSmoke(
        BaseWindowsScenario,
        windows_scenarios.CloudstackWindowsScenario):

    test_classes = (smoke.TestCloudstackUpdatePasswordSmoke,
                    smoke.TestNoError)
    recipe_type = recipe.CloudbaseinitCloudstackRecipe
    service_type = util.CLOUD_STACK_SERVICE
    metadata = {"admin_pass": "PASsw0r4&!="}


class ScenarioCloudstackMetadata(
        BaseWindowsScenario,
        windows_scenarios.CloudstackWindowsScenario):

    test_classes = (test_smoke.TestSmoke, )
    recipe_type = recipe.CloudbaseinitCloudstackRecipe
    service_type = util.CLOUD_STACK_SERVICE


class ScenarioEC2Metadata(BaseWindowsScenario,
                          windows_scenarios.EC2WindowsScenario):
    test_classes = (test_smoke.TestSmoke, )
    recipe_type = recipe.CloudbaseinitEC2Recipe
    service_type = util.EC2_SERVICE


class ScenarioMaasMetadata(BaseWindowsScenario,
                           windows_scenarios.MaasWindowsScenario):

    test_classes = (test_smoke.TestSmoke, )
    recipe_type = recipe.CloudbaseinitMaasRecipe
    service_type = util.MAAS_SERVICE


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
    service_type = util.HTTP_SERVICE


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


class ScenarioConfigdriveVfatDriveSmoke(BaseWindowsScenario):
    test_classes = (test_smoke.TestSmoke, )
    service_type = util.CONFIG_DRIVE_SERVICE
    availability_zone = 'configdrive_vfat_drive'


class ScenarioConfigdriveVfatCdromSmoke(BaseWindowsScenario):
    test_classes = (test_smoke.TestSmoke, )
    service_type = util.CONFIG_DRIVE_SERVICE
    availability_zone = 'configdrive_vfat_cdrom'


class ScenarioConfigdriveIso9660DriveSmoke(BaseWindowsScenario):
    test_classes = (test_smoke.TestSmoke, )
    service_type = util.CONFIG_DRIVE_SERVICE
    availability_zone = 'configdrive_iso9660_drive'


class ScenarioConfigdriveIso9660CdromSmoke(BaseWindowsScenario):
    test_classes = (test_smoke.TestSmoke, )
    service_type = util.CONFIG_DRIVE_SERVICE
    availability_zone = 'configdrive_iso9660_cdrom'


class ScenarioNetworkConfig(BaseWindowsScenario):
    # NOTE: For the KVM node, in nova.conf the `use_ipv6`,
    # `flat_injected` and `force_config_drive` parameters
    # need to be set to True
    backend_type = tempest_cloud_backend.NetworkWindowsBackend
    test_classes = (smoke.TestStaticNetwork, )
    service_type = util.CONFIG_DRIVE_SERVICE


@unittest.skipIf(CONFIG.openstack.require_sysprep,
                 'Needs sysprep')
class ScenarioImageSmoke(ScenarioBaseSmoke):

    test_classes = (test_smoke.TestSmoke, smoke.TestSwapEnabled)
    recipe_type = recipe.CloudbaseinitImageRecipe
    userdata = util.get_resource("windows/winrm.ps1")


class ScenarioPasswordLength(BaseWindowsScenario):

    test_classes = (test_smoke.TestPasswordLength,)
    recipe_type = recipe.CloudbaseinitPasswordRecipe
