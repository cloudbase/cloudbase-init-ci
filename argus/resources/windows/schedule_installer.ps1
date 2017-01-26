param
(
    [string]$MsiWebLocation = 'http://www.cloudbase.it/downloads',
    [string]$installer = 'CloudbaseInitSetup_Beta_x64.msi'
)

try {

    $Host.UI.RawUI.WindowTitle = "Starting task scheduler for Cloudbase-Init..."
    $ExistingTasks = "C:\\existing_tasks.log"
    $TaskName = "cloudbaseinit-installer"
    schtasks /query > $ExistingTasks
    $Task = Get-Content -Path $ExistingTasks | Select-String $TaskName -quiet -casesensitive
    if ($Task)
    {
        schtasks /DELETE /TN $TaskName /F
    }

    schtasks /CREATE /TN $TaskName /SC ONCE /SD 01/01/2020 /ST 00:00:00 /RL HIGHEST /RU CiAdmin /RP Passw0rd /TR "powershell C:\\installCBinit.ps1 -MsiWebLocation $MsiWebLocation -installer $installer" /F
    schtasks /RUN /TN $TaskName
    # Wait for task to finish installing
    while ((schtasks /query /tn $TaskName) -match "running") {}
} catch {
    $host.ui.WriteErrorLine($_.Exception.ToString())
    throw
}
