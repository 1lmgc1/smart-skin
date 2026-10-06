# Small shared lifecycle helpers for the proven HKCU/current installer.
# No administrator-token policy, machine-registration migration or persistent journal.
$script:SmartSkinKnownPluginFiles = @(
    'SmartSkin.Rhino8.rhp', 'SmartSkin.Rhino8.rui', 'SmartSkin.Rhino8.pdb',
    'SmartSkin.Rhino8.deps.json', 'SmartSkin.Core.dll', 'SmartSkin.Core.pdb'
)
$script:SmartSkinKnownRuntimeFiles = $script:SmartSkinKnownPluginFiles + @(
    'Python/smart_skin.py', 'Python/native_input.py', 'Python/native_family.py',
    'Python/skin_kernel.py', 'Python/preview.py', 'Python/native_boundary_evidence.py',
    'Python/fan_shared_jets.py', 'Python/fan_rational_fields.py', 'Python/fan_geometry.py',
    'Python/lower_corner_geometry.py', 'Python/upper_corner_geometry.py',
    'Python/upper_corner_certificate.py', 'Python/constrained_uv.py', 'Python/repaired_validation.py', 'Python/native_owner_separation.py', 'Python/atlas_separation.py'
)

function Assert-InstallPackageLayout([string]$Root) {
    if (-not (Test-Path -LiteralPath (Join-Path $Root 'manifest.json') -PathType Leaf) -or
        -not (Test-Path -LiteralPath (Join-Path $Root 'net48') -PathType Container)) {
        throw 'SOURCE_LAYOUT: An extracted runtime install package must contain manifest.json and net48 at its root. A source checkout or scripts directory is not an install kit. Download the install ZIP from the successful GitHub Windows CI run, extract it completely, and run its root INSTALL.cmd. This script does not build from source.'
    }
}

function Initialize-ProvenInstallContext([string]$InstallRoot, [string]$RegistryBase, [bool]$AllowTestInstallRoot, [bool]$SkipRhinoInstalledCheck, [string]$TestFailAt) {
    if ($env:OS -ne 'Windows_NT') { throw 'Smart Skin installation and uninstallation require Windows.' }
    if (-not [Environment]::Is64BitProcess) { throw 'Use the supplied CMD launcher or 64-bit Windows PowerShell.' }
    if ($PSVersionTable.PSVersion -lt [version]'5.1') { throw 'Windows PowerShell 5.1 or later is required.' }
    if (-not $env:LOCALAPPDATA) { throw 'LOCALAPPDATA is unavailable.' }
    $DefaultRoot = Get-FullPath (Join-Path $env:LOCALAPPDATA 'SmartSkin\Rhino8')
    if (-not $InstallRoot) { $InstallRoot = $DefaultRoot }
    $InstallRoot = Get-FullPath $InstallRoot
    $TestRoot = $null
    if ($AllowTestInstallRoot) {
        if ($RegistryBase -cnotmatch '^HKCU:\\Software\\SmartSkinInstallerTests\\[0-9a-f]{32}\\Plug-ins$') {
            throw 'Test mode requires a unique isolated HKCU SmartSkinInstallerTests registry root.'
        }
        $TestGuid = ($RegistryBase -split '\\')[-2]
        $TestTemp = if ($env:RUNNER_TEMP) { $env:RUNNER_TEMP } else { [IO.Path]::GetTempPath() }
        $TestRoot = Join-Path $TestTemp ('SmartSkinInstallerTest-' + $TestGuid)
        if (-not (Test-SamePath $InstallRoot (Join-Path $TestRoot 'install')) -or (Test-SamePath $InstallRoot $DefaultRoot)) {
            throw 'Test mode requires the matching isolated temporary filesystem root; the production install root is forbidden.'
        }
    } elseif (-not (Test-SamePath $InstallRoot $DefaultRoot) -or $RegistryBase -ne $script:SmartSkinRegistryBase) {
        throw 'A custom installation/registry root is permitted only by the isolated test harness.'
    }
    if (($SkipRhinoInstalledCheck -or $TestFailAt) -and -not $AllowTestInstallRoot) {
        throw 'Prerequisite bypass/failure injection is restricted to the isolated test harness.'
    }
    if (@(Get-Process -Name Rhino -ErrorAction SilentlyContinue).Count) {
        throw 'Close every Rhino window and retry. Rhino will not be launched automatically.'
    }
    Assert-NoReparsePoint $InstallRoot
    # Directory creation/locking happens only after package and context validation.
    New-Item -ItemType Directory -Path $InstallRoot -Force | Out-Null
    $LockPath = Join-Path $InstallRoot 'installer.lock'
    Assert-ManagedChildPath $LockPath $InstallRoot
    $Lock = [IO.File]::Open($LockPath, [IO.FileMode]::OpenOrCreate, [IO.FileAccess]::ReadWrite, [IO.FileShare]::None)
    return [pscustomobject]@{ Root = $InstallRoot; RegistryBase = $RegistryBase; Test = $AllowTestInstallRoot; TestRoot = $TestRoot; Id = [Guid]::NewGuid().ToString('N'); Lock = $Lock; LockPath = $LockPath }
}

function Close-ProvenInstallContext($Context) {
    if (-not $Context) { return }
    $Context.Lock.Dispose()
    try {
        Remove-Item -LiteralPath $Context.LockPath -Force
        if (@(Get-ChildItem -LiteralPath $Context.Root -Force).Count -eq 0) { Remove-Item -LiteralPath $Context.Root -Force }
    } catch { Write-Warning "Temporary installer lock could not be removed: $($_.Exception.Message)" }
}

function Get-RegisteredPluginPaths($Snapshot) {
    return @($Snapshot | Where-Object { $_.path -notmatch '\\' } | ForEach-Object {
        foreach ($Value in @($_.values)) {
            if ($Value.name -eq 'FileName' -and $Value.data) { Get-SnapshotFilePath $Value }
        }
    } | Select-Object -Unique)
}

function Get-KnownOldPluginFiles([string[]]$PluginPaths, [string[]]$ProtectedPaths, $Context) {
    $Seen = @{}
    foreach ($PluginPath in $PluginPaths) {
        $Full = Get-FullPath $PluginPath
        if ([IO.Path]::GetFileName($Full) -ine 'SmartSkin.Rhino8.rhp') { throw "Refusing to clean an unexpected registered plug-in path: $Full" }
        $Protected = $false
        foreach ($Path in $ProtectedPaths) { if (Test-SamePath $Full $Path) { $Protected = $true; break } }
        if ($Protected) { continue }
        $Directory = Split-Path -Parent $Full
        if ($Context.Test) { Assert-ManagedChildPath $Directory $Context.TestRoot }
        Assert-NoReparsePoint $Directory
        foreach ($Name in $script:SmartSkinKnownPluginFiles) {
            $Candidate = Join-Path $Directory $Name
            Assert-NoReparsePoint $Candidate
            if ((Test-Path -LiteralPath $Candidate -PathType Leaf) -and -not $Seen.ContainsKey($Candidate)) {
                $Seen[$Candidate] = $true
                $Candidate
            }
        }
    }
}

function Backup-AndRemovePluginFile([string]$Path, [string]$BackupRoot, $Backups) {
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { return }
    Assert-NoReparsePoint $Path
    New-Item -ItemType Directory -Path $BackupRoot -Force | Out-Null
    $Backup = Join-Path $BackupRoot ([Guid]::NewGuid().ToString('N'))
    Copy-Item -LiteralPath $Path -Destination $Backup -Force
    if ((Get-FileHash -LiteralPath $Backup).Hash -ne (Get-FileHash -LiteralPath $Path).Hash) { throw "Cleanup backup verification failed: $Path" }
    $Backups.Add([pscustomobject]@{ Path = $Path; Backup = $Backup })
    Remove-Item -LiteralPath $Path -Force
}

function Restore-RemovedPluginFiles($Backups) {
    foreach ($Entry in @($Backups.ToArray())) {
        $Directory = Split-Path -Parent $Entry.Path
        New-Item -ItemType Directory -Path $Directory -Force | Out-Null
        Copy-Item -LiteralPath $Entry.Backup -Destination $Entry.Path -Force
        if ((Get-FileHash -LiteralPath $Entry.Backup).Hash -ne (Get-FileHash -LiteralPath $Entry.Path).Hash) { throw "Cleanup recovery verification failed: $($Entry.Path)" }
    }
}

function Remove-EmptyPluginDirectories([string[]]$Directories, [string]$StopAt = '') {
    foreach ($Directory in @($Directories | Select-Object -Unique)) {
        try {
            if ($StopAt -and (Test-SamePath $Directory $StopAt)) { continue }
            if ((Test-Path -LiteralPath $Directory -PathType Container) -and @(Get-ChildItem -LiteralPath $Directory -Force).Count -eq 0) {
                Remove-Item -LiteralPath $Directory -Force
            }
        } catch { Write-Warning "An empty former plugin directory could not be removed: $Directory. $($_.Exception.Message)" }
    }
}

function Remove-LifecycleTemporaryDirectory([string]$Path, [string]$Root) {
    if ($Path -and (Test-Path -LiteralPath $Path)) {
        Assert-ManagedChildPath $Path $Root
        try { Remove-Item -LiteralPath $Path -Recurse -Force }
        catch { Write-Warning "Installation state is committed/restored, but temporary cleanup is incomplete: $Path. $($_.Exception.Message)" }
    }
}
