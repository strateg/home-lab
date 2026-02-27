# Verify tools for build/validate/generate workflows on Windows.

$ErrorActionPreference = "Stop"

function Check($name, $cmd) {
    if (Get-Command $cmd -ErrorAction SilentlyContinue) {
        Write-Host "[OK] $name" -ForegroundColor Green
    } else {
        Write-Host "[MISSING] $name" -ForegroundColor Yellow
    }
}

Write-Host "Build tools verification" -ForegroundColor Cyan

Check "Git" "git"
Check "Python" "python"
Check "pip" "pip"
Check "jq" "jq"
Check "yq" "yq"

Write-Host ""
Write-Host "If Python is present, verify packages:" -ForegroundColor Cyan
Write-Host "  python -m pip show pydantic pyyaml packaging jinja2 requests" -ForegroundColor Gray
