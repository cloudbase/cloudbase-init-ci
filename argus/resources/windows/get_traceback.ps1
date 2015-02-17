# Look for any tracebacks in the code
$osArch = (Get-WmiObject  Win32_OperatingSystem).OSArchitecture
if($osArch -eq "64-bit")
{

   $programFilesDir = ${ENV:ProgramFiles(x86)}
}
else
{
   $programFilesDir = $ENV:ProgramFiles
}

Select-string -Path $programFilesDir'\Cloudbase Solutions\Cloudbase-Init\log\cloudbase-init.log' -Pattern 'Traceback\s+\(most\s+recent\s+call\s+last\)' -AllMatches -Context 10
Select-string -Path $programFilesDir'\Cloudbase Solutions\Cloudbase-Init\log\cloudbase-init-unattend.log' -Pattern 'Traceback\s+\(most\s+recent\s+call\s+last\)' -AllMatches -Context 10
