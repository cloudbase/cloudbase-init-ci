param
(
    [string]$serviceType = 'http',
    [string]$installer = 'CloudbaseInitSetup_Beta_x64.msi'
)

Import-Module C:\common.psm1
$ErrorActionPreference = "Stop"


function Set-LocalScripts([string]$ProgramFilesDir) {
    $path = "$ProgramFilesDir\Cloudbase Solutions\Cloudbase-Init\conf\cloudbase-init.conf"

    # Write the locations of the scripts in the cloudbase-init configuration file.
    $home_drive = ${ENV:HOMEDRIVE}
    $scripts = $home_drive + '\Scripts'
    $value = "`nlocal_scripts_path=$scripts"
    ((Get-Content $path) + $value) | Set-Content $path
}


function Set-Service([string]$ProgramFilesDir) {
    $path = "$ProgramFilesDir\Cloudbase Solutions\Cloudbase-Init\conf\cloudbase-init.conf"

    if ($serviceType -eq 'http') {
        $value = "metadata_services=cloudbaseinit.metadata.services.httpservice.HttpService"
    } elseif ($serviceType -eq 'configdrive') {
        $value = "metadata_services=cloudbaseinit.metadata.services.configdrive.ConfigDriveService"
    } elseif ($serviceType -eq 'ec2') {
        $value = "metadata_services=cloudbaseinit.metadata.services.ec2service.EC2Service"
    } elseif ($serviceType -eq 'opennebula') {
        $value = "metadata_services=cloudbaseinit.metadata.services.opennebulaservice.OpenNebulaService"
    } elseif ($serviceType -eq 'cloudstack') {
        $value = "metadata_services=cloudbaseinit.metadata.services.cloudstack.CloudStack"
    } elseif ($serviceType -eq 'maas') {
        $value = "metadata_services=cloudbaseinit.metadata.services.maasservice.MaaSHttpService"
    }
    ((Get-Content $path) + $value) | Set-content $path
}

function Set-WindowsActivation([string]$ProgramFilesDir) {
    $value = "activate_windows=True"
    $path = "$ProgramFilesDir\Cloudbase Solutions\Cloudbase-Init\conf\cloudbase-init.conf"
    ((Get-Content $path) + $value) | Set-content $path
}

function Set-CloudbaseInitServiceStartupPolicy {
    #Cloudbase Init service must start only after the sysprep has rebooted the
    #the Windows machine.
    #In order to achieve this, the service is first disabled and reenabled
    #using SetupComplete.cmd script.
    #https://technet.microsoft.com/en-us/library/cc766314%28v=ws.10%29.aspx
    
    mkdir "${ENV:SystemRoot}\Setup\Scripts" -ErrorAction ignore
    cmd /c 'sc config cloudbase-init start= demand'
    Set-Content -Value "sc config cloudbase-init start= auto && net start cloudbase-init" `
                -Path "${ENV:SystemRoot}\Setup\Scripts\SetupComplete.cmd"
}


try {

    $Host.UI.RawUI.WindowTitle = "Downloading Cloudbase-Init..."

    $CloudbaseInitMsiPath = "$ENV:Temp\$installer"
    $CloudbaseInitMsiUrl = "http://www.cloudbase.it/downloads/$installer"
    $CloudbaseInitMsiLog = "C:\\installation.log"

    (new-object System.Net.WebClient).DownloadFile($CloudbaseInitMsiUrl, $CloudbaseInitMsiPath)

    $Host.UI.RawUI.WindowTitle = "Installing Cloudbase-Init..."

    $serialPortName = @(Get-WmiObject Win32_SerialPort)[0].DeviceId

    $p = Start-Process -Wait `
                       -PassThru `
                       -Verb runas `
                       -FilePath msiexec `
                       -ArgumentList "/i $CloudbaseInitMsiPath /qn /l*v $CloudbaseInitMsiLog LOGGINGSERIALPORTNAME=$serialPortName"
    if ($p.ExitCode -ne 0)
    {
        throw "Installing $CloudbaseInitMsiPath failed. Log: $CloudbaseInitMsiLog"
    }

    $programFilesDir = Get-ProgramDir
    Set-LocalScripts $ProgramFilesDir
    Set-WindowsActivation $ProgramFilesDir

    if ($serviceType)
    {
        Set-Service $ProgramFilesDir
    }

    Set-CloudbaseInitServiceStartupPolicy
} catch {
    $host.ui.WriteErrorLine($_.Exception.ToString())
    throw
}
