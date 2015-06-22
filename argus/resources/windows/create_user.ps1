param
(
   [Parameter(Mandatory=$true)]
   [string]$user,
   [Parameter(Mandatory=$false)]
   [string]$password="PASsw0r4&!="
)
$Computer = [ADSI]"WinNT://$Env:COMPUTERNAME,Computer"

$LocalUser = $Computer.Create("User", $user)
$LocalUser.SetPassword($password)
$LocalUser.SetInfo()
net localgroup Administrators $user /ADD
