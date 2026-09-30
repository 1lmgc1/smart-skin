[CmdletBinding()]
param(
    [string]$Configuration = "Release",
    [string]$Version = "0.0.4-p02",
    [string]$Commit = "local",
    [string]$OutputRoot = ""
)

$ErrorActionPreference = "Stop"

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
if ([string]::IsNullOrWhiteSpace($OutputRoot)) {
    $OutputRoot = Join-Path $RepoRoot "artifacts"
}
elseif (-not [System.IO.Path]::IsPathRooted($OutputRoot)) {
    $OutputRoot = Join-Path $RepoRoot $OutputRoot
}

$CommitLabel = $Commit -replace "[^0-9A-Za-z._-]", "_"
if ($CommitLabel.Length -gt 12) {
    $CommitLabel = $CommitLabel.Substring(0, 12)
}

$PackageName = "SmartSkin-$Version-$CommitLabel-rh8-win-x64"
$Stage = Join-Path $OutputRoot $PackageName
$ZipPath = Join-Path $OutputRoot "$PackageName.zip"

New-Item -ItemType Directory -Force $OutputRoot | Out-Null
if (Test-Path $Stage) {
    Remove-Item -Recurse -Force $Stage
}
if (Test-Path $ZipPath) {
    Remove-Item -Force $ZipPath
}
New-Item -ItemType Directory -Force $Stage | Out-Null

foreach ($TargetFramework in @("net48")) {
    $Source = Join-Path $RepoRoot "src\SmartSkin.Rhino8\bin\$Configuration\$TargetFramework"
    $Rhp = Join-Path $Source "SmartSkin.Rhino8.rhp"
    $Core = Join-Path $Source "SmartSkin.Core.dll"

    if (-not (Test-Path $Rhp)) {
        throw "Required plug-in output not found: $Rhp"
    }
    if (-not (Test-Path $Core)) {
        throw "Required core output not found: $Core"
    }

    $Destination = Join-Path $Stage $TargetFramework
    New-Item -ItemType Directory -Force $Destination | Out-Null

    foreach ($Name in @(
        "SmartSkin.Rhino8.rhp",
        "SmartSkin.Rhino8.pdb",
        "SmartSkin.Rhino8.deps.json",
        "SmartSkin.Core.dll",
        "SmartSkin.Core.pdb"
    )) {
        $Candidate = Join-Path $Source $Name
        if (Test-Path $Candidate) {
            Copy-Item $Candidate $Destination
        }
    }
}

Copy-Item (Join-Path $RepoRoot "docs\FIELD_TEST.md") $Stage
Copy-Item (Join-Path $RepoRoot "docs\PATCH_NOTES.md") $Stage

foreach ($Name in @(
    "INSTALL.cmd",
    "UNINSTALL.cmd",
    "Install-SmartSkin.ps1",
    "Uninstall-SmartSkin.ps1"
)) {
    $InstallerFile = Join-Path (Join-Path $RepoRoot "scripts") $Name
    if (-not (Test-Path -LiteralPath $InstallerFile -PathType Leaf)) {
        throw "Required installer file not found: $InstallerFile"
    }
    Copy-Item -LiteralPath $InstallerFile -Destination $Stage
}

@(
    "package=$PackageName"
    "version=$Version"
    "patch=P02"
    "commit=$Commit"
    "configuration=$Configuration"
    "installer=managed-v1"
    "created_utc=$([DateTime]::UtcNow.ToString('o'))"
) | Set-Content (Join-Path $Stage "build-info.txt") -Encoding UTF8

Compress-Archive -Path (Join-Path $Stage "*") -DestinationPath $ZipPath -CompressionLevel Optimal

if ($env:GITHUB_OUTPUT) {
    "artifact_path=$ZipPath" | Out-File -FilePath $env:GITHUB_OUTPUT -Encoding utf8 -Append
    "package_root=$Stage" | Out-File -FilePath $env:GITHUB_OUTPUT -Encoding utf8 -Append
}

Write-Host "Created $ZipPath"
