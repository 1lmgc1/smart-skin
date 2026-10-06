[CmdletBinding()]
param([Parameter(Mandatory = $true)][string]$PackageRoot, [string]$LogPath = '')
Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'
if ($env:OS -ne 'Windows_NT') { throw 'This harness requires actual Windows registry, tokens, CMD and Windows PowerShell 5.1.' }
if ($PSVersionTable.PSVersion.Major -ne 5 -or $PSVersionTable.PSVersion.Minor -ne 1 -or -not [Environment]::Is64BitProcess) { throw 'Run this harness with 64-bit Windows PowerShell 5.1.' }
$PackageRoot = (Resolve-Path -LiteralPath $PackageRoot).Path
$SourceScripts = $PSScriptRoot
$HelperRoot = Join-Path $PSScriptRoot 'test-helpers'
Add-Type -Path (Join-Path $HelperRoot 'InstallerTokenHarness.cs')
$ParentToken = [SmartSkin.InstallerTests.TokenProcess]::CurrentFacts()
if (-not $ParentToken.IsAdministrator -or -not $ParentToken.IsElevated) { throw 'The CI harness requires an elevated Windows runner to exercise both full and restricted tokens; tests are not skipped.' }
$PluginGuid = 'b3f42f21-1f15-45e6-9bc2-a68b0b27c877'
$TestId = [Guid]::NewGuid().ToString('N')
$TempRoot = if ($env:RUNNER_TEMP) { $env:RUNNER_TEMP } else { [IO.Path]::GetTempPath() }
$TestRoot = Join-Path $TempRoot ("SmartSkinInstallerTest-$TestId")
$InstallRoot = Join-Path $TestRoot 'install'
# Build the non-ASCII path without relying on this source file's encoding.
$SpecialName = 'runtime package & bang! (caf' + [char]0x00E9 + ')'
$RuntimePackage = Join-Path $TestRoot $SpecialName
$OldDirectory = Join-Path $TestRoot ('legacy package & bang! (caf' + [char]0x00E9 + ')\net48')
$RegistryTestRoot = "HKCU:\Software\SmartSkinInstallerTests\$TestId"
$RegistryBase = Join-Path $RegistryTestRoot 'Plug-ins'
$MachineTestRoot = "HKLM:\Software\SmartSkinInstallerTests\$TestId"
$MachineRegistryBase = Join-Path $MachineTestRoot 'Plug-ins'
$MachineLiveBases = @('HKLM:\SOFTWARE\McNeel\Rhinoceros\8.0\Plug-ins', 'HKLM:\SOFTWARE\WOW6432Node\McNeel\Rhinoceros\8.0\Plug-ins')
$RhinoEventId = "SmartSkinInstallerRhinoStart-$TestId"
$TranscriptStarted = $false
$EventRegistered = $false
$InvocationCount = 0
$PowerShellExe = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
$SavedPreviousEnv = $env:SMARTSKIN_TEST_PREVIOUS
function Assert-True([bool]$Value, [string]$Message) { if (-not $Value) { throw $Message } }
function Test-SamePath([string]$Left, [string]$Right) { return [string]::Equals([IO.Path]::GetFullPath($Left).TrimEnd('\'), [IO.Path]::GetFullPath($Right).TrimEnd('\'), [StringComparison]::OrdinalIgnoreCase) }
function Get-RegistrySnapshotJson([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path)) { return '{"exists":false}' }
    $Root = Get-Item -LiteralPath $Path
    $RootName = $Root.Name
    $Rows = @()
    foreach ($Key in @($Root) + @(Get-ChildItem -LiteralPath $Path -Recurse | Sort-Object Name)) {
        try {
        $Values = @()
        foreach ($Name in @($Key.GetValueNames() | Sort-Object)) {
            $Kind = $Key.GetValueKind($Name).ToString()
            $Value = $Key.GetValue($Name, $null, [Microsoft.Win32.RegistryValueOptions]::DoNotExpandEnvironmentNames)
            if ($Value -is [byte[]]) { $Value = [Convert]::ToBase64String($Value) }
            elseif ($Kind -in @('DWord', 'QWord')) { $Value = [string]$Value }
            $Values += [ordered]@{ name = $Name; kind = $Kind; value = $Value }
        }
        $Rows += [ordered]@{ path = $Key.Name.Substring($RootName.Length); values = $Values }
        } finally { $Key.Close() }
    }
    return ([ordered]@{ exists = $true; keys = $Rows } | ConvertTo-Json -Depth 40 -Compress)
}
function Get-FileSnapshotJson([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path)) { return '{"exists":false}' }
    $Rows = @(Get-ChildItem -LiteralPath $Path -Recurse -File | Sort-Object FullName | ForEach-Object {
        [ordered]@{ path = $_.FullName.Substring($Path.Length); sha256 = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash }
    })
    return ([ordered]@{ exists = $true; files = $Rows } | ConvertTo-Json -Depth 12 -Compress)
}
function Get-OwnKeys {
    return @(Get-ChildItem -LiteralPath $RegistryBase -ErrorAction SilentlyContinue | ForEach-Object {
        try {
            if ($_.PSChildName.Trim([char[]]'{}') -ieq $PluginGuid) { [pscustomobject]@{ PSChildName = $_.PSChildName; FileName = $_.GetValue('FileName') } }
        } finally { $_.Close() }
    })
}
function Assert-NoRhinoLaunch {
    $Events = @(Get-Event -SourceIdentifier $RhinoEventId -ErrorAction SilentlyContinue)
    Assert-True ($Events.Count -eq 0) 'An installer entry launched Rhino.exe.'
    Assert-True (@(Get-Process -Name Rhino -ErrorAction SilentlyContinue).Count -eq 0) 'Rhino appeared while the lifecycle harness was running.'
}
function Assert-MachineUnchanged {
    Assert-True ((Get-RegistrySnapshotJson $MachineTestRoot) -ceq $script:MachineFixtureBefore) 'Isolated pre-existing HKLM fixture changed.'
    foreach ($Base in $MachineLiveBases) { Assert-True ((Get-RegistrySnapshotJson $Base) -ceq $script:MachineLiveBefore[$Base]) "Actual Rhino HKLM registration changed: $Base" }
}
function Quote-Argument([string]$Value) {
    if ($Value.Contains('"') -or $Value.Contains("`r") -or $Value.Contains("`n") -or $Value.Contains('%')) { throw 'Unsafe test argument.' }
    return '"' + $Value + '"'
}
function Invoke-Entry([string]$Launcher, [bool]$Restricted, [string]$Root = $RuntimePackage, [string]$FailAt = '', [bool]$ExpectSuccess = $true, [string]$ExpectedError = '') {
    $script:InvocationCount++
    $Label = if ($Restricted) { 'same-user-restricted-nonadmin' } else { 'same-user-elevated' }
    $Arguments = '-InstallRoot ' + (Quote-Argument $InstallRoot) + ' -RegistryBase ' + (Quote-Argument $RegistryBase) + ' -AllowTestInstallRoot'
    if ($Launcher -eq 'INSTALL') { $Arguments += ' -SkipRhinoInstalledCheck' }
    if ($FailAt) { $Arguments += ' -TestFailAt ' + (Quote-Argument $FailAt) }
    $Stem = Join-Path $TestRoot ('entry-' + $script:InvocationCount.ToString('D3'))
    $DescriptorPath = $Stem + '.json'
    $ResultPath = $Stem + '.result.json'
    [ordered]@{
        expected_sid = $ParentToken.UserSid; restricted = $Restricted; package_root = $Root; launcher = $Launcher;
        launcher_sha256 = (Get-FileHash -LiteralPath (Join-Path $Root ($Launcher + '.cmd')) -Algorithm SHA256).Hash;
        arguments = $Arguments; result_path = $ResultPath
    } | ConvertTo-Json | Set-Content -LiteralPath $DescriptorPath -Encoding UTF8
    $ChildArgs = '-NoLogo -NoProfile -ExecutionPolicy Bypass -File ' + (Quote-Argument (Join-Path $HelperRoot 'Invoke-InstallerEntry.ps1')) + ' -DescriptorPath ' + (Quote-Argument $DescriptorPath)
    $ChildExit = [SmartSkin.InstallerTests.TokenProcess]::Run($PowerShellExe, $ChildArgs, $TestRoot, $Restricted, 120)
    Assert-True (Test-Path -LiteralPath $ResultPath) "No actual entry/token result: $Label $Launcher (child exit $ChildExit)."
    $Result = Get-Content -LiteralPath $ResultPath -Raw | ConvertFrom-Json
    Assert-True ($ChildExit -eq 0 -and $Result.completed) "Entry observer failed rather than exercising production: $($Result.error)"
    Write-Host ("SMARTSKIN_ENTRY | mode={0} | launcher={1} | sid={2} | admin={3} | elevated={4} | restricting_sid_list={5} | admin_deny_only={6} | integrity={7} | exit={8}" -f $Label, $Launcher, $Result.token.UserSid, $Result.token.IsAdministrator, $Result.token.IsElevated, $Result.token.HasRestrictingSids, $Result.token.AdministratorsSidDenyOnly, $Result.token.IntegrityRid, $Result.launcher_exit_code)
    Write-Host $Result.output
    if ($ExpectSuccess) {
        Assert-True ($Result.launcher_exit_code -eq 0) "$Label $Launcher unexpectedly failed."
        $Marker = if ($Launcher -eq 'INSTALL') { 'SMARTSKIN_INSTALL PASS' } else { 'SMARTSKIN_UNINSTALL PASS' }
        Assert-True ($Result.output.Contains($Marker)) "Genuine production success marker absent: $Marker"
    } else {
        Assert-True ($Result.launcher_exit_code -ne 0) "$Label $Launcher did not propagate the genuine production failure exit code."
        if ($ExpectedError) { Assert-True ($Result.output -match $ExpectedError) "Wrong failure reason; expected $ExpectedError" }
    }
    Assert-NoRhinoLaunch
    Assert-MachineUnchanged
    if (Test-Path -LiteralPath $InstallRoot) { Assert-True (@(Get-ChildItem -LiteralPath $InstallRoot -Force | Where-Object { $_.Name -like '.staging-*' -or $_.Name -like '.previous-*' }).Count -eq 0) 'Lifecycle left temporary recovery directories after success or completed rollback.' }
    return $Result
}
function Reset-UserFixture {
    foreach ($Path in @($InstallRoot, $OldDirectory, $RegistryTestRoot)) { if (Test-Path -LiteralPath $Path) { Remove-Item -LiteralPath $Path -Recurse -Force } }
    New-Item -ItemType Directory -Path $OldDirectory -Force | Out-Null
    Get-ChildItem -LiteralPath (Join-Path $RuntimePackage 'net48') -Force | Copy-Item -Destination $OldDirectory -Recurse
    Set-Content -LiteralPath (Join-Path $OldDirectory 'keep-user-file.txt') -Value 'must survive' -Encoding ASCII
    Set-Content -LiteralPath (Join-Path $OldDirectory 'keep-other-toolbar.rui') -Value 'unrelated UI' -Encoding ASCII
    New-Item -ItemType Directory -Path (Join-Path $OldDirectory 'Python') -Force | Out-Null
    Set-Content -LiteralPath (Join-Path $OldDirectory 'Python\keep-user-module.py') -Value '# must survive' -Encoding ASCII
    $env:SMARTSKIN_TEST_PREVIOUS = $OldDirectory
    foreach ($Leaf in @($PluginGuid, ('{' + $PluginGuid.ToUpperInvariant() + '}'))) {
        $Path = Join-Path $RegistryBase $Leaf
        New-Item -Path $Path -Force | Out-Null
        New-ItemProperty -LiteralPath $Path -Name Name -PropertyType String -Value 'Smart Skin' -Force | Out-Null
        New-ItemProperty -LiteralPath $Path -Name FileName -PropertyType ExpandString -Value '%SMARTSKIN_TEST_PREVIOUS%\SmartSkin.Rhino8.rhp' -Force | Out-Null
        $NestedPath = Join-Path $Path 'Settings\Nested'
        $Nested = [Microsoft.Win32.Registry]::CurrentUser.CreateSubKey($NestedPath.Substring(6))
        $Nested.SetValue('', 'default value', [Microsoft.Win32.RegistryValueKind]::String)
        $Nested.SetValue('FileName', 'C:\User\notes.txt', [Microsoft.Win32.RegistryValueKind]::String)
        $Nested.SetValue('Expand', '%TEMP%\verbatim', [Microsoft.Win32.RegistryValueKind]::ExpandString)
        $Nested.SetValue('Multi', [string[]]@('one', 'two'), [Microsoft.Win32.RegistryValueKind]::MultiString)
        $Nested.SetValue('Bytes', [byte[]]@(0, 128, 255), [Microsoft.Win32.RegistryValueKind]::Binary)
        $Nested.SetValue('Number', [int]-1, [Microsoft.Win32.RegistryValueKind]::DWord)
        $Nested.SetValue('Long', [long]::MaxValue, [Microsoft.Win32.RegistryValueKind]::QWord)
        $Nested.Close()
    }
    $OtherKey = Join-Path $RegistryBase 'f8de6453-85f8-44ba-b72d-b94162062749'
    New-Item -Path $OtherKey -Force | Out-Null
    New-ItemProperty -LiteralPath $OtherKey -Name Name -Value 'Unrelated plug-in' -PropertyType String | Out-Null
    $UiKey = Join-Path $RegistryTestRoot 'UnrelatedToolbarSettings'
    New-Item -Path $UiKey -Force | Out-Null
    New-ItemProperty -LiteralPath $UiKey -Name Keep -Value 'layout untouched' -PropertyType String | Out-Null
    $script:OtherRegistryBefore = Get-RegistrySnapshotJson $OtherKey
    $script:UiBefore = Get-RegistrySnapshotJson $UiKey
    $script:CanonicalSettingsBefore = Get-RegistrySnapshotJson (Join-Path $RegistryBase ($PluginGuid + '\Settings'))
}
function Assert-UnrelatedPreserved {
    Assert-True ((Get-RegistrySnapshotJson (Join-Path $RegistryBase 'f8de6453-85f8-44ba-b72d-b94162062749')) -ceq $script:OtherRegistryBefore) 'Unrelated plug-in registration changed.'
    Assert-True ((Get-RegistrySnapshotJson (Join-Path $RegistryTestRoot 'UnrelatedToolbarSettings')) -ceq $script:UiBefore) 'Unrelated toolbar settings changed.'
    foreach ($Fixture in @(@('keep-user-file.txt', 'must survive'), @('keep-other-toolbar.rui', 'unrelated UI'), @('Python\keep-user-module.py', '# must survive'))) {
        $Path = Join-Path $OldDirectory $Fixture[0]
        Assert-True ((Test-Path -LiteralPath $Path) -and (Get-Content -LiteralPath $Path -Raw).Trim() -ceq $Fixture[1]) "Unrelated legacy file changed: $($Fixture[0])"
    }
}
function Assert-Installed {
    $Current = Join-Path $InstallRoot 'current'
    Assert-True (Test-Path -LiteralPath $Current -PathType Container) 'Physical current directory is missing.'
    Assert-True (((Get-Item -LiteralPath $Current -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) -eq 0) 'current must be a physical directory, not a junction.'
    $Own = @(Get-OwnKeys)
    Assert-True ($Own.Count -eq 1 -and $Own[0].PSChildName -eq $PluginGuid) 'Own GUID registration was not normalized to one canonical HKCU key.'
    $ExpectedRhp = Join-Path $Current 'SmartSkin.Rhino8.rhp'
    Assert-True (Test-SamePath ([string]$Own[0].FileName) $ExpectedRhp) 'HKCU FileName does not point to the physical current payload.'
    $NetRoot = Join-Path $RuntimePackage 'net48'
    foreach ($File in Get-ChildItem -LiteralPath $NetRoot -Recurse -File) {
        $Relative = $File.FullName.Substring($NetRoot.Length + 1)
        $Installed = Join-Path $Current $Relative
        Assert-True (Test-Path -LiteralPath $Installed -PathType Leaf) "Missing installed runtime asset: $Relative"
        Assert-True ((Get-FileHash -LiteralPath $Installed -Algorithm SHA256).Hash -eq (Get-FileHash -LiteralPath $File.FullName -Algorithm SHA256).Hash) "Wrong installed runtime asset bytes: $Relative"
    }
    Assert-True ((Get-RegistrySnapshotJson (Join-Path $RegistryBase ($PluginGuid + '\Settings'))) -ceq $script:CanonicalSettingsBefore) 'Canonical typed custom settings did not survive installation/update.'
    Assert-UnrelatedPreserved
}
try {
    if ($LogPath) {
        $Parent = Split-Path -Parent $LogPath
        if ($Parent) { New-Item -ItemType Directory -Path $Parent -Force | Out-Null }
        Start-Transcript -LiteralPath $LogPath -Force | Out-Null
        $TranscriptStarted = $true
    }
    New-Item -ItemType Directory -Path $TestRoot -Force | Out-Null
    # Grant only this temporary fixture to the existing caller SID. Hosted-runner
    # temp parents can otherwise grant writes through Administrators alone.
    $FixtureAcl = Get-Acl -LiteralPath $TestRoot
    $FixtureSid = New-Object Security.Principal.SecurityIdentifier($ParentToken.UserSid)
    $FixtureRule = New-Object Security.AccessControl.FileSystemAccessRule($FixtureSid, 'FullControl', 'ContainerInherit,ObjectInherit', 'None', 'Allow')
    $FixtureAcl.AddAccessRule($FixtureRule)
    Set-Acl -LiteralPath $TestRoot -AclObject $FixtureAcl
    New-Item -ItemType Directory -Path $RuntimePackage -Force | Out-Null
    Get-ChildItem -LiteralPath $PackageRoot -Force | Copy-Item -Destination $RuntimePackage -Recurse
    # The package is byte-for-byte copied, including the actual CMD/PS scripts and
    # manifest. No launcher stub or replacement installer is introduced anywhere.
    Assert-True ((Get-FileSnapshotJson $PackageRoot) -ceq (Get-FileSnapshotJson $RuntimePackage)) 'Runtime package copy changed bytes or source layout.'
    $PackageBefore = Get-FileSnapshotJson $RuntimePackage
    $MachineKey = Join-Path $MachineRegistryBase ('{' + $PluginGuid.ToUpperInvariant() + '}')
    New-Item -Path $MachineKey -Force | Out-Null
    New-ItemProperty -LiteralPath $MachineKey -Name Name -Value 'Smart Skin legacy machine fixture' -PropertyType String | Out-Null
    New-ItemProperty -LiteralPath $MachineKey -Name FileName -Value (Join-Path $OldDirectory 'SmartSkin.Rhino8.rhp') -PropertyType String | Out-Null
    $script:MachineFixtureBefore = Get-RegistrySnapshotJson $MachineTestRoot
    $script:MachineLiveBefore = @{}
    foreach ($Base in $MachineLiveBases) { $script:MachineLiveBefore[$Base] = Get-RegistrySnapshotJson $Base }
    Assert-True (@(Get-Process -Name Rhino -ErrorAction SilentlyContinue).Count -eq 0) 'Close Rhino before running isolated lifecycle tests.'
    Register-WmiEvent -Query "SELECT * FROM Win32_ProcessStartTrace WHERE ProcessName = 'Rhino.exe'" -SourceIdentifier $RhinoEventId | Out-Null
    $EventRegistered = $true
    foreach ($Restricted in @($false, $true)) {
        $Mode = if ($Restricted) { 'restricted-nonadmin' } else { 'elevated-same-user' }
        Write-Host "SMARTSKIN_INSTALLER_TEST PHASE | $Mode | genuine-source-layout-fast-fail"
        Reset-UserFixture
        $OriginalRegistry = Get-RegistrySnapshotJson $RegistryTestRoot
        $OriginalLegacy = Get-FileSnapshotJson $OldDirectory
        $Null = Invoke-Entry INSTALL $Restricted -Root $SourceScripts -ExpectSuccess $false -ExpectedError 'SOURCE_LAYOUT'
        Assert-True ((Get-RegistrySnapshotJson $RegistryTestRoot) -ceq $OriginalRegistry) 'Source/scripts entry changed user registration.'
        Assert-True ((Get-FileSnapshotJson $OldDirectory) -ceq $OriginalLegacy) 'Source/scripts entry changed legacy files.'
        Assert-True (-not (Test-Path -LiteralPath $InstallRoot)) 'Source/scripts entry created install state before layout rejection.'
        Write-Host "SMARTSKIN_INSTALLER_TEST PHASE | $Mode | real-package-integrity-rejection"
        foreach ($Kind in @('missing-rui', 'changed-core', 'extra-file', 'wrong-version')) {
            $Bad = Join-Path $TestRoot ('bad package & bang! (' + $Mode + '-' + $Kind + ')')
            New-Item -ItemType Directory -Path $Bad | Out-Null
            Get-ChildItem -LiteralPath $RuntimePackage -Force | Copy-Item -Destination $Bad -Recurse
            switch ($Kind) {
                'missing-rui' { Remove-Item -LiteralPath (Join-Path $Bad 'net48\SmartSkin.Rhino8.rui') }
                'changed-core' { Add-Content -LiteralPath (Join-Path $Bad 'net48\SmartSkin.Core.dll') -Value 'intentional test corruption' }
                'extra-file' { Set-Content -LiteralPath (Join-Path $Bad 'unlisted-file.txt') -Value 'intentional unexpected file' }
                'wrong-version' { $Manifest = Get-Content -LiteralPath (Join-Path $Bad 'manifest.json') -Raw | ConvertFrom-Json; $Manifest.version = '0.0.0-invalid-test'; $Manifest | ConvertTo-Json -Depth 30 | Set-Content -LiteralPath (Join-Path $Bad 'manifest.json') -Encoding UTF8 }
            }
            $Null = Invoke-Entry INSTALL $Restricted -Root $Bad -ExpectSuccess $false -ExpectedError '(?i)package|manifest'
            Assert-True ((Get-RegistrySnapshotJson $RegistryTestRoot) -ceq $OriginalRegistry) "Rejected $Kind changed user registration."
            Assert-True ((Get-FileSnapshotJson $OldDirectory) -ceq $OriginalLegacy) "Rejected $Kind changed legacy files."
            Assert-True (-not (Test-Path -LiteralPath $InstallRoot)) "Rejected $Kind created installation state."
            Remove-Item -LiteralPath $Bad -Recurse -Force
        }
        Write-Host "SMARTSKIN_INSTALLER_TEST PHASE | $Mode | real-package-install-failure-atomicity"
        foreach ($Point in @('AfterPayload', 'AfterRegistryClear', 'AfterRegistryWrite', 'AfterCleanup')) {
            $Null = Invoke-Entry INSTALL $Restricted -FailAt $Point -ExpectSuccess $false -ExpectedError ([regex]::Escape($Point))
            Assert-True ((Get-RegistrySnapshotJson $RegistryTestRoot) -ceq $OriginalRegistry) "Failed install changed typed registry state: $Point"
            Assert-True ((Get-FileSnapshotJson $OldDirectory) -ceq $OriginalLegacy) "Failed install changed legacy files: $Point"
            Assert-True (-not (Test-Path -LiteralPath (Join-Path $InstallRoot 'current'))) "Failed initial install left active current payload: $Point"
        }
        Write-Host "SMARTSKIN_INSTALLER_TEST PHASE | $Mode | migrate-real-package-and-repeat-update"
        $Null = Invoke-Entry INSTALL $Restricted
        Assert-Installed
        foreach ($Name in @('SmartSkin.Rhino8.rhp', 'SmartSkin.Rhino8.rui', 'SmartSkin.Core.dll', 'SmartSkin.Rhino8.pdb', 'SmartSkin.Core.pdb', 'SmartSkin.Rhino8.deps.json')) { Assert-True (-not (Test-Path -LiteralPath (Join-Path $OldDirectory $Name))) "Known legacy asset survived cleanup: $Name" }
        # Put a deliberately distinguishable predecessor in physical current, then
        # update using the real unchanged release package. Rollback must restore
        # this predecessor's exact bytes on every injected failure.
        Set-Content -LiteralPath (Join-Path $InstallRoot 'current\keep-current-user.txt') -Value 'user current file' -Encoding ASCII
        Set-Content -LiteralPath (Join-Path $InstallRoot 'current\Python\keep-current-user.py') -Value '# user current module' -Encoding ASCII
        $CurrentCore = Join-Path $InstallRoot 'current\SmartSkin.Core.dll'
        [IO.File]::WriteAllBytes($CurrentCore, [byte[]]@(83, 83, 45, 111, 108, 100))
        $BeforeUpdateFiles = Get-FileSnapshotJson (Join-Path $InstallRoot 'current')
        $BeforeUpdateRegistry = Get-RegistrySnapshotJson $RegistryTestRoot
        foreach ($Point in @('AfterPayload', 'AfterRegistryClear', 'AfterRegistryWrite', 'AfterCleanup')) {
            $Null = Invoke-Entry INSTALL $Restricted -FailAt $Point -ExpectSuccess $false -ExpectedError ([regex]::Escape($Point))
            Assert-True ((Get-FileSnapshotJson (Join-Path $InstallRoot 'current')) -ceq $BeforeUpdateFiles) "Failed update lost predecessor bytes: $Point"
            Assert-True ((Get-RegistrySnapshotJson $RegistryTestRoot) -ceq $BeforeUpdateRegistry) "Failed update changed registration: $Point"
        }
        $Null = Invoke-Entry INSTALL $Restricted
        Assert-Installed
        $Null = Invoke-Entry INSTALL $Restricted
        Assert-Installed
        $InstalledFiles = Get-FileSnapshotJson (Join-Path $InstallRoot 'current')
        $InstalledRegistry = Get-RegistrySnapshotJson $RegistryTestRoot
        Write-Host "SMARTSKIN_INSTALLER_TEST PHASE | $Mode | genuine-uninstall-failure-atomicity"
        foreach ($Point in @('AfterRegistryClear', 'AfterCleanup')) {
            $Null = Invoke-Entry UNINSTALL $Restricted -FailAt $Point -ExpectSuccess $false -ExpectedError ([regex]::Escape($Point))
            Assert-True ((Get-FileSnapshotJson (Join-Path $InstallRoot 'current')) -ceq $InstalledFiles) "Failed uninstall changed current bytes: $Point"
            Assert-True ((Get-RegistrySnapshotJson $RegistryTestRoot) -ceq $InstalledRegistry) "Failed uninstall changed typed registry state: $Point"
        }
        $Null = Invoke-Entry UNINSTALL $Restricted
        Assert-True (@(Get-OwnKeys).Count -eq 0) 'Uninstall retained or restored an own-GUID registration.'
        Assert-True (-not (Test-Path -LiteralPath (Join-Path $InstallRoot 'current\SmartSkin.Rhino8.rhp'))) 'Uninstall retained the managed plug-in.'
        foreach ($Asset in @('smart_skin.py', 'native_input.py', 'native_family.py', 'skin_kernel.py', 'preview.py', 'native_boundary_evidence.py', 'fan_shared_jets.py', 'fan_rational_fields.py', 'fan_geometry.py', 'lower_corner_geometry.py', 'upper_corner_geometry.py', 'upper_corner_certificate.py', 'constrained_uv.py', 'repaired_validation.py', 'native_owner_separation.py', 'atlas_separation.py')) {
            Assert-True (-not (Test-Path -LiteralPath (Join-Path $InstallRoot ('current\Python\' + $Asset)))) "Uninstall retained a managed Python asset: $Asset"
        }
        Assert-UnrelatedPreserved
        Assert-True (Test-Path -LiteralPath (Join-Path $InstallRoot 'current\keep-current-user.txt')) 'Uninstall deleted unrelated current file.'
        Assert-True (Test-Path -LiteralPath (Join-Path $InstallRoot 'current\Python\keep-current-user.py')) 'Uninstall deleted unrelated current Python file.'
        $Null = Invoke-Entry UNINSTALL $Restricted
        Assert-True (@(Get-OwnKeys).Count -eq 0) 'Repeat uninstall restored a predecessor registration.'
        Assert-UnrelatedPreserved
    }
    & (Join-Path $HelperRoot 'Test-OptionalCleanup.ps1') -LifecyclePath (Join-Path $RuntimePackage 'Installer-Lifecycle.ps1') -TestRoot $TestRoot
    Assert-True ((Get-FileSnapshotJson $RuntimePackage) -ceq $PackageBefore) 'Installer or harness mutated the packaged entry scripts/payload.'
    Assert-MachineUnchanged
    Assert-NoRhinoLaunch
    Write-Host "SMARTSKIN_INSTALLER_TEST PASS | real_CMD_invocations=$InvocationCount | PowerShell=5.1-x64 | tokens=elevated+same-SID-restricted-nonadmin | physical_current=VERIFIED | isolated_HKCU=VERIFIED | existing_HKLM_fixture=UNCHANGED | Rhino_autolaunch=NONE | native_Rhino_load_and_HKCU_HKLM_lookup=NOT VERIFIED"
} finally {
    if ($EventRegistered) { Unregister-Event -SourceIdentifier $RhinoEventId -ErrorAction SilentlyContinue; Get-Event -SourceIdentifier $RhinoEventId -ErrorAction SilentlyContinue | Remove-Event -ErrorAction SilentlyContinue }
    foreach ($Path in @($RegistryTestRoot, $MachineTestRoot, $TestRoot)) { if (Test-Path -LiteralPath $Path) { Remove-Item -LiteralPath $Path -Recurse -Force } }
    $env:SMARTSKIN_TEST_PREVIOUS = $SavedPreviousEnv
    if ($TranscriptStarted) { Stop-Transcript | Out-Null }
}
