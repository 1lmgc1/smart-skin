[CmdletBinding()]
param([switch]$NoLaunch)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 2
$Package = 'P08D1B-FIELD01'
function Test-Payload([string]$Base) {
    $manifestPath = Join-Path $Base 'SHA256.json'
    if (-not (Test-Path -LiteralPath $manifestPath -PathType Leaf)) { throw 'SHA256.json missing. Extract the entire ZIP first.' }
    $manifest = Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($manifest.package -ne $Package -or @($manifest.files).Count -lt 4) { throw 'Wrong package manifest.' }
    foreach ($record in $manifest.files) {
        $rel = [string]$record.path
        if ([IO.Path]::IsPathRooted($rel) -or $rel -match '(^|[/\\])\.\.?([/\\]|$)' -or $rel -match ':') { throw 'Unsafe manifest path.' }
        $path = Join-Path $Base $rel
        $item = Get-Item -LiteralPath $path -ErrorAction Stop
        if ($item.PSIsContainer -or ($item.Attributes -band [IO.FileAttributes]::ReparsePoint)) { throw 'Unsafe payload item.' }
        if ((Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant() -ne $record.sha256) { throw "Checksum mismatch: $rel" }
    }
    return $manifest
}
function Set-AtomicText([string]$Path,[string]$Value) {
    $tmp = $Path + '.' + [Guid]::NewGuid().ToString('N') + '.tmp'
    try {
        [IO.File]::WriteAllText($tmp,$Value,(New-Object Text.UTF8Encoding($false)))
        if (Test-Path -LiteralPath $Path) { [IO.File]::Replace($tmp,$Path,$null) }
        else { [IO.File]::Move($tmp,$Path) }
    } finally { if (Test-Path -LiteralPath $tmp) { Remove-Item -LiteralPath $tmp -Force } }
}
function Install-Payload([string]$Source,[string]$Root) {
    $manifest=Test-Payload $Source
    $digest=(Get-FileHash -LiteralPath (Join-Path $Source 'SHA256.json') -Algorithm SHA256).Hash.ToLowerInvariant()
    $release=Join-Path (Join-Path $Root 'releases') ($Package+'-'+$digest.Substring(0,12))
    if (Test-Path -LiteralPath $release) {
        if (-not (Test-Path -LiteralPath (Join-Path $release '.smartskin-field-owned'))) { throw 'Existing release is not managed by Smart Skin Field.' }
        $null=Test-Payload $release
    } else {
        $stage=$release+'.staging-'+[Guid]::NewGuid().ToString('N')
        try {
            $null=New-Item -ItemType Directory -Path $stage -Force
            foreach ($record in $manifest.files) {
                $dest=Join-Path $stage $record.path
                $null=New-Item -ItemType Directory -Path ([IO.Path]::GetDirectoryName($dest)) -Force
                Copy-Item -LiteralPath (Join-Path $Source $record.path) -Destination $dest
            }
            Copy-Item -LiteralPath (Join-Path $Source 'SHA256.json') -Destination $stage
            [IO.File]::WriteAllText((Join-Path $stage '.smartskin-field-owned'),$Package)
            $null=Test-Payload $stage
            Move-Item -LiteralPath $stage -Destination $release
        } finally { if (Test-Path -LiteralPath $stage) { Remove-Item -LiteralPath $stage -Recurse -Force } }
    }
    return $release
}
function Resolve-Rhino {
    $exe=Join-Path $env:ProgramFiles 'Rhino 8\System\Rhino.exe'
    if (-not (Test-Path -LiteralPath $exe -PathType Leaf)) { throw 'Rhino 8 was not found in Program Files.' }
    $info=(Get-Item -LiteralPath $exe).VersionInfo
    if ($info.FileMajorPart -ne 8 -or $info.FileMinorPart -lt 21) { throw 'This field kit requires Rhino 8.21 or later.' }
    return $exe
}
if ($MyInvocation.InvocationName -eq '.') { return }
try {
    if (Get-Process -Name Rhino -ErrorAction SilentlyContinue) { throw 'Save your models and close Rhino before installing. No process will be terminated.' }
    $null=Resolve-Rhino
    $root=Join-Path $env:LOCALAPPDATA 'SmartSkin\Field'
    $release=Install-Payload $PSScriptRoot $root
    $desktop=[Environment]::GetFolderPath('Desktop')
    $link=Join-Path $desktop 'Smart Skin Field.lnk'
    $shell=New-Object -ComObject WScript.Shell
    if (Test-Path -LiteralPath $link) {
        $prior=$shell.CreateShortcut($link)
        if ($prior.Arguments -notlike ('*'+$root+'*')) { throw 'An unrelated Smart Skin Field shortcut already exists; it was not overwritten.' }
    }
    $shortcut=$shell.CreateShortcut($link)
    $shortcut.TargetPath=Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
    $shortcut.Arguments='-NoLogo -NoProfile -ExecutionPolicy Bypass -File "'+(Join-Path $release 'launch.ps1')+'"'
    $shortcut.WorkingDirectory=$release
    $shortcut.Description='Smart Skin experimental field review. No production plug-in replacement.'
    $shortcut.Save()
    $pointer=@{package=$Package;release=$release;installed_utc=[DateTime]::UtcNow.ToString('o')} | ConvertTo-Json
    Set-AtomicText (Join-Path $root 'current.json') $pointer
    $logDir=Join-Path $root 'reports'; $null=New-Item -ItemType Directory -Path $logDir -Force
    $log=Join-Path $logDir ('install-'+[DateTime]::UtcNow.ToString('yyyyMMdd-HHmmss')+'.txt')
    [IO.File]::WriteAllText($log,"Package: $Package`r`nRelease: $release`r`nProduction RHP: UNCHANGED`r`nRhino runtime settings: UNCHANGED`r`nChecksums: MATCH`r`n")
    Write-Host ('INSTALLED: '+$Package)
    Write-Host ('Shortcut: '+$link)
    Write-Host 'Production P07F2 is unchanged. No .NET or Python installation is needed.'
    if (-not $NoLaunch) { & (Join-Path $release 'launch.ps1') }
} catch {
    Write-Host ('INSTALL STOP: '+$_.Exception.Message) -ForegroundColor Red
    exit 1
}
