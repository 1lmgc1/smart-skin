[CmdletBinding()]
param()
$ErrorActionPreference='Stop'
try {
    . (Join-Path $PSScriptRoot 'install.ps1')
    $null=Test-Payload $PSScriptRoot
    $exe=Resolve-Rhino
    $root=Join-Path $env:LOCALAPPDATA 'SmartSkin\Field'
    $reportDir=Join-Path $root 'reports'
    $null=New-Item -ItemType Directory -Path $reportDir -Force
    $run=Join-Path (Join-Path $root 'work') ([DateTime]::UtcNow.ToString('yyyyMMdd-HHmmss')+'-'+[Guid]::NewGuid().ToString('N').Substring(0,8))
    $null=New-Item -ItemType Directory -Path $run -Force
    $model=Join-Path $run 'SmartSkin_FieldComparison.3dm'
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'payload\comparison.3dm') -Destination $model
    $script=Join-Path $PSScriptRoot 'payload\field_runtime.py'
    $env:SMARTSKIN_FIELD_REPORTS=$reportDir
    # Parenthesized Python path is Rhino's documented /runscript quoting form.
    $arguments='"'+$model+'" /nosplash /runscript="_-RunPythonScript ('+$script+')"'
    $null=Start-Process -FilePath $exe -ArgumentList $arguments -PassThru
    Write-Host ('FIELD COPY: '+$model)
    Write-Host ('REPORTS: '+$reportDir)
} catch {
    Write-Host ('LAUNCH STOP: '+$_.Exception.Message) -ForegroundColor Red
    if ($Host.Name -eq 'ConsoleHost') { $null=Read-Host 'Press Enter to close' }
    throw
}
