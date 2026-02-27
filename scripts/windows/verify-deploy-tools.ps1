# Verify tools for deployment on Windows.

$ErrorActionPreference = "Stop"

function Check($name, $cmd) {
    if (Get-Command $cmd -ErrorAction SilentlyContinue) {
        Write-Host "[OK] $name" -ForegroundColor Green
    } else {
        Write-Host "[MISSING] $name" -ForegroundColor Yellow
    }
}

Write-Host "Deploy tools verification" -ForegroundColor Cyan

Check "Terraform" "terraform"
Check "OpenSSH client" "ssh"

Write-Host ""
Write-Host "Ansible on Windows is typically used via WSL." -ForegroundColor Yellow
Write-Host "Check in WSL: ansible --version" -ForegroundColor Gray
