@echo off
setlocal
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0Uninstall-SmartSkin.ps1"
set "SMARTSKIN_EXIT=%ERRORLEVEL%"
echo.
pause
exit /b %SMARTSKIN_EXIT%

