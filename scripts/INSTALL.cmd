@echo off
setlocal
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0Install-SmartSkin.ps1" -PackageRoot "%~dp0"
set "SMARTSKIN_EXIT=%ERRORLEVEL%"
echo.
pause
exit /b %SMARTSKIN_EXIT%

