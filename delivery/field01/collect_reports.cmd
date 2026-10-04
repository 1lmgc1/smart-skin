@echo off
setlocal
"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0collect_reports.ps1"
set "result=%errorlevel%"
echo.
pause
exit /b %result%
