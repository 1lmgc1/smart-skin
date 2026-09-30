[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$PackageRoot,
    [string]$LogPath = ""
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = "Stop"

$PluginGuid = "b3f42f21-1f15-45e6-9bc2-a68b0b27c877"
$TestId = [Guid]::NewGuid().ToString("N")
$TestRoot = Join-Path $env:RUNNER_TEMP ("SmartSkinInstallerTest-" + $TestId)
$InstallRoot = Join-Path $TestRoot "install"
$OldDirectory = Join-Path $TestRoot "old-artifact\net48"
$RegistrySuiteRoot = "HKCU:\Software\SmartSkinInstallerTests"
$RegistryTestRoot = Join-Path $RegistrySuiteRoot $TestId
$RegistryBase = Join-Path $RegistryTestRoot "Plug-ins"
$TranscriptStarted = $false

try {
    if (-not [string]::IsNullOrWhiteSpace($LogPath)) {
        $LogDirectory = Split-Path -Parent $LogPath
        if (-not [string]::IsNullOrWhiteSpace($LogDirectory)) {
            New-Item -ItemType Directory -Path $LogDirectory -Force | Out-Null
        }
        Start-Transcript -LiteralPath $LogPath -Force | Out-Null
        $TranscriptStarted = $true
    }

    Write-Host "SMARTSKIN_INSTALLER_TEST PHASE | setup-fixture"
    New-Item -ItemType Directory -Path $OldDirectory -Force | Out-Null
    Copy-Item -LiteralPath (Join-Path $PackageRoot "net48\SmartSkin.Rhino8.rhp") -Destination $OldDirectory
    Copy-Item -LiteralPath (Join-Path $PackageRoot "net48\SmartSkin.Core.dll") -Destination $OldDirectory
    Set-Content -LiteralPath (Join-Path $OldDirectory "keep-user-file.txt") -Value "must survive" -Encoding ASCII

    New-Item -Path $RegistrySuiteRoot -Force | Out-Null
    New-Item -Path $RegistryTestRoot -Force | Out-Null
    New-Item -Path $RegistryBase -Force | Out-Null
    $OldRegistryKey = Join-Path $RegistryBase ("{" + $PluginGuid.ToUpperInvariant() + "}")
    New-Item -Path $OldRegistryKey -Force | Out-Null
    New-ItemProperty -Path $OldRegistryKey -Name "Name" -PropertyType String -Value "Smart Skin" -Force | Out-Null
    New-ItemProperty -Path $OldRegistryKey -Name "FileName" -PropertyType String -Value (Join-Path $OldDirectory "SmartSkin.Rhino8.rhp") -Force | Out-Null

    Write-Host "SMARTSKIN_INSTALLER_TEST PHASE | migrate-manual-install"
    & (Join-Path $PackageRoot "Install-SmartSkin.ps1") `
        -PackageRoot $PackageRoot `
        -InstallRoot $InstallRoot `
        -RegistryBase $RegistryBase `
        -SkipRhinoInstalledCheck `
        -AllowTestInstallRoot

    $InstalledRhp = Join-Path $InstallRoot "current\SmartSkin.Rhino8.rhp"
    if (-not (Test-Path -LiteralPath $InstalledRhp -PathType Leaf)) {
        throw "Managed RHP was not installed."
    }
    if (Test-Path -LiteralPath (Join-Path $OldDirectory "SmartSkin.Rhino8.rhp")) {
        throw "Old registered RHP was not removed."
    }
    if (Test-Path -LiteralPath (Join-Path $OldDirectory "SmartSkin.Core.dll")) {
        throw "Old registered Core DLL was not removed."
    }
    if (-not (Test-Path -LiteralPath (Join-Path $OldDirectory "keep-user-file.txt"))) {
        throw "Installer removed an unrelated old-folder file."
    }

    $CanonicalRegistryKey = Join-Path $RegistryBase $PluginGuid
    $RegisteredPath = (Get-ItemProperty -LiteralPath $CanonicalRegistryKey -Name "FileName").FileName
    if (-not [string]::Equals(
        [System.IO.Path]::GetFullPath([string]$RegisteredPath),
        [System.IO.Path]::GetFullPath($InstalledRhp),
        [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Registry does not point to the managed RHP."
    }
    if (Test-Path -LiteralPath $OldRegistryKey) {
        throw "Installer left the old braced registry key behind."
    }

    Write-Host "SMARTSKIN_INSTALLER_TEST PHASE | repeat-update"
    & (Join-Path $PackageRoot "Install-SmartSkin.ps1") `
        -PackageRoot $PackageRoot `
        -InstallRoot $InstallRoot `
        -RegistryBase $RegistryBase `
        -SkipRhinoInstalledCheck `
        -AllowTestInstallRoot

    $LeftoverManagedVersions = @(
        Get-ChildItem -LiteralPath $InstallRoot -Force |
            Where-Object { $_.Name -like ".previous-*" -or $_.Name -like ".staging-*" }
    )
    if ($LeftoverManagedVersions.Count -ne 0) {
        throw "Installer left an old managed version behind."
    }

    Write-Host "SMARTSKIN_INSTALLER_TEST PHASE | uninstall"
    & (Join-Path $PackageRoot "Uninstall-SmartSkin.ps1") `
        -InstallRoot $InstallRoot `
        -RegistryBase $RegistryBase `
        -AllowTestInstallRoot

    if (Test-Path -LiteralPath $CanonicalRegistryKey) {
        throw "Uninstaller left the registry key behind."
    }
    if (Test-Path -LiteralPath $InstallRoot) {
        throw "Uninstaller left the managed install root behind."
    }
    if (-not (Test-Path -LiteralPath (Join-Path $OldDirectory "keep-user-file.txt"))) {
        throw "Uninstaller removed an unrelated old-folder file."
    }

    Write-Host "SMARTSKIN_INSTALLER_TEST PASS"
}
catch {
    $Invocation = $_.InvocationInfo
    $FailureLocation = "unknown"
    if ($null -ne $Invocation) {
        $FailureLocation = "$($Invocation.ScriptName):$($Invocation.ScriptLineNumber)"
    }
    Write-Host "SMARTSKIN_INSTALLER_TEST FAIL | location=$FailureLocation | error=$($_.Exception.Message)"
    throw
}
finally {
    if (Test-Path -LiteralPath $RegistryTestRoot) {
        Remove-Item -LiteralPath $RegistryTestRoot -Recurse -Force -ErrorAction SilentlyContinue
    }
    if ((Test-Path -LiteralPath $RegistrySuiteRoot) -and
        @(Get-ChildItem -LiteralPath $RegistrySuiteRoot -ErrorAction SilentlyContinue).Count -eq 0) {
        Remove-Item -LiteralPath $RegistrySuiteRoot -Force -ErrorAction SilentlyContinue
    }
    if (Test-Path -LiteralPath $TestRoot) {
        Remove-Item -LiteralPath $TestRoot -Recurse -Force -ErrorAction SilentlyContinue
    }
    if ($TranscriptStarted) {
        Stop-Transcript -ErrorAction SilentlyContinue | Out-Null
    }
}
