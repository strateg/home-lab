# Install tools for build/validate/generate workflows on Windows.
# This script does NOT install deployment tools (Ansible/Terraform apply).

param(
    [switch]$SkipOptional,
    [switch]$SkipVenv
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

Write-Info "Installing build/validate/generate tools (Windows)"
Ensure-Winget

# Required: Git, Python
Ensure-Tool "Git" "git" "Git.Git"

# Prefer existing Python if present
if (Get-Command python -ErrorAction SilentlyContinue) {
    Write-Ok "Python already installed"
} else {
    Write-Info "Installing Python 3.11"
    winget install --id Python.Python.3.11 --silent --accept-source-agreements --accept-package-agreements
}

# Optional tools
if (-not $SkipOptional) {
    Ensure-Tool "jq" "jq" "jqlang.jq"
    # yq is optional; use kislyuk.yq (Python-based) if needed
    if (-not (Get-Command yq -ErrorAction SilentlyContinue)) {
        Write-Info "Installing yq (Python-based)"
        python -m pip install yq
    } else {
        Write-Ok "yq already installed"
    }
}

# Project venv + deps (optional)
if (-not $SkipVenv) {
    Write-Info "Setting up Python venv and dev dependencies"
    if (-not (Test-Path ".venv")) {
        python -m venv .venv
    }
    .\.venv\Scripts\python -m pip install --upgrade pip
    .\.venv\Scripts\python -m pip install -r requirements-dev.txt
}

Write-Ok "Build tools installation completed"
