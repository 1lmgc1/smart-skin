[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$Version = (Get-Content -LiteralPath (Join-Path $Root 'VERSION') -Raw).Trim()
[xml]$Props = Get-Content -LiteralPath (Join-Path $Root 'Directory.Build.props') -Raw
if ($Version -ne '0.0.19-p08e1f5' -or ($Props.Project.PropertyGroup.VersionPrefix + '-' + $Props.Project.PropertyGroup.VersionSuffix) -ne $Version) { throw 'P08E1 version identity mismatch.' }
$Common = Get-Content -LiteralPath (Join-Path $PSScriptRoot 'Installer-Common.ps1') -Raw
if ($Common -notmatch "SmartSkinVersion = '0.0.19-p08e1f5'" -or $Common -notmatch "SmartSkinRuntimeVersion = '0.0.19-p08e1f5'") { throw 'Installer/runtime version separation mismatch.' }
if ((Get-Content -LiteralPath (Join-Path $PSScriptRoot 'Install-SmartSkin.ps1') -Raw) -notmatch '\$Version = \$script:SmartSkinVersion') { throw 'Installer must report its bundle identity.' }
[xml]$Plugin = Get-Content -LiteralPath (Join-Path $Root 'src/SmartSkin.Rhino8/SmartSkin.Rhino8.csproj') -Raw
if ($Plugin.Project.PropertyGroup.TargetFramework -ne 'net48') { throw 'Native package must retain net48 compatibility.' }
$AssemblyInfo = Get-Content -LiteralPath (Join-Path $Root 'src/SmartSkin.Rhino8/Properties/AssemblyInfo.cs') -Raw
if ($AssemblyInfo -notmatch 'b3f42f21-1f15-45e6-9bc2-a68b0b27c877') { throw 'Plug-in GUID changed.' }
foreach ($Name in @('INSTALL.cmd', 'UNINSTALL.cmd', 'Install-SmartSkin.ps1', 'Uninstall-SmartSkin.ps1', 'Installer-Common.ps1', 'Installer-Lifecycle.ps1')) {
    $Source = Get-Content -LiteralPath (Join-Path $PSScriptRoot $Name) -Raw
    if ($Source -match '(?im)^\s*(?:Start-Process\s+.*Rhino|&\s+.*Rhino\.exe|start\s+.*Rhino\.exe)') { throw "Unsafe launch/external cleanup in $Name" }
}
# Production lifecycle must stay token-neutral and must not migrate HKLM registrations.
foreach ($Name in @('INSTALL.cmd', 'UNINSTALL.cmd', 'Install-SmartSkin.ps1', 'Uninstall-SmartSkin.ps1', 'Installer-Lifecycle.ps1')) {
    $Source = Get-Content -LiteralPath (Join-Path $PSScriptRoot $Name) -Raw
    if ($Source -match '(?i)HKLM:|RegistryHive\]::LocalMachine|WindowsBuiltInRole|IsInRole|Assert-Unelevated|MachineRegistration|-Verb\s+RunAs') { throw "Retired elevation/machine-registration policy in $Name" }
}
foreach ($Name in @('MachineRegistration.ps1', 'Migrate-MachineRegistration.ps1', 'Rollback-SmartSkin.ps1', 'ROLLBACK.cmd')) { if (Test-Path -LiteralPath (Join-Path $PSScriptRoot $Name)) { throw 'Retired migration/rollback delivery file survived.' } }
$Errors = @()
Get-ChildItem -LiteralPath $PSScriptRoot -Filter '*.ps1' -Recurse | ForEach-Object {
    $Tokens = $null; $ParseErrors = $null
    $null = [Management.Automation.Language.Parser]::ParseFile($_.FullName, [ref]$Tokens, [ref]$ParseErrors)
    $Errors += @($ParseErrors)
}
if ($Errors.Count) { $Errors | ForEach-Object { Write-Host $_ }; throw 'PowerShell syntax validation failed.' }
& (Join-Path $PSScriptRoot 'Test-Toolbar.ps1') -RuiPath (Join-Path $Root 'src/SmartSkin.Rhino8/SmartSkin.Rhino8.rui') -StructureOnly:($env:OS -ne 'Windows_NT')
Write-Host 'SMARTSKIN_P08E1F5_GUARDS PASS | version/net48/GUID/toolbar/scripts=STATICALLY CHECKED | native_Rhino=NOT VERIFIED'
