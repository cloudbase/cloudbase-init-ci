@echo off

set path=C:\reboot

:first
if exist %path% goto second
echo first
mkdir %path%
exit /b 1003

:second
echo second
mkdir %path%2
