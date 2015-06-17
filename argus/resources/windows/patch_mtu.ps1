# Look for any tracebacks in the code

Import-Module C:\common.psm1
$programFilesDir = Get-ProgramDir

$cloudbaseinit = "$programFilesDir\Cloudbase Solutions\Cloudbase-Init"
$python_name = Get-Childitem $cloudbaseinit -Filter Python* -Name
$cloudstack = "$cloudbaseinit\$python_name\Lib\site-packages\cloudbaseinit\plugins\common\mtu.py"
$src = "osutils = osutils_factory.get_os_utils()"
$dest = "1/0"

(Get-Content $cloudstack).replace($src, $dest) | Set-Content $cloudstack
