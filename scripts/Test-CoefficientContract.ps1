[CmdletBinding()]
param([string]$AssemblyPath)
$ErrorActionPreference = 'Stop'
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
if (-not $AssemblyPath) {
    [xml]$Project = Get-Content -LiteralPath (Join-Path $RepoRoot 'src/SmartSkin.Rhino8/SmartSkin.Rhino8.csproj') -Raw
    $Reference = @($Project.Project.ItemGroup.PackageReference | Where-Object { $_.Include -eq 'RhinoCommon' })
    if ($Reference.Count -ne 1) { throw 'Expected exactly one official RhinoCommon package reference.' }
    $AssetsPath = Join-Path $RepoRoot 'src/SmartSkin.Rhino8/obj/project.assets.json'
    if (-not (Test-Path -LiteralPath $AssetsPath)) { throw 'Restore the project before testing the managed coefficient contract.' }
    $Assets = Get-Content -LiteralPath $AssetsPath -Raw | ConvertFrom-Json
    $Candidates = @($Assets.packageFolders.PSObject.Properties.Name | ForEach-Object {
        Join-Path $_ ('rhinocommon/' + $Reference[0].Version + '/lib/net48/RhinoCommon.dll')
    } | Where-Object { Test-Path -LiteralPath $_ })
    if ($Candidates.Count -ne 1) { throw 'The exact restored official net48 RhinoCommon assembly was not uniquely resolved.' }
    $AssemblyPath = $Candidates[0]
}
# Pure managed constructors/properties only. No native Rhino API, host loading,
# document, plug-in installation or Rhino geometry-kernel call is executed.
$Assembly = [Reflection.Assembly]::LoadFrom((Resolve-Path -LiteralPath $AssemblyPath).Path)
$InputValues = @(0.7, 2.1, -5.0, 0.3)
$Point = [Rhino.Geometry.ControlPoint]::new($InputValues[0], $InputValues[1], $InputValues[2], $InputValues[3])
$ActualValues = @($Point.X, $Point.Y, $Point.Z, $Point.Weight)
for ($Index = 0; $Index -lt 4; $Index++) {
    if ([BitConverter]::DoubleToInt64Bits($ActualValues[$Index]) -ne [BitConverter]::DoubleToInt64Bits($InputValues[$Index])) {
        throw 'The homogeneous managed constructor changed a binary64 coefficient.'
    }
}
$Euclidean = [Rhino.Geometry.ControlPoint]::new([Rhino.Geometry.Point3d]::new(0.7 / 0.3, 2.1 / 0.3, -5.0 / 0.3), 0.3)
if ([BitConverter]::DoubleToInt64Bits($Euclidean.X) -eq [BitConverter]::DoubleToInt64Bits(0.7)) {
    throw 'The rational round-trip regression no longer distinguishes the two construction paths; review the package semantics.'
}
Write-Host ('SMARTSKIN_COEFFICIENT_CONTRACT PASS | managed_package=' + $Assembly.GetName().Version + ' | homogeneous_bits=VERIFIED | native_set_get=NOT VERIFIED')
