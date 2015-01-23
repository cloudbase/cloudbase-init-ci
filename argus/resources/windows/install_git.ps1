param
(
    [Parameter(Mandatory=$true)]
    [string]$gitUrl,
    [Parameter(Mandatory=$true)]
    [string]$gitBasename
)

$GitInstallPath = "$ENV:Temp\$gitBasename"
(new-object System.Net.WebClient).DownloadFile($gitUrl, $GitInstallPath)
cmd.exe /C call $GitInstallPath /silent
setx PATH "$env:PATH;${env:ProgramFiles(x86)}\Git\cmd;"