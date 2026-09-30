[CmdletBinding()]
param(
    [string]$PackageRoot = $PSScriptRoot,
    [string]$InstallRoot = "",
    [string]$RegistryBase = "HKCU:\Software\McNeel\Rhinoceros\8.0\Plug-ins",
    [Parameter(DontShow = $true)]
    [switch]$SkipRhinoInstalledCheck,
    [Parameter(DontShow = $true)]
    [switch]$AllowTestInstallRoot
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = "Stop"

$PluginGuid = "b3f42f21-1f15-45e6-9bc2-a68b0b27c877"
$PluginName = "Smart Skin"
$Version = "0.0.4-p02"
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

function Test-SamePath([string]$Left, [string]$Right) {
    return [string]::Equals(
        (Get-FullPath $Left).TrimEnd('\'),
        (Get-FullPath $Right).TrimEnd('\'),
        [System.StringComparison]::OrdinalIgnoreCase)
}

function Assert-ManagedChildPath([string]$Path, [string]$ManagedRoot) {
    $FullPath = (Get-FullPath $Path).TrimEnd('\')
    $FullRoot = (Get-FullPath $ManagedRoot).TrimEnd('\')
    $Prefix = $FullRoot + [System.IO.Path]::DirectorySeparatorChar

    if (-not $FullPath.StartsWith($Prefix, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to modify a path outside the managed install root: $FullPath"
    }
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

function Remove-KnownPluginFiles([string]$PluginPath, [string[]]$ProtectedPaths) {
    if ([string]::IsNullOrWhiteSpace($PluginPath)) {
        return 0
    }

    $FullPluginPath = Get-FullPath $PluginPath
    if ([System.IO.Path]::GetFileName($FullPluginPath) -ne "SmartSkin.Rhino8.rhp") {
        throw "Refusing to clean an unexpected registered plug-in path: $FullPluginPath"
    }

    foreach ($ProtectedPath in $ProtectedPaths) {
        if (Test-SamePath $FullPluginPath $ProtectedPath) {
            return 0
        }
    }

    $Directory = Split-Path -Parent $FullPluginPath
    if (-not (Test-Path -LiteralPath $Directory -PathType Container)) {
        return 0
    }

    $Removed = 0
    foreach ($Name in $KnownPluginFiles) {
        $Candidate = Join-Path $Directory $Name
        if (Test-Path -LiteralPath $Candidate -PathType Leaf) {
            Remove-Item -LiteralPath $Candidate -Force
            $Removed++
        }
    }

    if (@(Get-ChildItem -LiteralPath $Directory -Force).Count -eq 0) {
        Remove-Item -LiteralPath $Directory -Force
    }

    return $Removed
}

try {
    if ($env:OS -ne "Windows_NT") {
        throw "Smart Skin installation is supported only on Windows."
    }

    if (-not $SkipRhinoInstalledCheck) {
        $RhinoInstallKey = "HKLM:\SOFTWARE\McNeel\Rhinoceros\8.0\Install"
        if (-not (Test-Path -LiteralPath $RhinoInstallKey)) {
            throw "Rhino 8 installation was not found."
        }
    }

    $RunningRhino = @(Get-Process -Name "Rhino" -ErrorAction SilentlyContinue)
    if ($RunningRhino.Count -gt 0) {
        throw "Close every Rhino window before installing Smart Skin."
    }

    $ResolvedPackageRoot = (Resolve-Path -LiteralPath $PackageRoot).Path
    $SourceDirectory = Join-Path $ResolvedPackageRoot "net48"
    $SourceRhp = Join-Path $SourceDirectory "SmartSkin.Rhino8.rhp"
    $SourceCore = Join-Path $SourceDirectory "SmartSkin.Core.dll"

    if (-not (Test-Path -LiteralPath $SourceRhp -PathType Leaf)) {
        throw "Package is incomplete: $SourceRhp was not found."
    }
    if (-not (Test-Path -LiteralPath $SourceCore -PathType Leaf)) {
        throw "Package is incomplete: $SourceCore was not found."
    }

    if ([string]::IsNullOrWhiteSpace($env:LOCALAPPDATA)) {
        throw "LOCALAPPDATA is unavailable."
    }
    $DefaultInstallRoot = Get-FullPath (Join-Path $env:LOCALAPPDATA "SmartSkin\Rhino8")
    if ([string]::IsNullOrWhiteSpace($InstallRoot)) {
        $InstallRoot = $DefaultInstallRoot
    }
    $InstallRoot = Get-FullPath $InstallRoot
    if (-not (Test-SamePath $InstallRoot $DefaultInstallRoot) -and -not $AllowTestInstallRoot) {
        throw "Refusing to use a non-standard install root: $InstallRoot"
    }
    $CurrentDirectory = Join-Path $InstallRoot "current"
    $StagingDirectory = Join-Path $InstallRoot (".staging-" + [Guid]::NewGuid().ToString("N"))
    $BackupDirectory = Join-Path $InstallRoot (".previous-" + [Guid]::NewGuid().ToString("N"))
    $DestinationRhp = Join-Path $CurrentDirectory "SmartSkin.Rhino8.rhp"

    Assert-ManagedChildPath $CurrentDirectory $InstallRoot
    Assert-ManagedChildPath $StagingDirectory $InstallRoot
    Assert-ManagedChildPath $BackupDirectory $InstallRoot

    New-Item -ItemType Directory -Path $InstallRoot -Force | Out-Null
    New-Item -ItemType Directory -Path $StagingDirectory -Force | Out-Null

    foreach ($Name in $KnownPluginFiles) {
        $Candidate = Join-Path $SourceDirectory $Name
        if (Test-Path -LiteralPath $Candidate -PathType Leaf) {
            Copy-Item -LiteralPath $Candidate -Destination $StagingDirectory -Force
        }
    }

    $StagedRhp = Join-Path $StagingDirectory "SmartSkin.Rhino8.rhp"
    $StagedCore = Join-Path $StagingDirectory "SmartSkin.Core.dll"
    if (-not (Test-Path -LiteralPath $StagedRhp -PathType Leaf) -or
        -not (Test-Path -LiteralPath $StagedCore -PathType Leaf)) {
        throw "Staging validation failed."
    }

    $SourceHash = (Get-FileHash -LiteralPath $SourceRhp -Algorithm SHA256).Hash
    $StagedHash = (Get-FileHash -LiteralPath $StagedRhp -Algorithm SHA256).Hash
    if ($SourceHash -ne $StagedHash) {
        throw "Staged plug-in hash does not match the package."
    }

    [ordered]@{
        product = $PluginName
        version = $Version
        plugin_guid = $PluginGuid
        installed_utc = [DateTime]::UtcNow.ToString("o")
        source_sha256 = $SourceHash
    } | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $StagingDirectory "install-info.json") -Encoding UTF8

    $RegistryKeys = @(Get-SmartSkinRegistryKeys $RegistryBase $PluginGuid)
    $OldPluginPaths = @()
    foreach ($Key in $RegistryKeys) {
        $Properties = Get-ItemProperty -LiteralPath $Key.PSPath -ErrorAction SilentlyContinue
        if ($null -ne $Properties -and
            $Properties.PSObject.Properties.Name -contains "FileName" -and
            -not [string]::IsNullOrWhiteSpace([string]$Properties.FileName)) {
            $OldPluginPaths += [string]$Properties.FileName
        }
    }
    $OldPluginPaths = @($OldPluginPaths | Select-Object -Unique)

    $HadCurrent = Test-Path -LiteralPath $CurrentDirectory -PathType Container
    if ($HadCurrent) {
        Move-Item -LiteralPath $CurrentDirectory -Destination $BackupDirectory
    }

    try {
        Move-Item -LiteralPath $StagingDirectory -Destination $CurrentDirectory

        if ((Get-FileHash -LiteralPath $DestinationRhp -Algorithm SHA256).Hash -ne $SourceHash) {
            throw "Installed plug-in hash does not match the package."
        }
    }
    catch {
        if (Test-Path -LiteralPath $CurrentDirectory) {
            Remove-Item -LiteralPath $CurrentDirectory -Recurse -Force
        }
        if ($HadCurrent -and (Test-Path -LiteralPath $BackupDirectory)) {
            Move-Item -LiteralPath $BackupDirectory -Destination $CurrentDirectory
        }
        throw
    }

    New-Item -Path $RegistryBase -Force | Out-Null
    $CanonicalRegistryKey = Join-Path $RegistryBase $PluginGuid
    New-Item -Path $CanonicalRegistryKey -Force | Out-Null
    New-ItemProperty -Path $CanonicalRegistryKey -Name "Name" -PropertyType String -Value $PluginName -Force | Out-Null
    New-ItemProperty -Path $CanonicalRegistryKey -Name "FileName" -PropertyType String -Value $DestinationRhp -Force | Out-Null

    $RegisteredPath = (Get-ItemProperty -LiteralPath $CanonicalRegistryKey -Name "FileName").FileName
    if (-not (Test-SamePath ([string]$RegisteredPath) $DestinationRhp)) {
        throw "Registry validation failed."
    }

    foreach ($Key in $RegistryKeys) {
        if ($Key.PSChildName -ne $PluginGuid -and
            (Test-Path -LiteralPath $Key.PSPath)) {
            Remove-Item -LiteralPath $Key.PSPath -Recurse -Force
        }
    }

    $RemovedOldFiles = 0
    foreach ($OldPluginPath in $OldPluginPaths) {
        $RemovedOldFiles += Remove-KnownPluginFiles $OldPluginPath @($SourceRhp, $DestinationRhp)
    }

    if (Test-Path -LiteralPath $BackupDirectory) {
        Remove-Item -LiteralPath $BackupDirectory -Recurse -Force
    }

    Write-Host "Smart Skin $Version installed for Rhino 8."
    Write-Host "Old registered Smart Skin files removed: $RemovedOldFiles"
    Write-Host "SMARTSKIN_INSTALL PASS | version=$Version | removed_old_files=$RemovedOldFiles | path=$DestinationRhp"
}
catch {
    Write-Host "SMARTSKIN_INSTALL FAIL | version=$Version | error=$($_.Exception.Message)"
    throw
}
