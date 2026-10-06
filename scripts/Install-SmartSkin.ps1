[CmdletBinding()]
param(
    [string]$PackageRoot = $PSScriptRoot,
    [string]$InstallRoot = '',
    [string]$RegistryBase = 'HKCU:\Software\McNeel\Rhinoceros\8.0\Plug-ins',
    [Parameter(DontShow = $true)][switch]$SkipRhinoInstalledCheck,
    [Parameter(DontShow = $true)][switch]$AllowTestInstallRoot,
    [Parameter(DontShow = $true)][ValidateSet('', 'AfterPayload', 'AfterRegistryClear', 'AfterRegistryWrite', 'AfterCleanup')][string]$TestFailAt = ''
)
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'Installer-Common.ps1')
. (Join-Path $PSScriptRoot 'Installer-Lifecycle.ps1')
$Version = $script:SmartSkinVersion
$Context = $null
$Stage = $Previous = $CleanupBackup = $null
$Snapshot = @()
$FileBackups = New-Object 'Collections.Generic.List[object]'
$MovedPrevious = $InstalledCurrent = $RegistryChanged = $Committed = $RecoveryFailed = $false
try {
    # A source checkout is not a runtime kit. Diagnose it before context/prerequisites.
    Assert-InstallPackageLayout $PackageRoot
    $PackageRoot = (Resolve-Path -LiteralPath $PackageRoot).Path
    $Manifest = Assert-Package $PackageRoot
    if ($Manifest.feature_status -eq 'INSTALLER_SCAFFOLD_INCOMPLETE') { throw 'An installer-test scaffold is not a runtime install kit. Download the complete GitHub CI install ZIP.' }
    $Context = Initialize-ProvenInstallContext $InstallRoot $RegistryBase $AllowTestInstallRoot.IsPresent $SkipRhinoInstalledCheck.IsPresent $TestFailAt
    if (-not $SkipRhinoInstalledCheck) { Assert-RhinoPrerequisites }
    Assert-NoForeignRegistration $RegistryBase
    $Current = Join-Path $Context.Root 'current'
    $Stage = Join-Path $Context.Root ('.staging-' + $Context.Id)
    $Previous = Join-Path $Context.Root ('.previous-' + $Context.Id)
    $CleanupBackup = Join-Path $Context.Root ('.staging-cleanup-' + $Context.Id)
    foreach ($Path in @($Current, $Stage, $Previous, $CleanupBackup)) { Assert-ManagedChildPath $Path $Context.Root }
    if ((Test-Path -LiteralPath $Current) -and -not (Test-Path -LiteralPath $Current -PathType Container)) { throw 'The managed current path is not a directory. Nothing will be replaced.' }
    $DestinationRhp = Join-Path $Current 'SmartSkin.Rhino8.rhp'
    $SourceRhp = Join-Path $PackageRoot 'net48\SmartSkin.Rhino8.rhp'
    $Snapshot = Get-RegistrySnapshot $RegistryBase
    $OldFiles = @(Get-KnownOldPluginFiles (Get-RegisteredPluginPaths $Snapshot) @($SourceRhp, $DestinationRhp) $Context)
    New-Item -ItemType Directory -Path $Stage | Out-Null
    if (Test-Path -LiteralPath $Current -PathType Container) {
        # Retain unrelated files and toolbars in current; replace only our known payload.
        foreach ($Item in Get-ChildItem -LiteralPath $Current -Recurse -Force) { Assert-NoReparsePoint $Item.FullName }
        Get-ChildItem -LiteralPath $Current -Force | Copy-Item -Destination $Stage -Recurse
    }
    foreach ($Name in $script:SmartSkinKnownRuntimeFiles) {
        $Old = Join-Path $Stage $Name
        if (Test-Path -LiteralPath $Old -PathType Leaf) { Remove-Item -LiteralPath $Old -Force }
    }
    $Payload = @($Manifest.files | Where-Object { $_.path.StartsWith('net48/') })
    foreach ($File in $Payload) {
        $Relative = ([string]$File.path).Substring(6)
        if ($Relative -notin $script:SmartSkinKnownRuntimeFiles) { throw "Unexpected runtime payload file: $Relative" }
        $Target = Join-Path $Stage $Relative
        New-Item -ItemType Directory -Path (Split-Path -Parent $Target) -Force | Out-Null
        Copy-Item -LiteralPath (Join-Path $PackageRoot $File.path) -Destination $Target -Force
        if ((Get-FileHash -LiteralPath $Target -Algorithm SHA256).Hash -ne $File.sha256) { throw "Staged payload hash mismatch: $Relative" }
    }
    Write-AtomicJson (Join-Path $Stage 'install-info.json') ([ordered]@{
        product = 'Smart Skin'; version = $Version; runtime_version = $script:SmartSkinRuntimeVersion
        plugin_guid = $script:SmartSkinGuid; source_commit = $Manifest.runtime_commit
        installed_utc = [DateTime]::UtcNow.ToString('o'); manifest_sha256 = (Get-FileHash -LiteralPath (Join-Path $PackageRoot 'manifest.json')).Hash
    })
    if (@(Get-Process -Name Rhino -ErrorAction SilentlyContinue).Count) { throw 'Rhino opened during installation. Close it and retry.' }
    if (Test-Path -LiteralPath $Current) { Move-Item -LiteralPath $Current -Destination $Previous; $MovedPrevious = $true }
    Move-Item -LiteralPath $Stage -Destination $Current
    $InstalledCurrent = $true
    foreach ($File in $Payload) {
        if ((Get-FileHash -LiteralPath (Join-Path $Current ([string]$File.path).Substring(6))).Hash -ne $File.sha256) { throw "Installed payload hash mismatch: $($File.path)" }
    }
    Invoke-TestFailure $Context $TestFailAt 'AfterPayload'
    $RegistryChanged = $true
    Restore-RegistrySnapshot $RegistryBase @()
    Invoke-TestFailure $Context $TestFailAt 'AfterRegistryClear'
    # As in the proven installer, retain settings under the canonical GUID key.
    # Duplicate brace-form registrations are retired without merging their settings.
    $CanonicalSnapshot = @($Snapshot | Where-Object { (($_.path -split '\\')[0]) -ieq $script:SmartSkinGuid })
    Restore-RegistrySnapshot $RegistryBase $CanonicalSnapshot
    $CanonicalKey = Join-Path $RegistryBase $script:SmartSkinGuid
    # Registry New-Item -Force replaces an existing key; do not erase restored settings.
    if (-not (Test-Path -LiteralPath $CanonicalKey)) { New-Item -Path $CanonicalKey -Force | Out-Null }
    New-ItemProperty -LiteralPath $CanonicalKey -Name 'Name' -PropertyType String -Value 'Smart Skin' -Force | Out-Null
    New-ItemProperty -LiteralPath $CanonicalKey -Name 'FileName' -PropertyType String -Value $DestinationRhp -Force | Out-Null
    Invoke-TestFailure $Context $TestFailAt 'AfterRegistryWrite'
    if (@(Get-PluginRegistryKeys $RegistryBase).Count -ne 1 -or -not (Test-SamePath ([string](Get-ItemProperty -LiteralPath $CanonicalKey).FileName) $DestinationRhp)) { throw 'Registry activation verification failed.' }
    foreach ($Path in $OldFiles) { Backup-AndRemovePluginFile $Path $CleanupBackup $FileBackups }
    # Test actual post-deletion rollback while temporary recovery copies still exist.
    Invoke-TestFailure $Context $TestFailAt 'AfterCleanup'
    $Committed = $true
    Remove-EmptyPluginDirectories @($OldFiles | ForEach-Object { Split-Path -Parent $_ })
    Write-InstallLog "SMARTSKIN_INSTALL PASS | version=$Version | removed_old_files=$($FileBackups.Count) | path=$DestinationRhp | Rhino_auto_launch=False"
    Write-Host 'Installation finished. Open Rhino yourself when ready. Native Rhino geometry and UI remain NOT VERIFIED.'
} catch {
    $OriginalError = $_
    if ($Context -and -not $Committed) {
        try {
            Restore-RemovedPluginFiles $FileBackups
            if ($RegistryChanged) { Restore-RegistrySnapshot $RegistryBase $Snapshot }
            if ($InstalledCurrent -and (Test-Path -LiteralPath $Current)) { Remove-Item -LiteralPath $Current -Recurse -Force }
            if ($MovedPrevious -and (Test-Path -LiteralPath $Previous)) { Move-Item -LiteralPath $Previous -Destination $Current }
            Write-InstallLog 'RECOVERY PASS | prior_files_and_registration_restored=True'
        } catch {
            $RecoveryFailed = $true
            Write-Warning "Recovery needs attention. Keep temporary backups under $($Context.Root). $($_.Exception.Message)"
        }
    }
    Write-InstallLog "SMARTSKIN_INSTALL FAIL | version=$Version | error=$($OriginalError.Exception.Message)"
    throw $OriginalError
} finally {
    if ($Context) {
        if (-not $RecoveryFailed) {
            foreach ($Path in @($Stage, $Previous, $CleanupBackup)) { Remove-LifecycleTemporaryDirectory $Path $Context.Root }
        }
        Close-ProvenInstallContext $Context
    }
}
