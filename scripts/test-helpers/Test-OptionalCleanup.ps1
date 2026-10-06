# Focused helper-only regression. Main lifecycle tests never mock entry scripts.
[CmdletBinding()]
param([Parameter(Mandatory = $true)][string]$LifecyclePath, [Parameter(Mandatory = $true)][string]$TestRoot)
Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'
. $LifecyclePath
$Empty = Join-Path $TestRoot 'optional-empty-cleanup'
New-Item -ItemType Directory -Path $Empty -Force | Out-Null
foreach ($Failure in @('enumeration', 'removal')) {
    # A child scope keeps command substitutes out of the real harness and every
    # production process. This is intentionally not counted as a launcher test.
    $Warnings = @(& {
        param($LifecyclePath, $Failure, $Empty)
        . $LifecyclePath
        if ($Failure -eq 'enumeration') {
            function Get-ChildItem { param([string]$LiteralPath, [switch]$Force) throw 'synthetic enumeration access error' }
        } else {
            function Remove-Item { param([string]$LiteralPath, [switch]$Force) throw 'synthetic optional directory-delete error' }
        }
        Remove-EmptyPluginDirectories @($Empty) 3>&1
    } $LifecyclePath $Failure $Empty)
    if ($Warnings.Count -ne 1 -or [string]$Warnings[0] -notmatch 'could not be removed') { throw "Optional $Failure failure was not reported as a warning." }
    if (-not (Test-Path -LiteralPath $Empty -PathType Container)) { throw 'Optional failure unexpectedly deleted its fixture.' }
}
Remove-Item -LiteralPath $Empty -Force
Write-Host 'SMARTSKIN_OPTIONAL_CLEANUP_TEST PASS | helper-only | enumeration+removal-errors=warning'
