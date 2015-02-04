param
(
   [Parameter(Mandatory=$true)]
   [string]$user
)
$Computer = [ADSI]"WinNT://$Env:COMPUTERNAME,Computer"

$LocalUser = $Computer.Create("User", $user)
$LocalUser.SetPassword("Passw0rd")
$LocalUser.SetInfo()
