$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$pythonScript = Join-Path $scriptDir "update-mikrotik-terraform-secrets.py"

if (-not (Test-Path $pythonScript)) {
    Write-Error "Script not found: $pythonScript"
    exit 1
}

python $pythonScript @args
exit $LASTEXITCODE
