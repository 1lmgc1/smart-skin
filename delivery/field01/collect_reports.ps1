[CmdletBinding()]
param([string]$ReportRoot='', [string]$OutputRoot='', [switch]$SkipWindowsEvents)
$ErrorActionPreference='Stop'
Set-StrictMode -Version 2
# Reads Field text logs and recent Rhino-related Windows events only.
# No Rhino process start/stop, no registry changes, no geometry or memory dumps.
if ([string]::IsNullOrWhiteSpace($ReportRoot)) { $ReportRoot=Join-Path $env:LOCALAPPDATA 'SmartSkin\Field\reports' }
if ([string]::IsNullOrWhiteSpace($OutputRoot)) { $OutputRoot=[Environment]::GetFolderPath('Desktop') }
$tag='SmartSkin_Field_Diagnostics_'+[DateTime]::UtcNow.ToString('yyyyMMdd-HHmmss')+'-'+[Guid]::NewGuid().ToString('N').Substring(0,8)
$stage=Join-Path ([IO.Path]::GetTempPath()) $tag
$archive=Join-Path $OutputRoot ($tag+'.zip')
try {
    $null=New-Item -ItemType Directory -Path (Join-Path $stage 'field_reports') -Force
    $summary=New-Object System.Collections.Generic.List[string]
    $summary.Add('Diagnostic collection only. Rhino not launched. No data sent anywhere.')
    $summary.Add('Source: '+$ReportRoot)
    $summary.Add('At most 30 recent Field TXT logs, max 5 MiB per file, max 50 MiB total.')
    $total=0L
    if (Test-Path -LiteralPath $ReportRoot -PathType Container) {
        $logs=@(Get-ChildItem -LiteralPath $ReportRoot -File | Where-Object {
            $_.Name -like 'SmartSkin_Field_*.txt*' -or $_.Name -like 'install-*.txt'
        } | Sort-Object LastWriteTimeUtc -Descending | Select-Object -First 30)
        foreach($log in $logs) {
            if (($log.Attributes -band [IO.FileAttributes]::ReparsePoint) -or $log.Length -gt 5MB -or ($total+$log.Length) -gt 50MB) {
                $summary.Add('SKIPPED_SIZE_OR_LINK: '+$log.Name); continue
            }
            try {
                Copy-Item -LiteralPath $log.FullName -Destination (Join-Path $stage 'field_reports')
                $total+=$log.Length; $summary.Add('COPIED: '+$log.Name)
            } catch { $summary.Add('COPY_ERROR: '+$log.Name+' | '+$_.Exception.Message) }
        }
    } else { $summary.Add('Field report folder was not found. No Rhino retry is required.') }
    $eventPath=Join-Path $stage 'windows_rhino_events.txt'
    if ($SkipWindowsEvents) {
        [IO.File]::WriteAllText($eventPath,'Windows event read was explicitly skipped.')
    } else {
        try {
            $events=@(Get-WinEvent -FilterHashtable @{LogName='Application';Id=1000,1001,1026;StartTime=(Get-Date).AddDays(-3)} -MaxEvents 250 -ErrorAction Stop | Where-Object { $_.Message -match '(?i)rhino|smartskin' })
            $text=($events | ForEach-Object { 'Time: '+$_.TimeCreated.ToString('o')+"`r`nProvider: "+$_.ProviderName+"`r`nEvent: "+$_.Id+"`r`n"+$_.Message+"`r`n---`r`n" }) -join "`r`n"
            if (-not $text) { $text='No Rhino-related entry in the bounded event sample. This does not prove no crash occurred.' }
            [IO.File]::WriteAllText($eventPath,$text,(New-Object Text.UTF8Encoding($true)))
        } catch { [IO.File]::WriteAllText($eventPath,('EVENT_READ_UNAVAILABLE: '+$_.Exception.Message),(New-Object Text.UTF8Encoding($true))) }
    }
    $summary.Add('Privacy: text may contain local paths, source identifiers and fault-module names. Review before sharing.')
    $summary.Add('No .3dm, .dmp, credentials, unrelated application files or registry exports are collected.')
    [IO.File]::WriteAllLines((Join-Path $stage 'COLLECTION.txt'),$summary,(New-Object Text.UTF8Encoding($true)))
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    [IO.Compression.ZipFile]::CreateFromDirectory($stage,$archive)
    Write-Output ('DIAGNOSTICS_SAVED: '+$archive)
} finally {
    if (Test-Path -LiteralPath $stage) { Remove-Item -LiteralPath $stage -Recurse -Force }
}
