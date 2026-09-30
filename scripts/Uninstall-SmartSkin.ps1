[CmdletBinding()]
param(
    [string]$InstallRoot = "",
    [string]$RegistryBase = "HKCU:\Software\McNeel\Rhinoceros\8.0\Plug-ins",
    [Parameter(DontShow = $true)]
    [switch]$AllowTestInstallRoot
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = "Stop"

$PluginGuid = "b3f42f21-1f15-45e6-9bc2-a68b0b27c877"
$KnownPluginFiles = @(
    "SmartSkin.Rhino8.rhp",
    "SmartSkin.Rhino8.pdb",
    "SmartSkin.Rhino8.deps.json",
    "SmartSkin.Core.dll",
    "SmartSkin.Core.pdb"
)

function Get-FullPath([string]$Path) {
    return [System.IO.Path]::GetFullPath($Path)
}

function Get-SmartSkinRegistryKeys([string]$BasePath, [string]$Guid) {
    if (-not (Test-Path -LiteralPath $BasePath)) {
        return @()
    }

    return @(
        Get-ChildItem -LiteralPath $BasePath -ErrorAction Stop |
            Where-Object {
                $_.PSChildName.Trim([char[]]"{}").Equals(
                    $Guid,
                    [System.StringComparison]::OrdinalIgnoreCase)
            }
    )
}

function Remove-KnownPluginFiles([string]$PluginPath, [string]$ManagedRoot) {
    if ([string]::IsNullOrWhiteSpace($PluginPath)) {
        return 0
    }

    $FullPluginPath = Get-FullPath $PluginPath
    if ([System.IO.Path]::GetFileName($FullPluginPath) -ne "SmartSkin.Rhino8.rhp") {
        throw "Refusing to clean an unexpected registered plug-in path: $FullPluginPath"
    }

    $PluginDirectory = (Split-Path -Parent $FullPluginPath).TrimEnd('\')
    $FullManagedRoot = (Get-FullPath $ManagedRoot).TrimEnd('\')
    if ($PluginDirectory.StartsWith(
        $FullManagedRoot + [System.IO.Path]::DirectorySeparatorChar,
        [System.StringComparison]::OrdinalIgnoreCase)) {
        return 0
    }

    if (-not (Test-Path -LiteralPath $PluginDirectory -PathType Container)) {
        return 0
    }

    $Removed = 0
    foreach ($Name in $KnownPluginFiles) {
        $Candidate = Join-Path $PluginDirectory $Name
        if (Test-Path -LiteralPath $Candidate -PathType Leaf) {
            Remove-Item -LiteralPath $Candidate -Force
            $Removed++
        }
    }

    if (@(Get-ChildItem -LiteralPath $PluginDirectory -Force).Count -eq 0) {
        Remove-Item -LiteralPath $PluginDirectory -Force
    }

    return $Removed
}

try {
    if ($env:OS -ne "Windows_NT") {
        throw "Smart Skin uninstallation is supported only on Windows."
    }

    $RunningRhino = @(Get-Process -Name "Rhino" -ErrorAction SilentlyContinue)
    if ($RunningRhino.Count -gt 0) {
        throw "Close every Rhino window before uninstalling Smart Skin."
    }

    if ([string]::IsNullOrWhiteSpace($env:LOCALAPPDATA)) {
        throw "LOCALAPPDATA is unavailable."
    }
    $DefaultInstallRoot = Get-FullPath (Join-Path $env:LOCALAPPDATA "SmartSkin\Rhino8")
    if ([string]::IsNullOrWhiteSpace($InstallRoot)) {
        $InstallRoot = $DefaultInstallRoot
    }
    $InstallRoot = Get-FullPath $InstallRoot
    if (-not [string]::Equals(
        $InstallRoot.TrimEnd('\'),
        $DefaultInstallRoot.TrimEnd('\'),
        [System.StringComparison]::OrdinalIgnoreCase) -and
        -not $AllowTestInstallRoot) {
        throw "Refusing to use a non-standard install root: $InstallRoot"
    }

    $RegistryKeys = @(Get-SmartSkinRegistryKeys $RegistryBase $PluginGuid)
    $RegisteredPaths = @()
    foreach ($Key in $RegistryKeys) {
        $Properties = Get-ItemProperty -LiteralPath $Key.PSPath -ErrorAction SilentlyContinue
        if ($null -ne $Properties -and
            $Properties.PSObject.Properties.Name -contains "FileName" -and
            -not [string]::IsNullOrWhiteSpace([string]$Properties.FileName)) {
            $RegisteredPaths += [string]$Properties.FileName
        }
    }

    foreach ($Key in $RegistryKeys) {
        Remove-Item -LiteralPath $Key.PSPath -Recurse -Force
    }

    $RemovedFiles = 0
    foreach ($RegisteredPath in @($RegisteredPaths | Select-Object -Unique)) {
        $RemovedFiles += Remove-KnownPluginFiles $RegisteredPath $InstallRoot
    }

    if (Test-Path -LiteralPath $InstallRoot -PathType Container) {
        Remove-Item -LiteralPath $InstallRoot -Recurse -Force
    }

    Write-Host "SMARTSKIN_UNINSTALL PASS | removed_registry_keys=$($RegistryKeys.Count) | removed_external_files=$RemovedFiles"
}
catch {
    Write-Host "SMARTSKIN_UNINSTALL FAIL | error=$($_.Exception.Message)"
    throw
}
