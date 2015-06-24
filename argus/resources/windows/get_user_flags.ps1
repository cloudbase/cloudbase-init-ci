param
(
    [Parameter(Mandatory=$true)]
    [string]$username
)
$Computer = [ADSI]"WinNT://$Env:COMPUTERNAME,Computer"
$users = $Computer.Children | where {$_.SchemaClassName -eq 'user'}
$user = $users | where {$_.Name -eq $username}
$flags = $user.UserFlags
$password_expired = $user.PasswordExpired
echo $flags, $password_expired