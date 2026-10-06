@echo off
setlocal DisableDelayedExpansion
set "SMARTSKIN_POWERSHELL=%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe"
if exist "%SystemRoot%\Sysnative\WindowsPowerShell\v1.0\powershell.exe" set "SMARTSKIN_POWERSHELL=%SystemRoot%\Sysnative\WindowsPowerShell\v1.0\powershell.exe"
"%SMARTSKIN_POWERSHELL%" -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0Install-SmartSkin.ps1" -PackageRoot "%~dp0." %*
set "SMARTSKIN_EXIT=%ERRORLEVEL%"
echo.
if not "%SMARTSKIN_INSTALL_NO_PAUSE%"=="1" pause
exit /b %SMARTSKIN_EXIT%
