param
(
    [string]$serviceType = 'http'
)

$ErrorActionPreference = "Stop"


function setLocalScripts([string]$programFiels) {
    $path = "$programFilesDir\Cloudbase Solutions\Cloudbase-Init\conf\cloudbase-init.conf"

    # Write the locations of the scripts in the cloudbase-init configuration file.
    $home_drive = ${ENV:HOMEDRIVE}
    $scripts = $home_drive + '\Scripts'
    $value = "`nlocal_scripts_path=$scripts"
    ((Get-Content $path) + $value) | Set-Content $path

    # Create the scripts.
    mkdir $scripts
    echo "echo 1 > %HOMEDRIVE%\Scripts\shell.output" | Set-Content $scripts\shell.cmd
    echo "Test-Path $scripts > $scripts\powershell.output" | Set-Content $scripts\powersh.ps1
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

function activateWindows([string]$programFiles) {
    $value = "activate_windows=True"
    $path = "$programFilesDir\Cloudbase Solutions\Cloudbase-Init\conf\cloudbase-init.conf"
    ((Get-Content $path) + $value) | Set-content $path
}

function Set-CloudbaseInitServiceStartupPolicy {
    #Cloudbase Init service must start only after the sysprep has rebooted the
    #the Windows machine.
    #In order to achieve this, the service is first disabled and reenabled
    #using SetupComplete.cmd script.
    #https://technet.microsoft.com/en-us/library/cc766314%28v=ws.10%29.aspx
    
    mkdir "${ENV:SystemRoot}\Setup\Scripts"
    cmd /c 'sc config cloudbase-init start= demand'
    Set-Content -Value "sc config cloudbase-init start= auto && net start cloudbase-init" `
                -Path "${ENV:SystemRoot}\Setup\Scripts\SetupComplete.cmd"
}


try {

    $Host.UI.RawUI.WindowTitle = "Downloading Cloudbase-Init..."

    $osArch = (Get-WmiObject  Win32_OperatingSystem).OSArchitecture
    $programDirs = @($ENV:ProgramFiles)

    if($osArch -eq "64-bit")
    {
        $CloudbaseInitMsi = "CloudbaseInitSetup_Beta_x64.msi"
        $programDirs += ${ENV:ProgramFiles(x86)}
    }
    else
    {
        $CloudbaseInitMsi = "CloudbaseInitSetup_Beta_x86.msi"
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

    $programFilesDir = 0
    foreach ($programDir in $programDirs) {
        if (Test-Path "$programDir\Cloudbase Solutions") {
            $programFilesDir = $programDir
        }
    }
    if (!$programFilesDir) {
        throw "Cloudbase-init installed files not found in $programDirs"
    }

    setLocalScripts $programFilesDir
    activateWindows $programFilesDir

    if ($serviceType)
    {
        setService $programFilesDir
    }

    Set-CloudbaseInitServiceStartupPolicy
} catch {
    $host.ui.WriteErrorLine($_.Exception.ToString())
    $x = $host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
    throw
}
