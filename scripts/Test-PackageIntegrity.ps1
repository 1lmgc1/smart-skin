[CmdletBinding()]
param([Parameter(Mandatory = $true)][string]$PackageRoot)
# Portable tests execute actual metadata/hash/manifest helpers, never a Rhino runtime.
$ErrorActionPreference = 'Stop'
$PackageRoot = (Resolve-Path -LiteralPath $PackageRoot).Path
. (Join-Path $PSScriptRoot 'Installer-Common.ps1')
$TestRoot = Join-Path ([IO.Path]::GetTempPath()) ('SmartSkinPackageTest-' + [Guid]::NewGuid().ToString('N'))
function Assert-Rejected([scriptblock]$Action, [string]$Label, [string]$Expected) {
    $Rejected = $false
    try { & $Action } catch { $Rejected = $true; if ($Expected -and $_.Exception.Message -notmatch $Expected) { throw "Unexpected rejection for ${Label}: $($_.Exception.Message)" }; Write-Host "EXPECTED REJECTION | $Label | $($_.Exception.Message)" }
    if (-not $Rejected) { throw "Expected package rejection: $Label" }
}
try {
    New-Item -ItemType Directory -Path $TestRoot | Out-Null
    $ValidManifest = Assert-Package $PackageRoot
    # Windows checkout uses CRLF; validation must accept both exact line-ending forms.
    foreach ($NewLine in @("`n", "`r`n")) {
        $Entry = '#! python 3' + $NewLine + '# requirements: numpy==1.26.4, scipy==1.13.1, mpmath==1.3.0' + $NewLine
        Assert-PythonEntryPoint $Entry
        Assert-Rejected { Assert-PythonEntryPoint ($Entry.Replace('scipy==1.13.1', 'scipy==0.0.0')) } 'entrypoint-wrong-pin' 'pinned requirements'
    }
    foreach ($Case in @(@(8, 20, $false), @(8, 21, $true), @(8, 99, $true), @(9, 0, $false), @(7, 99, $false))) {
        if ((Test-CompatibleRhinoVersion $Case[0] $Case[1]) -ne $Case[2]) { throw "Rhino version boundary failure: $Case" }
    }
    $JsonPath = Join-Path $TestRoot 'atomic.json'
    Write-AtomicJson $JsonPath ([ordered]@{ state = 'initial'; integer = [long]::MaxValue })
    Write-AtomicJson $JsonPath ([ordered]@{ state = 'updated'; integer = [long]::MaxValue })
    $Value = Get-Content -LiteralPath $JsonPath -Raw | ConvertFrom-Json
    if ($Value.state -ne 'updated' -or $Value.integer -ne [long]::MaxValue) { throw 'Atomic JSON replacement lost state/data.' }
    # A postcommit logging error must not change transaction status or throw.
    $script:SmartSkinLog = $TestRoot # Add-Content cannot append to a directory.
    Write-InstallLog 'EXPECTED LOG FAILURE | nonthrowing_after_commit=True'
    $script:SmartSkinLog = $null
    $Cases = [ordered]@{
        'missing-rui' = 'Package file missing'; 'tampered-core' = 'integrity mismatch'; 'extra-file' = 'Unlisted package file'
        'wrong-version' = 'identity or compatibility'; 'wrong-assembly' = 'Assembly manifest mismatch'
        'path-traversal' = 'Unsafe or duplicate'; 'duplicate-file' = 'Unsafe or duplicate'
        'missing-uninstall' = 'Required manifest file missing'; 'bad-size' = 'integrity mismatch'
        'missing-lifecycle-helper' = 'Required manifest file missing'; 'wrong-installer-revision' = 'identity or compatibility'
        'wrong-runtime-version' = 'identity or compatibility'; 'wrong-runtime-commit' = 'Runtime/source commit identity mismatch'
    }
    if ($ValidManifest.feature_status -eq 'EXPERIMENTAL_NATIVE_CURVATURE') {
        $Cases['missing-engine'] = 'Required native curvature engine asset missing'
        $Cases['wrong-dependency'] = 'Native Python dependency contract mismatch'
    } else { Write-Host 'SMARTSKIN_PACKAGE_TEST SKIP | native_engine_contract=NOT VERIFIED in installer-only scaffold' }
    foreach ($Kind in $Cases.Keys) {
        $Bad = Join-Path $TestRoot $Kind
        New-Item -ItemType Directory -Path $Bad | Out-Null
        Get-ChildItem -LiteralPath $PackageRoot -Force | Copy-Item -Destination $Bad -Recurse
        $ManifestPath = Join-Path $Bad 'manifest.json'
        $M = Get-Content -LiteralPath $ManifestPath -Raw | ConvertFrom-Json
        switch ($Kind) {
            'missing-rui' { Remove-Item -LiteralPath (Join-Path $Bad 'net48/SmartSkin.Rhino8.rui') }
            'tampered-core' { Add-Content -LiteralPath (Join-Path $Bad 'net48/SmartSkin.Core.dll') -Value 'corruption' }
            'extra-file' { Set-Content -LiteralPath (Join-Path $Bad 'extra.dll') -Value 'unlisted' }
            'wrong-version' { $M.version = '0.0.14-p07f2' }
            'wrong-installer-revision' { $M.installer_revision = 'unverified' }
            'wrong-runtime-version' { $M.runtime_version = '0.0.16-p08e1' }
            'wrong-runtime-commit' { $M.runtime_commit = ('a' * 40) }
            'missing-lifecycle-helper' { $M.files = @($M.files | Where-Object { $_.path -ne 'Installer-Lifecycle.ps1' }); Remove-Item -LiteralPath (Join-Path $Bad 'Installer-Lifecycle.ps1') }
            'wrong-assembly' { $M.assemblies.'SmartSkin.Core'.assembly_version = '0.0.14.0' }
            'path-traversal' { $M.files[0].path = '../outside' }
            'duplicate-file' { $M.files += $M.files[0] }
            'missing-uninstall' { $M.files = @($M.files | Where-Object { $_.path -ne 'UNINSTALL.cmd' }); Remove-Item -LiteralPath (Join-Path $Bad 'UNINSTALL.cmd') }
            'bad-size' { $M.files[0].size = -1 }
            'missing-engine' {
                $M.feature_status = 'EXPERIMENTAL_NATIVE_CURVATURE'
                $M.files = @($M.files | Where-Object { $_.path -ne 'net48/Python/native_input.py' })
                $Engine = Join-Path $Bad 'net48/Python/native_input.py'
                if (Test-Path -LiteralPath $Engine) { Remove-Item -LiteralPath $Engine }
            }
            'wrong-dependency' { $M.feature_status = 'EXPERIMENTAL_NATIVE_CURVATURE'; $M.runtime.packages.scipy = '0.0.0' }
        }
        Write-AtomicJson $ManifestPath $M
        Assert-Rejected { $null = Assert-Package $Bad } $Kind $Cases[$Kind]
    }
    if ($ValidManifest.feature_status -eq 'EXPERIMENTAL_NATIVE_CURVATURE') {
        # Each new module is independently mandatory. A source-only import must
        # never make a package that omits a fan/provenance helper appear usable.
        foreach ($Asset in @('native_boundary_evidence.py', 'fan_shared_jets.py', 'fan_rational_fields.py', 'fan_geometry.py', 'lower_corner_geometry.py', 'upper_corner_geometry.py', 'upper_corner_certificate.py', 'constrained_uv.py', 'repaired_validation.py', 'native_owner_separation.py', 'atlas_separation.py')) {
            $Bad = Join-Path $TestRoot ('missing-' + $Asset)
            New-Item -ItemType Directory -Path $Bad | Out-Null
            Get-ChildItem -LiteralPath $PackageRoot -Force | Copy-Item -Destination $Bad -Recurse
            $ManifestPath = Join-Path $Bad 'manifest.json'
            $M = Get-Content -LiteralPath $ManifestPath -Raw | ConvertFrom-Json
            $Relative = 'net48/Python/' + $Asset
            $M.files = @($M.files | Where-Object { $_.path -ne $Relative })
            Remove-Item -LiteralPath (Join-Path $Bad $Relative)
            Write-AtomicJson $ManifestPath $M
            Assert-Rejected { $null = Assert-Package $Bad } ('missing-' + $Asset) 'Required native curvature engine asset missing'
        }
    }
    Write-Host 'SMARTSKIN_PACKAGE_TEST PASS | metadata/manifests/atomic_json/log_failure=VERIFIED | Windows_lifecycle/native_Rhino=NOT VERIFIED'
} finally {
    $script:SmartSkinLog = $null
    if (Test-Path -LiteralPath $TestRoot) { Remove-Item -LiteralPath $TestRoot -Recurse -Force }
}
