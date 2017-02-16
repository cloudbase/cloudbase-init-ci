param
(
    [string]$fileLocation = "C:\diskid"
)

New-item -Path $fileLocation -Type file -Force | foreach {
$command = @"
select disk 0
uniqueid disk
"@
$command | diskpart | Out-file $fileLocation
}
$id = Get-Content -Path $fileLocation | findstr /R /C:"Disk ID"
echo $id > $fileLocation
