[CmdletBinding()]
param(
    [string]$Configuration = 'Release',
    [string]$Version = "0.0.18-p08e1f4",
    [string]$Commit = 'local',
    [string]$OutputRoot = '',
    [switch]$InstallerScaffold
)
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'Installer-Common.ps1')
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
if ($Version -ne $script:SmartSkinVersion -or (Get-Content -LiteralPath (Join-Path $RepoRoot 'VERSION') -Raw).Trim() -ne $Version) { throw 'Requested/repository/installer package versions disagree.' }
[xml]$Props = Get-Content -LiteralPath (Join-Path $RepoRoot 'Directory.Build.props') -Raw
if (($Props.Project.PropertyGroup.VersionPrefix + '-' + $Props.Project.PropertyGroup.VersionSuffix) -ne $script:SmartSkinRuntimeVersion) { throw 'Build properties and package version disagree.' }
if ($Configuration -notin @('Release', 'Debug')) { throw 'Unsupported build configuration.' }
if ([string]::IsNullOrWhiteSpace($OutputRoot)) { $OutputRoot = Join-Path $RepoRoot 'artifacts' }
elseif (-not [IO.Path]::IsPathRooted($OutputRoot)) { $OutputRoot = Join-Path $RepoRoot $OutputRoot }
$OutputRoot = Get-FullPath $OutputRoot
Assert-NoReparsePoint $OutputRoot
$CommitLabel = $Commit -replace '[^0-9A-Za-z._-]', '_'
if (-not $CommitLabel) { throw 'Commit label is required.' }
if ($CommitLabel.Length -gt 12) { $CommitLabel = $CommitLabel.Substring(0, 12) }
$PackageName = "SmartSkin-$Version-$CommitLabel-rh8-win-x64"
if ($InstallerScaffold) { $PackageName += '-installer-scaffold' }
$FeatureStatus = if ($InstallerScaffold) { 'INSTALLER_SCAFFOLD_INCOMPLETE' } else { 'EXPERIMENTAL_NATIVE_CURVATURE' }
$Stage = Join-Path $OutputRoot $PackageName
$ZipPath = Join-Path $OutputRoot "$PackageName.zip"
if ((Test-Path -LiteralPath $Stage) -or (Test-Path -LiteralPath $ZipPath)) { throw "Refusing to overwrite an existing bundle: $PackageName. Use a new output directory or a new build/version identity." }
$Source = Join-Path $RepoRoot "src/SmartSkin.Rhino8/bin/$Configuration/net48"
foreach ($Name in @('SmartSkin.Rhino8.rhp', 'SmartSkin.Core.dll', 'SmartSkin.Rhino8.rui')) {
    if (-not (Test-Path -LiteralPath (Join-Path $Source $Name) -PathType Leaf)) { throw "Required real build output missing: $Name. Build the solution first." }
}
$Assemblies = [ordered]@{}
foreach ($Spec in @(@('SmartSkin.Rhino8.rhp', 'SmartSkin.Rhino8'), @('SmartSkin.Core.dll', 'SmartSkin.Core'))) {
    $Identity = Get-AssemblyIdentity (Join-Path $Source $Spec[0]) $Spec[1] $script:SmartSkinRuntimeVersion
    if ($Commit -ne 'local' -and $Identity.informational_version -ne ($script:SmartSkinRuntimeVersion + "+" + $Commit)) { throw "Built assembly is not from the requested commit: $($Spec[1])." }
    if ($Identity.informational_version -match 'installer-scaffold' -and -not $InstallerScaffold) { throw 'This build is incomplete installer scaffolding; package only with -InstallerScaffold for isolated tests.' }
    $Assemblies[$Spec[1]] = $Identity
}
# Rhino supplies these assemblies. Shipping private copies risks runtime conflicts.
foreach ($Name in @('RhinoCommon.dll', 'Rhino.UI.dll', 'Eto.dll')) {
    if (Test-Path -LiteralPath (Join-Path $Source $Name)) { throw "Unexpected host assembly in plug-in output: $Name" }
}
& (Join-Path $PSScriptRoot 'Test-Toolbar.ps1') -RuiPath (Join-Path $Source 'SmartSkin.Rhino8.rui') -StructureOnly:($env:OS -ne 'Windows_NT')
New-Item -ItemType Directory -Path $OutputRoot -Force | Out-Null
$Working = Join-Path $OutputRoot ('.package-' + [Guid]::NewGuid().ToString('N'))
$TempZip = Join-Path $OutputRoot ('.package-' + [Guid]::NewGuid().ToString('N') + '.zip')
try {
    New-Item -ItemType Directory -Path (Join-Path $Working 'net48') -Force | Out-Null
    foreach ($Item in Get-ChildItem -LiteralPath $Source -Recurse -Force) {
        if ($Item.Name -eq '__pycache__' -or $Item.Extension -in @('.pyc', '.pyo', '.3dm', '.step', '.stp', '.brep', '.obj')) { throw "Unsafe/stale build output must not ship: $($Item.Name). Clean and rebuild." }
        if (($Item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) { throw "Build output contains a link: $($Item.FullName)" }
    }
    Get-ChildItem -LiteralPath $Source -Force | Copy-Item -Destination (Join-Path $Working 'net48') -Recurse
    # Current release instructions only: do not mislabel old P07 field instructions as this release's protocol.
    Copy-Item -LiteralPath (Join-Path $RepoRoot 'docs/INSTALL_CURVATURE_RU.md') -Destination $Working
    Copy-Item -LiteralPath (Join-Path $RepoRoot 'docs/P08E1F2_PIPELINE_REPAIR.md') -Destination $Working
    Copy-Item -LiteralPath (Join-Path $RepoRoot 'docs/P08E1F3_COMPOUND_EDGE_REPAIR.md') -Destination $Working
    Copy-Item -LiteralPath (Join-Path $RepoRoot 'docs/P08E1F3_NATIVE_OWNER_SCREEN.md') -Destination $Working
    Copy-Item -LiteralPath (Join-Path $RepoRoot 'docs/P08E1F4_NATIVE_FRAME_REPAIR.md') -Destination $Working
    if (Test-Path -LiteralPath (Join-Path $RepoRoot 'docs/P08E1_CURVATURE_CONTROL.md')) { Copy-Item -LiteralPath (Join-Path $RepoRoot 'docs/P08E1_CURVATURE_CONTROL.md') -Destination $Working }
    foreach ($Name in @('INSTALL.cmd', 'UNINSTALL.cmd', 'Install-SmartSkin.ps1', 'Uninstall-SmartSkin.ps1', 'Installer-Common.ps1', 'Installer-Lifecycle.ps1', 'Test-Toolbar.ps1')) {
        Copy-Item -LiteralPath (Join-Path $PSScriptRoot $Name) -Destination $Working
    }
    @(
        "package=$PackageName", "version=$Version", 'patch=P08E1F4', "commit=$Commit", "configuration=$Configuration",
        "ci_repository=$env:GITHUB_REPOSITORY", "ci_run_id=$env:GITHUB_RUN_ID", "ci_run_attempt=$env:GITHUB_RUN_ATTEMPT", "ci_ref=$env:GITHUB_REF",
        'installer=proven-current-hkcu', ('runtime_version=' + $script:SmartSkinRuntimeVersion), ('runtime_commit=' + $Commit), ('installer_commit=' + $Commit), 'minimum_rhino=8.21', 'target_framework=net48', 'geometry_runtime=Rhino-managed CPython >=3.9', 'python_packages=numpy==1.26.4;scipy==1.13.1;mpmath==1.3.0',
        'native_geometry=NOT VERIFIED', 'native_UI=NOT VERIFIED', 'automatic_Rhino_launch=False',
        "feature_status=$FeatureStatus", 'scope=experimental live curvature control', 'lifecycle=current;known_owned_cleanup;genuine_uninstall',
        "created_utc=$([DateTime]::UtcNow.ToString('o'))"
    ) | Set-Content -LiteralPath (Join-Path $Working 'build-info.txt') -Encoding UTF8
    $Files = @(Get-ChildItem -LiteralPath $Working -Recurse -File -Force | Sort-Object FullName | ForEach-Object {
        [ordered]@{ path = $_.FullName.Substring($Working.Length + 1).Replace('\', '/'); size = $_.Length; sha256 = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant() }
    })
    Write-AtomicJson (Join-Path $Working 'manifest.json') ([ordered]@{
        schema = 1; product = 'Smart Skin'; version = $Version; runtime_version = $script:SmartSkinRuntimeVersion; installer_revision = 'f4'; installer_commit = $Commit; runtime_commit = $Commit; patch = 'P08E1F4'; commit = $Commit
        feature_status = $FeatureStatus; plugin_guid = $script:SmartSkinGuid; minimum_rhino = '8.21'; target_framework = 'net48'
        runtime = [ordered]@{ rhino_cpython_min = '3.9'; packages = [ordered]@{ numpy = '1.26.4'; scipy = '1.13.1'; mpmath = '1.3.0' } }
        verification = 'NOT VERIFIED: native Rhino geometry, loading and UI'; assemblies = $Assemblies; files = $Files
    })
    $null = Assert-Package $Working
    Compress-Archive -Path (Join-Path $Working '*') -DestinationPath $TempZip -CompressionLevel Optimal
    # Neither final path is overwritten. An interrupted packaging run preserves prior bundles.
    [IO.Directory]::Move($Working, $Stage)
    [IO.File]::Move($TempZip, $ZipPath)
    if ($env:GITHUB_OUTPUT) {
        "artifact_path=$ZipPath" | Out-File -FilePath $env:GITHUB_OUTPUT -Encoding utf8 -Append
        "package_root=$Stage" | Out-File -FilePath $env:GITHUB_OUTPUT -Encoding utf8 -Append
    }
    Write-Host "Created $ZipPath"
    Write-Host "SHA256 $((Get-FileHash -LiteralPath $ZipPath -Algorithm SHA256).Hash)"
    Write-Host 'Native Rhino behavior: NOT VERIFIED. Package hash integrity is not a digital signature.'
} finally {
    if (Test-Path -LiteralPath $Working) { Remove-Item -LiteralPath $Working -Recurse -Force }
    if (Test-Path -LiteralPath $TempZip) { Remove-Item -LiteralPath $TempZip -Force }
}
