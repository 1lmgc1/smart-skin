# Shared by the extracted Windows package. Requires Windows PowerShell 5.1 (64-bit).
Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'
$script:SmartSkinVersion = '0.0.21-p08e1f7'
$script:SmartSkinRuntimeVersion = '0.0.21-p08e1f7'
$script:SmartSkinInstallerRevision = 'f7'
$script:SmartSkinGuid = 'b3f42f21-1f15-45e6-9bc2-a68b0b27c877'
$script:SmartSkinRegistryBase = 'HKCU:\Software\McNeel\Rhinoceros\8.0\Plug-ins'
$script:SmartSkinLog = $null

function Write-InstallLog([string]$Message) {
    $Line = '{0} | {1}' -f [DateTime]::UtcNow.ToString('o'), $Message
    Write-Host $Line
    if ($script:SmartSkinLog) {
        try { Add-Content -LiteralPath $script:SmartSkinLog -Value $Line -Encoding UTF8 }
        catch { Write-Warning "Log append failed; transaction outcome is unchanged. Log: $script:SmartSkinLog. $($_.Exception.Message)" -WarningAction Continue }
    }
}
function Get-FullPath([string]$Path) { return [IO.Path]::GetFullPath($Path).TrimEnd([char[]]'\/') }
function Test-SamePath([string]$Left, [string]$Right) {
    return [string]::Equals((Get-FullPath $Left), (Get-FullPath $Right), [StringComparison]::OrdinalIgnoreCase)
}
function Assert-NoReparsePoint([string]$Path) {
    $Cursor = Get-FullPath $Path
    while ($Cursor) {
        if (Test-Path -LiteralPath $Cursor) {
            if (((Get-Item -LiteralPath $Cursor -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
                throw "Refusing a symbolic link or junction: $Cursor"
            }
        }
        $Cursor = Split-Path -Parent $Cursor
    }
}
function Assert-ManagedChildPath([string]$Path, [string]$ManagedRoot) {
    $Full = Get-FullPath $Path
    $Prefix = (Get-FullPath $ManagedRoot) + [IO.Path]::DirectorySeparatorChar
    if (-not $Full.StartsWith($Prefix, [StringComparison]::OrdinalIgnoreCase)) { throw "Path is outside the managed root: $Full" }
    Assert-NoReparsePoint $Full
}
function Write-AtomicJson([string]$Path, $Value) {
    $Temp = $Path + '.' + [Guid]::NewGuid().ToString('N') + '.tmp'
    try {
        $Json = $Value | ConvertTo-Json -Depth 40
        [IO.File]::WriteAllText($Temp, $Json, (New-Object Text.UTF8Encoding($false)))
        if (Test-Path -LiteralPath $Path) { [IO.File]::Replace($Temp, $Path, [NullString]::Value) }
        else { [IO.File]::Move($Temp, $Path) }
    } finally { if (Test-Path -LiteralPath $Temp) { Remove-Item -LiteralPath $Temp -Force } }
}
function Test-CompatibleRhinoVersion([int]$Major, [int]$Minor) { return $Major -eq 8 -and $Minor -ge 21 }
function Assert-RhinoPrerequisites {
    $Net = Get-ItemProperty -LiteralPath 'HKLM:\SOFTWARE\Microsoft\NET Framework Setup\NDP\v4\Full' -ErrorAction SilentlyContinue
    if ($null -eq $Net -or -not $Net.PSObject.Properties['Release'] -or [int]$Net.Release -lt 528040) {
        throw 'Microsoft .NET Framework 4.8 or later is required. No Rhino runtime setting will be changed.'
    }
    $Key = 'HKLM:\SOFTWARE\McNeel\Rhinoceros\8.0\Install'
    if (-not (Test-Path -LiteralPath $Key)) { throw 'Rhino 8 installation was not found.' }
    $Values = Get-ItemProperty -LiteralPath $Key
    $Candidates = New-Object 'Collections.Generic.List[string]'
    foreach ($Name in @('Path', 'InstallPath', 'InstallDir', 'InstallFolder', 'ExePath')) {
        if ($Values.PSObject.Properties[$Name] -and $Values.$Name -is [string] -and $Values.$Name) {
            $Base = [Environment]::ExpandEnvironmentVariables([string]$Values.$Name).Trim('"')
            if ([IO.Path]::GetExtension($Base) -eq '.exe') { $Candidates.Add($Base) }
            else { $Candidates.Add((Join-Path $Base 'Rhino.exe')); $Candidates.Add((Join-Path $Base 'System\Rhino.exe')) }
        }
    }
    if ($env:ProgramFiles) { $Candidates.Add((Join-Path $env:ProgramFiles 'Rhino 8\System\Rhino.exe')) }
    foreach ($Candidate in $Candidates | Select-Object -Unique) {
        if (Test-Path -LiteralPath $Candidate -PathType Leaf) {
            $Info = [Diagnostics.FileVersionInfo]::GetVersionInfo($Candidate)
            if (Test-CompatibleRhinoVersion $Info.FileMajorPart $Info.FileMinorPart) {
                Write-InstallLog "PREREQUISITES PASS | Rhino=$($Info.FileVersion) | executable=$Candidate | runtime=unchanged"
                return
            }
        }
    }
    throw 'Rhino 8.21 or later is required; a compatible Rhino.exe version could not be verified. Update Rhino 8 before installing.'
}
function Get-AssemblyIdentity([string]$Path, [string]$ExpectedName, [string]$ExpectedVersion) {
    # AssemblyName reads metadata without executing plug-in code or loading Rhino.
    $Identity = [Reflection.AssemblyName]::GetAssemblyName($Path)
    $Info = [Diagnostics.FileVersionInfo]::GetVersionInfo($Path)
    $Numeric = ($ExpectedVersion -split '-')[0] + '.0'
    if ($Identity.Name -ne $ExpectedName -or $Identity.Version.ToString() -ne $Numeric -or $Info.FileVersion -ne $Numeric) {
        throw "Assembly name/version mismatch: $Path ($($Identity.FullName); file=$($Info.FileVersion))"
    }
    if ($Info.ProductVersion -notmatch ('^' + [regex]::Escape($ExpectedVersion) + '(\+[^\s]+)?$')) { throw "Assembly informational version mismatch: $Path ($($Info.ProductVersion))" }
    # Compiler-generated TargetFrameworkAttribute text is retained in CLR metadata.
    # This is a compatibility sanity check, not a signature or a runtime load test.
    $Framework = if ($ExpectedName -eq 'SmartSkin.Rhino8') { '.NETFramework,Version=v4.8' } else { '.NETStandard,Version=v2.0' }
    $MetadataText = [Text.Encoding]::UTF8.GetString([IO.File]::ReadAllBytes($Path))
    if (-not $MetadataText.Contains($Framework)) { throw "Expected framework marker missing from assembly: $Path ($Framework)" }
    return [ordered]@{ name = $Identity.Name; assembly_version = $Identity.Version.ToString(); file_version = $Info.FileVersion; informational_version = $Info.ProductVersion; target_framework = $Framework }
}
function Assert-PythonEntryPoint([string]$EntryPoint) {
    $RequirementsMatch = [regex]::Match($EntryPoint, '(?m)^# requirements:[ \t]*([^\r\n]+)\r?$')
    $ActualRequirements = @($RequirementsMatch.Groups[1].Value.Split(',') | ForEach-Object { $_.Trim() } | Sort-Object)
    if ($EntryPoint -notmatch '^#! python 3' -or -not $RequirementsMatch.Success -or ($ActualRequirements -join ';') -ne 'mpmath==1.3.0;numpy==1.26.4;scipy==1.13.1') {
        throw 'Native entrypoint Python version or pinned requirements directive differs from the manifest.'
    }
}

function Assert-Package([string]$Root) {
    $Root = Get-FullPath $Root
    Assert-NoReparsePoint $Root
    $ManifestPath = Join-Path $Root 'manifest.json'
    if (-not (Test-Path -LiteralPath $ManifestPath -PathType Leaf)) { throw 'Package is incomplete: manifest.json is missing. Extract the complete ZIP before running INSTALL.cmd.' }
    $Manifest = Get-Content -LiteralPath $ManifestPath -Raw | ConvertFrom-Json
    if ($Manifest.schema -ne 1 -or $Manifest.product -ne 'Smart Skin' -or $Manifest.patch -ne 'P08E1F7' -or $Manifest.feature_status -notin @('EXPERIMENTAL_NATIVE_CURVATURE', 'INSTALLER_SCAFFOLD_INCOMPLETE') -or $Manifest.version -ne $script:SmartSkinVersion -or $Manifest.runtime_version -ne $script:SmartSkinRuntimeVersion -or $Manifest.installer_revision -ne $script:SmartSkinInstallerRevision -or $Manifest.installer_commit -notmatch '^[a-f0-9]{40}$' -or $Manifest.runtime_commit -notmatch '^[a-f0-9]{40}$' -or $Manifest.plugin_guid -ne $script:SmartSkinGuid -or $Manifest.target_framework -ne 'net48' -or $Manifest.minimum_rhino -ne '8.21') { throw 'Package identity or compatibility manifest mismatch.' }
    if ($Manifest.runtime_commit -ne $Manifest.commit -or $Manifest.installer_commit -ne $Manifest.commit) { throw 'Runtime/source commit identity mismatch.' }
    $Listed = @{}
    foreach ($File in $Manifest.files) {
        $Relative = [string]$File.path
        if ($Relative -notmatch '^[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)*$' -or $Relative -match '(^|/)\.\.?(/|$)' -or $Relative -eq 'manifest.json' -or $Listed.ContainsKey($Relative)) { throw "Unsafe or duplicate manifest path: $Relative" }
        $Listed[$Relative] = $true
        $Path = Join-Path $Root ($Relative.Replace('/', [IO.Path]::DirectorySeparatorChar))
        Assert-ManagedChildPath $Path $Root
        if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { throw "Package file missing: $Relative" }
        $Item = Get-Item -LiteralPath $Path
        if ($Item.Length -ne [long]$File.size -or $File.sha256 -notmatch '^[A-Fa-f0-9]{64}$' -or (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash -ne $File.sha256) { throw "Package integrity mismatch: $Relative" }
    }
    foreach ($Item in Get-ChildItem -LiteralPath $Root -Recurse -Force) {
        if (($Item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) { throw "Package contains a symbolic link or junction: $($Item.FullName)" }
        if (-not $Item.PSIsContainer) {
            $Relative = $Item.FullName.Substring($Root.Length + 1).Replace('\', '/')
            if ($Relative -ne 'manifest.json' -and -not $Listed.ContainsKey($Relative)) { throw "Unlisted package file: $Relative" }
        }
    }
    foreach ($Name in @('net48/SmartSkin.Rhino8.rhp', 'net48/SmartSkin.Core.dll', 'net48/SmartSkin.Rhino8.rui', 'INSTALL.cmd', 'UNINSTALL.cmd', 'Install-SmartSkin.ps1', 'Uninstall-SmartSkin.ps1', 'Installer-Common.ps1', 'Installer-Lifecycle.ps1', 'Test-Toolbar.ps1', 'INSTALL_CURVATURE_RU.md', 'P08E1F2_PIPELINE_REPAIR.md', 'P08E1F3_COMPOUND_EDGE_REPAIR.md', 'P08E1F3_NATIVE_OWNER_SCREEN.md', 'P08E1F4_NATIVE_FRAME_REPAIR.md', 'P08E1F5_PREVIEW_INTERACTION.md', 'P08E1F6_NATIVE_CACHE_LATENCY.md', 'P08E1F7_SLIDER_RECOVERY.md', 'build-info.txt')) {
        if (-not $Listed.ContainsKey($Name)) { throw "Required manifest file missing: $Name" }
    }
    if ($Manifest.feature_status -eq 'EXPERIMENTAL_NATIVE_CURVATURE') {
        if (-not $Listed.ContainsKey('P08E1_CURVATURE_CONTROL.md')) { throw 'Current full-cycle feature guide is missing.' }
        foreach ($Asset in @('smart_skin.py', 'native_input.py', 'native_family.py', 'skin_kernel.py', 'preview.py', 'native_boundary_evidence.py', 'fan_shared_jets.py', 'fan_rational_fields.py', 'fan_geometry.py', 'lower_corner_geometry.py', 'upper_corner_geometry.py', 'upper_corner_certificate.py', 'constrained_uv.py', 'repaired_validation.py', 'native_owner_separation.py', 'atlas_separation.py')) {
            if (-not $Listed.ContainsKey('net48/Python/' + $Asset)) { throw "Required native curvature engine asset missing: $Asset" }
        }
        if ($Manifest.runtime.rhino_cpython_min -ne '3.9' -or $Manifest.runtime.packages.numpy -ne '1.26.4' -or $Manifest.runtime.packages.scipy -ne '1.13.1' -or $Manifest.runtime.packages.mpmath -ne '1.3.0') { throw 'Native Python dependency contract mismatch.' }
        $EntryPoint = Get-Content -LiteralPath (Join-Path $Root 'net48/Python/smart_skin.py') -Raw
        Assert-PythonEntryPoint $EntryPoint
    }
    foreach ($Spec in @(@('SmartSkin.Rhino8.rhp', 'SmartSkin.Rhino8'), @('SmartSkin.Core.dll', 'SmartSkin.Core'))) {
        $Actual = Get-AssemblyIdentity (Join-Path $Root ('net48/' + $Spec[0])) $Spec[1] $script:SmartSkinRuntimeVersion
        if ($Actual.informational_version -ne ($script:SmartSkinRuntimeVersion + '+' + $Manifest.runtime_commit)) { throw 'Runtime commit differs from assembly metadata.' }
        $Declared = $Manifest.assemblies.PSObject.Properties[$Spec[1]]
        if (-not $Declared) { throw "Missing assembly manifest identity: $($Spec[1])" }
        foreach ($Field in @('name', 'assembly_version', 'file_version', 'informational_version', 'target_framework')) {
            if ($Actual[$Field] -ne $Declared.Value.$Field) { throw "Assembly manifest mismatch: $($Spec[1]) / $Field" }
        }
    }
    & (Join-Path $Root 'Test-Toolbar.ps1') -RuiPath (Join-Path $Root 'net48/SmartSkin.Rhino8.rui') -StructureOnly:($env:OS -ne 'Windows_NT')
    return $Manifest
}
function Get-PluginRegistryKeys([string]$Base) {
    if (Test-Path -LiteralPath $Base) {
        foreach ($Key in Get-ChildItem -LiteralPath $Base) {
            try {
                if ($Key.PSChildName.Trim([char[]]'{}') -ieq $script:SmartSkinGuid) {
                    # Never retain native key handles across delete/recreate activation.
                    [pscustomobject]@{ PSChildName = $Key.PSChildName; PSPath = $Key.PSPath; Name = $Key.Name }
                }
            } finally { $Key.Close() }
        }
    }
}
function Open-WritableRegistryKey([string]$Path) {
    if (-not $Path.StartsWith('HKCU:\', [StringComparison]::OrdinalIgnoreCase)) { throw 'Writable registry access is restricted to HKCU.' }
    $Key = [Microsoft.Win32.Registry]::CurrentUser.OpenSubKey($Path.Substring(6), $true)
    if ($null -eq $Key) { throw "Could not open writable registry snapshot key: $Path" }
    return $Key
}
function Assert-NoForeignRegistration([string]$Base) {
    if (-not (Test-Path -LiteralPath $Base)) { return }
    foreach ($Key in Get-ChildItem -LiteralPath $Base) {
        $KeyName = $Key.Name; $KeyPath = $Key.PSPath; $ChildName = $Key.PSChildName
        $Key.Close()
        if ($ChildName.Trim([char[]]'{}') -ieq $script:SmartSkinGuid) { continue }
        $Properties = Get-ItemProperty -LiteralPath $KeyPath
        $Name = if ($Properties.PSObject.Properties['Name']) { [string]$Properties.Name } else { '' }
        $File = if ($Properties.PSObject.Properties['FileName']) { [string]$Properties.FileName } else { '' }
        if ($Name -eq 'Smart Skin' -or ($File -and [IO.Path]::GetFileName($File) -ieq 'SmartSkin.Rhino8.rhp')) {
            throw "Conflicting Smart Skin registration has an unexpected GUID: $KeyName. Nothing was changed. Inspect it in Rhino PlugInManager; do not delete old files."
        }
    }
}
function Get-RegistrySnapshot([string]$Base) {
    $Entries = New-Object 'Collections.Generic.List[object]'
    foreach ($RootKey in @(Get-PluginRegistryKeys $Base)) {
        foreach ($Key in @((Get-Item -LiteralPath $RootKey.PSPath)) + @(Get-ChildItem -LiteralPath $RootKey.PSPath -Recurse)) {
            $Values = New-Object 'Collections.Generic.List[object]'
            foreach ($Name in $Key.GetValueNames()) {
                $Kind = $Key.GetValueKind($Name).ToString()
                $Value = $Key.GetValue($Name, $null, [Microsoft.Win32.RegistryValueOptions]::DoNotExpandEnvironmentNames)
                $Data = switch ($Kind) {
                    { $_ -in @('Binary', 'None') } { [Convert]::ToBase64String([byte[]]$Value); break }
                    'DWord' { ([int]$Value).ToString([Globalization.CultureInfo]::InvariantCulture); break }
                    'QWord' { ([long]$Value).ToString([Globalization.CultureInfo]::InvariantCulture); break }
                    'MultiString' { ,([string[]]$Value); break }
                    default { [string]$Value }
                }
                $Values.Add([ordered]@{ name = $Name; kind = $Kind; data = $Data })
            }
            $Suffix = $Key.Name.Substring($RootKey.Name.Length)
            $Entries.Add([ordered]@{ path = $RootKey.PSChildName + $Suffix; values = @($Values.ToArray()) })
            $Key.Close()
        }
    }
    return ,($Entries.ToArray())
}
function Restore-RegistrySnapshot([string]$Base, $Snapshot) {
    # Validate the complete snapshot before modifying any key.
    foreach ($Entry in @($Snapshot)) {
        $Parts = ([string]$Entry.path).Split('\')
        if ($Parts[0].Trim([char[]]'{}') -ine $script:SmartSkinGuid -or @($Parts | Where-Object { $_ -in @('', '.', '..') }).Count -gt 0) { throw 'Unsafe registry snapshot path.' }
        foreach ($Value in @($Entry.values)) {
            if ($Value.kind -notin @('String', 'ExpandString', 'MultiString', 'Binary', 'None', 'DWord', 'QWord')) { throw 'Unsupported registry snapshot value kind.' }
        }
    }
    foreach ($Key in @(Get-PluginRegistryKeys $Base)) { Remove-Item -LiteralPath $Key.PSPath -Recurse -Force }
    foreach ($Entry in @($Snapshot)) {
        $Path = Join-Path $Base $Entry.path
        New-Item -Path $Path -Force | Out-Null
        $Key = Open-WritableRegistryKey $Path
        try {
            foreach ($Value in @($Entry.values)) {
                $Data = switch ([string]$Value.kind) {
                    { $_ -in @('Binary', 'None') } { ,([Convert]::FromBase64String([string]$Value.data)); break }
                    'DWord' { [int]::Parse([string]$Value.data, [Globalization.CultureInfo]::InvariantCulture); break }
                    'QWord' { [long]::Parse([string]$Value.data, [Globalization.CultureInfo]::InvariantCulture); break }
                    'MultiString' { ,([string[]]@($Value.data)); break }
                    default { [string]$Value.data }
                }
                $Key.SetValue([string]$Value.name, $Data, ([Microsoft.Win32.RegistryValueKind][Enum]::Parse([Microsoft.Win32.RegistryValueKind], [string]$Value.kind)))
            }
        } finally { $Key.Close() }
    }
}
function Invoke-TestFailure($Context, [string]$Requested, [string]$Point) {
    if ($Requested -and -not $Context.Test) { throw 'Failure injection is allowed only in an isolated test root.' }
    if ($Requested -eq $Point) { throw "Injected isolated lifecycle failure: $Point" }
}

function Get-SnapshotFilePath($Value) {
    if ($Value.kind -eq 'ExpandString') { return [Environment]::ExpandEnvironmentVariables([string]$Value.data) }
    return [string]$Value.data
}
