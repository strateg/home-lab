# Install tools for deployment (apply to target devices) on Windows.
# This script is separate from build/validate/generate tooling.

param(
    [switch]$WithWSLAnsible,
    [switch]$SkipOptional
)

$ErrorActionPreference = "Stop"

function Write-Info([string]$Message) {
    Write-Host "[INFO] $Message" -ForegroundColor Cyan
}

function Write-Ok([string]$Message) {
    Write-Host "[OK] $Message" -ForegroundColor Green
}

function Write-Warn([string]$Message) {
    Write-Host "[WARN] $Message" -ForegroundColor Yellow
}

function Write-Err([string]$Message) {
    Write-Host "[ERROR] $Message" -ForegroundColor Red
}

function Ensure-Winget {
    if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
        Write-Err "winget not found. Install App Installer from Microsoft Store."
        exit 1
    }
}

function Ensure-Tool($name, $cmd, $wingetId) {
    if (Get-Command $cmd -ErrorAction SilentlyContinue) {
        Write-Ok "$name already installed"
        return
    }
    Write-Info "Installing $name ($wingetId)"
    winget install --id $wingetId --silent --accept-source-agreements --accept-package-agreements
}

Write-Info "Installing deployment tools (Windows)"
Ensure-Winget

# Terraform for apply
Ensure-Tool "Terraform" "terraform" "HashiCorp.Terraform"

# OpenSSH client is usually present on Windows; check and enable if missing
if (-not (Get-Command ssh -ErrorAction SilentlyContinue)) {
    Write-Warn "OpenSSH client not found. Enable it in Windows Features."
    Write-Info "Settings -> Apps -> Optional Features -> OpenSSH Client"
} else {
    Write-Ok "OpenSSH client available"
}

# Optional: rsync in WSL or Git Bash; not installed by default
if (-not $SkipOptional) {
    Write-Warn "rsync is optional. If needed, install via WSL (sudo apt install rsync)."
}

# Optional: Install WSL + Ansible
if ($WithWSLAnsible) {
    Write-Info "Installing WSL (requires admin)"
    wsl --install
    Write-Info "After WSL is installed, run in WSL: sudo apt update && sudo apt install -y ansible"
}

Write-Ok "Deployment tools installation completed"
