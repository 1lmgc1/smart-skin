$ErrorActionPreference='Stop'
. (Join-Path $PSScriptRoot 'install.ps1')
$root=Join-Path ([IO.Path]::GetTempPath()) ('SmartSkin test & space '+[Guid]::NewGuid().ToString('N'))
$src=Join-Path $root 'input';$dst=Join-Path $root 'installed';$checks=0
function Assert([bool]$ok,[string]$message) { if (-not $ok) { throw $message }; $script:checks++ }
function Expect-Error([scriptblock]$call) { $raised=$false;try { & $call | Out-Null } catch {$raised=$true};Assert $raised 'Expected error was not raised' }
try {
    $null=New-Item -ItemType Directory -Path $src -Force
    $records=@()
    foreach ($name in @('a.txt','b.txt','c.txt','d.txt')) {
        $p=Join-Path $src $name;[IO.File]::WriteAllText($p,'payload '+$name)
        $records+=@{path=$name;sha256=(Get-FileHash -LiteralPath $p -Algorithm SHA256).Hash.ToLowerInvariant()}
    }
    $mp=Join-Path $src 'SHA256.json'
    $body=@{package='P08D1B-FIELD01';files=$records}|ConvertTo-Json -Depth 5
    [IO.File]::WriteAllText($mp,$body)
    $null=Test-Payload $src;Assert $true 'Initial manifest'
    $release=Install-Payload $src $dst;Assert (Test-Path -LiteralPath (Join-Path $release '.smartskin-field-owned')) 'Owner marker'
    $again=Install-Payload $src $dst;Assert ($again -eq $release) 'Idempotent release'
    $pointer=Join-Path $dst 'pointer.txt';Set-AtomicText $pointer 'first';Set-AtomicText $pointer 'second'
    Assert (([IO.File]::ReadAllText($pointer)) -eq 'second') 'Atomic pointer update'
    $sentinel=Join-Path $root 'production.rhp';[IO.File]::WriteAllText($sentinel,'unchanged');$sentinelHash=(Get-FileHash $sentinel).Hash
    [IO.File]::WriteAllText((Join-Path $src 'a.txt'),'corrupt')
    Expect-Error {Test-Payload $src};Expect-Error {Install-Payload $src $dst}
    Assert ((Get-FileHash $sentinel).Hash -eq $sentinelHash) 'Production sentinel untouched'
    $bad=@{package='P08D1B-FIELD01';files=@(@{path='../escape';sha256='a'},@{path='b';sha256='a'},@{path='c';sha256='a'},@{path='d';sha256='a'})}|ConvertTo-Json -Depth 5
    [IO.File]::WriteAllText($mp,$bad);Expect-Error {Test-Payload $src}
    $tokens=$null;$errors=$null
    foreach ($file in @('install.ps1','launch.ps1','uninstall.ps1')) {
        $null=[System.Management.Automation.Language.Parser]::ParseFile((Join-Path $PSScriptRoot $file),[ref]$tokens,[ref]$errors)
        Assert (@($errors).Count -eq 0) ('Parse '+$file)
    }
    Write-Output ('INSTALLER_TESTS_PASS='+$checks)
} finally {if (Test-Path -LiteralPath $root) {Remove-Item -LiteralPath $root -Recurse -Force}}
