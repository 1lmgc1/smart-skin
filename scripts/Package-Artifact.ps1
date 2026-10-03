[CmdletBinding()]
param(
    [string]$Configuration = "Release",
    [string]$Version = "0.0.14-p07f2",
    [string]$Commit = "local",
    [string]$OutputRoot = ""
)
$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
if ([string]::IsNullOrWhiteSpace($OutputRoot)) { $OutputRoot = Join-Path $RepoRoot "artifacts" }
elseif (-not [System.IO.Path]::IsPathRooted($OutputRoot)) { $OutputRoot = Join-Path $RepoRoot $OutputRoot }
$CommitLabel = $Commit -replace "[^0-9A-Za-z._-]", "_"
if ($CommitLabel.Length -gt 12) { $CommitLabel = $CommitLabel.Substring(0, 12) }
$PackageName = "SmartSkin-$Version-$CommitLabel-rh8-win-x64"
$Stage = Join-Path $OutputRoot $PackageName
$ZipPath = Join-Path $OutputRoot "$PackageName.zip"
New-Item -ItemType Directory -Force $OutputRoot | Out-Null
if (Test-Path $Stage) { Remove-Item -Recurse -Force $Stage }
if (Test-Path $ZipPath) { Remove-Item -Force $ZipPath }
New-Item -ItemType Directory -Force $Stage | Out-Null
$Source = Join-Path $RepoRoot "src\SmartSkin.Rhino8\bin\$Configuration\net48"
foreach ($Name in @("SmartSkin.Rhino8.rhp", "SmartSkin.Core.dll", "SmartSkin.Rhino8.rui")) {
    if (-not (Test-Path (Join-Path $Source $Name))) { throw "Required output missing: $Name" }
}
& (Join-Path $PSScriptRoot "Test-Toolbar.ps1") -RuiPath (Join-Path $Source "SmartSkin.Rhino8.rui")
$Destination = Join-Path $Stage "net48"
New-Item -ItemType Directory -Force $Destination | Out-Null
foreach ($Name in @("SmartSkin.Rhino8.rhp", "SmartSkin.Rhino8.rui", "SmartSkin.Rhino8.pdb", "SmartSkin.Rhino8.deps.json", "SmartSkin.Core.dll", "SmartSkin.Core.pdb")) {
    $Candidate = Join-Path $Source $Name
    if (Test-Path $Candidate) { Copy-Item $Candidate $Destination }
}
foreach ($Name in @("FIELD_TEST.md", "PATCH_NOTES.md", "P07F1_VERIFICATION.md", "P07F2_VERIFICATION.md")) {
    Copy-Item (Join-Path (Join-Path $RepoRoot "docs") $Name) $Stage
}
foreach ($Name in @("INSTALL.cmd", "UNINSTALL.cmd", "Install-SmartSkin.ps1", "Uninstall-SmartSkin.ps1", "Test-Toolbar.ps1")) {
    $InstallerFile = Join-Path $PSScriptRoot $Name
    if (-not (Test-Path -LiteralPath $InstallerFile -PathType Leaf)) { throw "Required installer missing: $Name" }
    Copy-Item -LiteralPath $InstallerFile -Destination $Stage
}
@(
    "package=$PackageName"
    "version=$Version"
    "patch=P07F2"
    "commit=$Commit"
    "configuration=$Configuration"
    "installer=managed-v1"
    "minimum_rhino=8.21"
    "toolbar=SmartSkin.Rhino8.rui"
    "toolbar_sha256=$((Get-FileHash -LiteralPath (Join-Path $Stage 'net48\SmartSkin.Rhino8.rui') -Algorithm SHA256).Hash)"
    "native_geometry=NOT_VERIFIED_UNTIL_RHINO_FIELD_TEST"
    "created_utc=$([DateTime]::UtcNow.ToString('o'))"
) | Set-Content (Join-Path $Stage "build-info.txt") -Encoding UTF8
Compress-Archive -Path (Join-Path $Stage "*") -DestinationPath $ZipPath -CompressionLevel Optimal
if ($env:GITHUB_OUTPUT) {
    "artifact_path=$ZipPath" | Out-File -FilePath $env:GITHUB_OUTPUT -Encoding utf8 -Append
    "package_root=$Stage" | Out-File -FilePath $env:GITHUB_OUTPUT -Encoding utf8 -Append
}
Write-Host "Created $ZipPath"
