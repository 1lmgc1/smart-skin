[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Push-Location $Root
try {
    # Source integrity checks, NOT a Rhino execution or a UI-rendering test.
    $Preserved = @(
        'src/SmartSkin.Core',
        'src/SmartSkin.Rhino8/BoundaryMatchVerifier.cs',
        'src/SmartSkin.Rhino8/RhinoCandidateBuilder.cs',
        'src/SmartSkin.Rhino8/CandidateBuildSettings.cs',
        'src/SmartSkin.Rhino8/SmartSkinLivePreviewSession.cs',
        'src/SmartSkin.Rhino8/SmartSurfaceBuildCommand.cs',
        'src/SmartSkin.Rhino8/SmartSkin.Rhino8.rui',
        'src/SmartSkin.Rhino8/SmartSkin.Rhino8.csproj'
    )
    & git diff --exit-code b0581d2f627b323ec4f89fee7df0f1171ce18594 HEAD -- @Preserved
    if ($LASTEXITCODE -ne 0) { throw 'P07F2 changed a preserved production geometry, runtime, commit or safety path.' }
    Write-Host 'SMARTSKIN_P07F2_SCOPE PASS | check=production_paths_unchanged | evidence=STATIC_ONLY'

    $Tests = Get-Content 'src/SmartSkin.Rhino8/BoundaryVerifierSelfTests.cs' -Raw
    if ([regex]::Matches($Tests, 'Test\("').Count -ne 8) { throw 'Expected all eight native test cases to remain.' }
    $Finish = $Tests.IndexOf('cap.SetTolerancesBoxesAndFlags(')
    $Compact = $Tests.IndexOf('cap.Compact();')
    $Validate = $Tests.IndexOf('RequireValidFixture(cap, "after_split_finalization");')
    $Measure = $Tests.IndexOf('var metrics = CheckAgainst(cap, target);')
    if ($Finish -lt 0 -or $Compact -le $Finish -or $Validate -le $Compact -or $Measure -le $Validate) {
        throw 'Fixture must finish new vertex tolerances, compact and check validity before measuring G2.'
    }
    if ($Tests -notmatch '(?s)bLazy: true,\s*bSetVertexTolerances: true,\s*bSetEdgeTolerances: false,\s*bSetTrimTolerances: false,\s*bSetTrimIsoFlags: false,\s*bSetTrimTypeFlags: false,\s*bSetLoopTypeFlags: false,\s*bSetTrimBoxes: false') {
        throw 'Unexpected fixture finalization scope.'
    }
    Write-Host 'SMARTSKIN_P07F2_SCOPE PASS | check=fixture_finalization_and_eight_cases | evidence=STATIC_ONLY'

    $Form = Get-Content 'src/SmartSkin.Rhino8/SmartSkinPreviewForm.cs' -Raw
    foreach ($Field in @('_continuity', '_curvatureTolerance', '_isoDirection')) {
        if ($Form -notmatch ('matchLayout\.AddRow\(SettingRow\("[^"]+", ' + $Field + '\)\);')) {
            throw "Field lacks an independent layout row: $Field"
        }
    }
    if ($Form -notmatch 'Width = 430') { throw 'Average note has no bounded wrapping width.' }
    Write-Host 'SMARTSKIN_P07F2_SCOPE PASS | check=independent_field_rows | evidence=STATIC_ONLY | rendering=NOT_RUN'

    $Version = (Get-Content 'VERSION' -Raw).Trim()
    [xml]$Props = Get-Content 'Directory.Build.props' -Raw
    $PropsVersion = $Props.Project.PropertyGroup.VersionPrefix + '-' + $Props.Project.PropertyGroup.VersionSuffix
    if ($Version -ne '0.0.14-p07f2' -or $PropsVersion -ne $Version) { throw 'Version/assembly identity mismatch.' }
    foreach ($Script in @('scripts/Install-SmartSkin.ps1', 'scripts/Package-Artifact.ps1')) {
        $Source = Get-Content $Script -Raw
        if ($Source -notmatch ('\$Version = "' + [regex]::Escape($Version) + '"')) {
            throw "Installer/package identity mismatch: $Script"
        }
    }
    Write-Host 'SMARTSKIN_P07F2_SCOPE PASS | check=version_identity | evidence=STATIC_ONLY'
}
finally { Pop-Location }
