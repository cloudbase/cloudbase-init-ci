param
(
   [Parameter(Mandatory=$true)]
   [string]$user
)
$Computer = [ADSI]"WinNT://$Env:COMPUTERNAME,Computer"

$LocalUser = $Computer.Create("User", $user)
$LocalUser.SetPassword("PASsw0r4&!=")
$LocalUser.SetInfo()
net localgroup Administrators $user /ADD
