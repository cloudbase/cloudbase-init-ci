Import-Module C:\common.psm1

$ErrorActionPreference = "Stop"

try
{
    $programFilesDir = Get-ProgramDir
    $Host.UI.RawUI.WindowTitle = "Running Sysprep..."
    $unattendedXmlPath = "$programFilesDir\Cloudbase Solutions\Cloudbase-Init\conf\Unattend.xml"
    & "$ENV:SystemRoot\System32\Sysprep\Sysprep.exe" `/generalize `/oobe `/reboot `/unattend:"$unattendedXmlPath"

    # the CI will wait for the service to be stopped, in order to consider
    # the instance prepared. But there could be a small delay window, where
    # the system is preparing to reboot and the CI will see that the
    # cloudbaseinit service was stopped (it wasn't in fact started).
    # Since a restart will be called soon, block this until
    # the OS is ready to do the actual restart.
    While (1) { Start-Sleep 5 }
}

catch
{
    $host.ui.WriteErrorLine($_.Exception.ToString())
    $x = $host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
    throw
}
