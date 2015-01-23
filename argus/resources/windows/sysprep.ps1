$ErrorActionPreference = "Stop"

try
{

    $osArch = (Get-WmiObject  Win32_OperatingSystem).OSArchitecture
    if($osArch -eq "64-bit")
    {
        $programFilesDir = ${ENV:ProgramFiles(x86)}
    }
    else
    {
        $programFilesDir = $ENV:ProgramFiles
    }
        $Host.UI.RawUI.WindowTitle = "Running Sysprep..."
    $unattendedXmlPath = "$programFilesDir\Cloudbase Solutions\Cloudbase-Init\conf\Unattend.xml"
    & "$ENV:SystemRoot\System32\Sysprep\Sysprep.exe" `/generalize `/oobe `/shutdown `/unattend:"$unattendedXmlPath"
}

catch
{
    $host.ui.WriteErrorLine($_.Exception.ToString())
    $x = $host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
    throw
}
