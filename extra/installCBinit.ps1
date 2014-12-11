param
(
    [bool]$newCode = $False,
    [string]$serviceType = 'http'
)

$ErrorActionPreference = "Stop"

function replaceCloudbaseInitCode([string]$programFiles) {
    $path = "$programFiles\Cloudbase Solutions\Cloudbase-Init\Python27\Lib\site-packages\CLOUDB~1"

    # rm -Force -Recurse $path
    # copy code over either via git command or samba share
}

function setService([string]$programFiles) {
    $path = "$programFilesDir\Cloudbase Solutions\Cloudbase-Init\conf\cloudbase-init.conf"

    if ($serviceType -eq 'http') {
        $value = "metadata_services=cloudbaseinit.metadata.services.httpservice.HttpService"
    } elseif ($serviceType -eq 'configdrive') {
        $value = "metadata_services=cloudbaseinit.metadata.services.configdrive.ConfigDriveService"
    } elseif ($serviceType -eq 'ec2') {
            $value = "metadata_services=cloudbaseinit.metadata.services.ec2service.EC2Service"
    }
    ((Get-Content $path) + $value) | Set-content $path
}

try
{
    $Host.UI.RawUI.WindowTitle = "Downloading Cloudbase-Init..."

    $osArch = (Get-WmiObject  Win32_OperatingSystem).OSArchitecture
    if($osArch -eq "64-bit")
    {
        $CloudbaseInitMsi = "CloudbaseInitSetup_Beta_x64.msi"
        $programFilesDir = ${ENV:ProgramFiles(x86)}
    }
    else
    {
        $CloudbaseInitMsi = "CloudbaseInitSetup_Beta_x86.msi"
        $programFilesDir = $ENV:ProgramFiles
    }

    $CloudbaseInitMsiPath = "$ENV:Temp\$CloudbaseInitMsi"
    $CloudbaseInitMsiUrl = "http://www.cloudbase.it/downloads/$CloudbaseInitMsi"
    $CloudbaseInitMsiLog = "$ENV:Temp\CloudbaseInitSetup_Beta.log"

    (new-object System.Net.WebClient).DownloadFile($CloudbaseInitMsiUrl, $CloudbaseInitMsiPath)

    $Host.UI.RawUI.WindowTitle = "Installing Cloudbase-Init..."

    $serialPortName = @(Get-WmiObject Win32_SerialPort)[0].DeviceId

    $p = Start-Process -Wait -PassThru -Verb runas -FilePath msiexec -ArgumentList "/i $CloudbaseInitMsiPath /qn /l*v $CloudbaseInitMsiLog LOGGINGSERIALPORTNAME=$serialPortName"
    if ($p.ExitCode -ne 0)
    {
        throw "Installing $CloudbaseInitMsiPath failed. Log: $CloudbaseInitMsiLog"
    }

    if ($newCode)
    {
        replaceCloudbaseInitCode $programFilesDir
    }

    if ($serviceType)
    {
        setService $programFilesDir
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
