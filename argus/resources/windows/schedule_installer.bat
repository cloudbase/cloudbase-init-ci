schtasks /CREATE /TN "cloudbaseinit-installer" /SC ONCE /SD 01/01/2020 /ST 00:00:00 /RL HIGHEST /RU CiAdmin /RP Passw0rd /TR "powershell C:\\installcbinit.ps1  -serviceType %1 -installer %2" /F

schtasks /RUN /TN "cloudbaseinit-installer"

timeout /t 5

:loop
for /f "tokens=2 delims=: " %%f in ('schtasks /query /tn EnablePS-Remoting /fo list ^| find "Status:"' ) do (
    if "%%f"=="Running" (
        timeout /T 1 /NOBREAK > nul
        goto loop
    )
)