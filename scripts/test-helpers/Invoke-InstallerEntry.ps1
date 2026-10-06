# Test-only observer. Executes the unmodified packaged CMD and production PS1.
[CmdletBinding()]
param([Parameter(Mandatory = $true)][string]$DescriptorPath)
Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'
$Descriptor = Get-Content -LiteralPath $DescriptorPath -Raw | ConvertFrom-Json
$Result = [ordered]@{ completed = $false; launcher_exit_code = $null; token = $null; error = ''; output = '' }
try {
    if ($PSVersionTable.PSVersion.Major -ne 5 -or $PSVersionTable.PSVersion.Minor -ne 1 -or -not [Environment]::Is64BitProcess) { throw 'The entry observer must run in 64-bit Windows PowerShell 5.1.' }
    Add-Type -Path (Join-Path $PSScriptRoot 'InstallerTokenHarness.cs')
    $Result.token = [SmartSkin.InstallerTests.TokenProcess]::CurrentFacts()
    if ($Result.token.UserSid -ne $Descriptor.expected_sid) { throw 'Child process unexpectedly changed Windows user.' }
    if ($Descriptor.restricted) {
        if ($Result.token.IsAdministrator -or -not $Result.token.AdministratorsSidDenyOnly -or $Result.token.IntegrityRid -ne 8192) { throw 'Non-admin child token was not genuinely restricted at medium integrity.' }
    } elseif (-not $Result.token.IsAdministrator -or -not $Result.token.IsElevated) { throw 'Full-token test requires the same-user elevated CI token.' }
    $Launcher = Join-Path $Descriptor.package_root ($Descriptor.launcher + '.cmd')
    if ((Get-FileHash -LiteralPath $Launcher -Algorithm SHA256).Hash -ne $Descriptor.launcher_sha256) { throw 'Launcher changed before invocation.' }
    $env:SMARTSKIN_INSTALL_NO_PAUSE = '1'
    $Start = New-Object Diagnostics.ProcessStartInfo
    $Start.FileName = $env:ComSpec
    $Start.WorkingDirectory = $Descriptor.package_root
    $Start.Arguments = '/d /v:off /s /c ""' + $Launcher + '" ' + $Descriptor.arguments + '"'
    $Start.UseShellExecute = $false
    $Start.CreateNoWindow = $true
    $Start.RedirectStandardOutput = $true
    $Start.RedirectStandardError = $true
    $Process = New-Object Diagnostics.Process
    $Process.StartInfo = $Start
    [void]$Process.Start()
    $OutTask = $Process.StandardOutput.ReadToEndAsync()
    $ErrorTask = $Process.StandardError.ReadToEndAsync()
    $Process.WaitForExit()
    $Result.output = $OutTask.Result + $ErrorTask.Result
    $Result.launcher_exit_code = $Process.ExitCode
    $Result.completed = $true
    $Process.Dispose()
} catch { $Result.error = $_.Exception.ToString() }
finally { $Result | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $Descriptor.result_path -Encoding UTF8 }
if (-not $Result.completed) { exit 125 }
exit 0
