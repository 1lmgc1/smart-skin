$ErrorActionPreference='Stop'
try {
    if (Get-Process -Name Rhino -ErrorAction SilentlyContinue) { throw 'Close Rhino first. No process will be terminated.' }
    $root=Join-Path $env:LOCALAPPDATA 'SmartSkin\Field'
    $pointer=Join-Path $root 'current.json'
    if (-not (Test-Path -LiteralPath $pointer)) { Write-Host 'Smart Skin Field is not installed.'; exit 0 }
    $state=Get-Content -LiteralPath $pointer -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($state.package -ne 'P08D1B-FIELD01') { throw 'Another field version is active. It was not removed.' }
    $release=[IO.Path]::GetFullPath([string]$state.release)
    $allowed=[IO.Path]::GetFullPath((Join-Path $root 'releases'))+'\'
    if (-not $release.StartsWith($allowed,[StringComparison]::OrdinalIgnoreCase) -or -not (Test-Path -LiteralPath (Join-Path $release '.smartskin-field-owned'))) { throw 'Unmanaged path; uninstall stopped.' }
    $link=Join-Path ([Environment]::GetFolderPath('Desktop')) 'Smart Skin Field.lnk'
    if (Test-Path -LiteralPath $link) {
        $shell=New-Object -ComObject WScript.Shell
        $sc=$shell.CreateShortcut($link)
        if ($sc.Arguments -like ('*'+$release+'*')) { Remove-Item -LiteralPath $link -Force }
    }
    Remove-Item -LiteralPath $release -Recurse -Force
    Remove-Item -LiteralPath $pointer -Force
    Write-Host 'Field payload removed. Reports and working .3dm copies retained. Production Smart Skin untouched.'
} catch { Write-Host ('UNINSTALL STOP: '+$_.Exception.Message) -ForegroundColor Red; exit 1 }
