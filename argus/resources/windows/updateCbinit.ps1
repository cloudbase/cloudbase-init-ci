param(
    [switch]$UpdatePythonWrappers = $True
)

# Import required PowerShell modules
Import-Module Microsoft.PowerShell.Management
Import-Module Microsoft.PowerShell.Utility
Import-Module C:\common.psm1

$programDir = Get-ProgramDir
$cloudbaseInitBaseDir = Join-Path $programDir "Cloudbase Solutions\Cloudbase-Init"
$cloudbaseInitPythonDir = Join-Path $cloudbaseInitBaseDir "Python"
$pythonExePath = Join-Path $cloudbaseInitPythonDir "python.exe"

# Update Python exe wrappers
if ($UpdatePythonWrappers) {
    & $pythonExePath -c "import os; import sys; from pip._vendor.distlib import scripts; specs = 'cloudbase-init = cloudbaseinit.shell:main'; scripts_path = os.path.join(os.path.dirname(sys.executable), 'Scripts'); m = scripts.ScriptMaker(None, scripts_path); m.executable = sys.executable; m.make(specs)"
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Failed to update Python exe wrappers"
        exit 1
    }
}
