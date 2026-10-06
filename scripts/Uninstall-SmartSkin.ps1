[CmdletBinding()]
param(
    [string]$InstallRoot = '',
    [string]$RegistryBase = 'HKCU:\Software\McNeel\Rhinoceros\8.0\Plug-ins',
    [Parameter(DontShow = $true)][switch]$AllowTestInstallRoot,
    [Parameter(DontShow = $true)][ValidateSet('', 'AfterRegistryClear', 'AfterCleanup')][string]$TestFailAt = ''
)
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'Installer-Common.ps1')
. (Join-Path $PSScriptRoot 'Installer-Lifecycle.ps1')
$Context = $null
$Backup = $null
$Snapshot = @()
$FileBackups = New-Object 'Collections.Generic.List[object]'
$RegistryChanged = $Committed = $RecoveryFailed = $false
try {
    $Context = Initialize-ProvenInstallContext $InstallRoot $RegistryBase $AllowTestInstallRoot.IsPresent $false $TestFailAt
    $Current = Join-Path $Context.Root 'current'
    Assert-ManagedChildPath $Current $Context.Root
    $Backup = Join-Path $Context.Root ('.previous-uninstall-' + $Context.Id)
    Assert-ManagedChildPath $Backup $Context.Root
    $Snapshot = Get-RegistrySnapshot $RegistryBase
    $RegisteredPaths = Get-RegisteredPluginPaths $Snapshot
    $Files = @(Get-KnownOldPluginFiles $RegisteredPaths @((Join-Path $Current 'SmartSkin.Rhino8.rhp'), (Join-Path $PSScriptRoot 'net48\SmartSkin.Rhino8.rhp')) $Context)
    foreach ($Name in $script:SmartSkinKnownRuntimeFiles + @('install-info.json')) {
        $Path = Join-Path $Current $Name
        Assert-ManagedChildPath $Path $Context.Root
        if (Test-Path -LiteralPath $Path -PathType Leaf) { $Files += $Path }
    }
    $RegistryChanged = $true
    Restore-RegistrySnapshot $RegistryBase @()
    Invoke-TestFailure $Context $TestFailAt 'AfterRegistryClear'
    foreach ($Path in @($Files | Select-Object -Unique)) { Backup-AndRemovePluginFile $Path $Backup $FileBackups }
    Invoke-TestFailure $Context $TestFailAt 'AfterCleanup'
    if (@(Get-PluginRegistryKeys $RegistryBase).Count) { throw 'Smart Skin registration removal could not be verified.' }
    $Committed = $true
    Remove-EmptyPluginDirectories @($Files | ForEach-Object { Split-Path -Parent $_ })
    Remove-EmptyPluginDirectories @((Join-Path $Current 'Python'), $Current)
    Write-InstallLog "SMARTSKIN_UNINSTALL PASS | removed_registry_keys=$(@($Snapshot | Where-Object { $_.path -notmatch '\\' }).Count) | removed_files=$($FileBackups.Count) | unrelated_files_preserved=True | Rhino_auto_launch=False"
} catch {
    $OriginalError = $_
    if ($Context -and -not $Committed) {
        try {
            Restore-RemovedPluginFiles $FileBackups
            if ($RegistryChanged) { Restore-RegistrySnapshot $RegistryBase $Snapshot }
            Write-InstallLog 'RECOVERY PASS | prior_files_and_registration_restored=True'
        } catch {
            $RecoveryFailed = $true
            Write-Warning "Recovery needs attention. Keep the temporary backup $Backup. $($_.Exception.Message)"
        }
    }
    Write-InstallLog "SMARTSKIN_UNINSTALL FAIL | error=$($OriginalError.Exception.Message)"
    throw $OriginalError
} finally {
    if ($Context) {
        if (-not $RecoveryFailed) { Remove-LifecycleTemporaryDirectory $Backup $Context.Root }
        Close-ProvenInstallContext $Context
    }
}
