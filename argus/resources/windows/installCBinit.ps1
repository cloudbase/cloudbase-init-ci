param
(
    [string]$installer = 'CloudbaseInitSetup_Beta_x64.msi'
)

Import-Module C:\common.psm1
$ErrorActionPreference = "Stop"


function Set-CloudbaseInitServiceStartupPolicy {
    # Cloudbase-Init service must start only after the sysprep has rebooted the
    # the Windows machine.
    # In order to achieve this, the service is first disabled and reenabled
    # using SetupComplete.cmd script.
    # https://technet.microsoft.com/en-us/library/cc766314%28v=ws.10%29.aspx
    
    mkdir "${ENV:SystemRoot}\Setup\Scripts" -ErrorAction SilentlyContinue
    cmd /c 'sc config cloudbase-init start= demand'
    Set-Content -Value "sc config cloudbase-init start= auto && net start cloudbase-init" `
                -Path "${ENV:SystemRoot}\Setup\Scripts\SetupComplete.cmd"
}


try {

    $Host.UI.RawUI.WindowTitle = "Downloading Cloudbase-Init..."
    $CloudbaseInitMsiPath = "$ENV:Temp\$installer"
    $CloudbaseInitMsiUrl = "http://www.cloudbase.it/downloads/$installer"
    $CloudbaseInitMsiLog = "C:\\installation.log"
    $programDir = Get-ProgramDir "Git"
    $gitPath = Join-Path $programDir "Git"
    $curlPath = (Get-ChildItem -Path $gitPath -Filter "curl.exe" -Recurse | Select-Object -First 1).Fullname
    & $curlPath -L $CloudbaseInitMsiUrl --output $CloudbaseInitMsiPath

    if ($LastExitCode -ne 0) {
        throw "Download failed with exit code $LastExitCode"
    }

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

    Set-CloudbaseInitServiceStartupPolicy
} catch {
    $host.ui.WriteErrorLine($_.Exception.ToString())
    throw
}