@echo off
setlocal
set "SMARTSKIN_PACKAGE_ROOT=%~dp0."
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0Install-SmartSkin.ps1" -PackageRoot "%SMARTSKIN_PACKAGE_ROOT%"
set "SMARTSKIN_EXIT=%ERRORLEVEL%"
echo.
if not "%SMARTSKIN_INSTALL_NO_PAUSE%"=="1" pause
exit /b %SMARTSKIN_EXIT%
