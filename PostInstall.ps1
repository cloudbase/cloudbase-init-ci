<#
Copyright 2016 Cloudbase Solutions Srl
Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at
    http://www.apache.org/licenses/LICENSE-2.0
Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
#>

# Import required PowerShell modules
import-module Microsoft.PowerShell.Management
import-module Microsoft.PowerShell.Utility
import-module NetSecurity


Set-NetFirewallRule -DisplayName "File and Printer Sharing (Echo Request - ICMPv4-In)" -enabled True
Set-NetFirewallRule -DisplayName "File and Printer Sharing (Echo Request - ICMPv4-Out)" -enabled True

Set-NetFirewallRule -DisplayName "File and Printer Sharing (Echo Request - ICMPv6-In)" -enabled True
Set-NetFirewallRule -DisplayName "File and Printer Sharing (Echo Request - ICMPv6-Out)" -enabled True

Set-NetFirewallRule -DisplayName "File and Printer Sharing (SMB-In)" -enabled True
Set-NetFirewallRule -DisplayName "File and Printer Sharing (SMB-Out)" -enabled True

net.exe user CiAdmin Passw0rd /add
net.exe localgroup Administrators CiAdmin /add



set-item WSMan:\localhost\Service\Auth\Basic $true
set-item WSMan:\localhost\Service\AllowUnencrypted $true

# Adauga PortableGit in Porgram Files
$AddedFolder = "C:\Program Files\PortableGit\cmd\"
$OldPath = (Get-ItemProperty -Path `
           'Registry::HKEY_LOCAL_MACHINE\System\CurrentControlSet\Control\Session Manager\Environment' `
           -Name PATH).Path
$NewPath= $OldPath + ";" + $AddedFolder
Set-ItemProperty -Path `
    'Registry::HKEY_LOCAL_MACHINE\System\CurrentControlSet\Control\Session Manager\Environment' `
    -Name PATH -Value $NewPath
	
