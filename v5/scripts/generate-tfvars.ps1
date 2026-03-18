$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$pythonScript = Join-Path $scriptDir "generate-tfvars.py"

if (-not (Test-Path $pythonScript)) {
    Write-Error "Script not found: $pythonScript"
    exit 1
}

python $pythonScript @args
exit $LASTEXITCODE
