Import-Module C:\common.psm1

$ErrorActionPreference = "Stop"

try
{
    $programFilesDir = Get-ProgramDir
    $Host.UI.RawUI.WindowTitle = "Running Sysprep..."
    $unattendedXmlPath = "$programFilesDir\Cloudbase Solutions\Cloudbase-Init\conf\Unattend.xml"

    if (-Not (Test-Path -LiteralPath $unattendedXmlPath -PathType Leaf)){
    # if there is no Unattend.xml the command will halt and we will never
    # get to the last exit or reboot
        exit 1
    }

    & "$ENV:SystemRoot\System32\Sysprep\Sysprep.exe" `/generalize `/oobe `/reboot `/unattend:"$unattendedXmlPath"

    # the CI will wait for the service to be stopped, in order to consider
    # the instance prepared. But there could be a small delay window, where
    # the system is preparing to reboot and the CI will see that the
    # Cloudbase-Init service was stopped (it wasn't in fact started).
    # Since a restart will be called soon, block this until
    # the OS is ready to do the actual restart.
    # If sysprep doesn't finish within 10 minutes it means that it hang and
    # we need to exit with non zero exit code.
    Start-Sleep 600
    exit 1
}

catch
{
    $host.ui.WriteErrorLine($_.Exception.ToString())
    $x = $host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
    throw
}
