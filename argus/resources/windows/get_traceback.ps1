Import-Module C:\common.psm1
$programFilesDir = Get-ProgramDir

Select-string -Path $programFilesDir'\Cloudbase Solutions\Cloudbase-Init\log\cloudbase-init.log' `
              -Pattern 'Traceback\s+\(most\s+recent\s+call\s+last\)' `
              -AllMatches -Context 10
Select-string -Path $programFilesDir'\Cloudbase Solutions\Cloudbase-Init\log\cloudbase-init-unattend.log' `
              -Pattern 'Traceback\s+\(most\s+recent\s+call\s+last\)' `
              -AllMatches `
              -Context 10
