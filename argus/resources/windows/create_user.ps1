param
(
   [Parameter(Mandatory=$true)]
   [string]$user,
   [Parameter(Mandatory=$false)]
   [string]$password="PASsw0r4&!="
)

net user $user $password /add
net localgroup Administrators $user /ADD
