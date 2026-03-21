$ErrorActionPreference = "Stop"

param(
    [switch]$SkipPythonDeps
)

$repoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)

function Write-Info {
    param([string]$Message)
    Write-Host "[setup-dev] $Message"
}

function Ensure-Command {
    param([string]$Name)
    return [bool](Get-Command $Name -ErrorAction SilentlyContinue)
}

function Install-WingetPackage {
    param(
        [Parameter(Mandatory = $true)][string]$Id
    )
    if (-not (Ensure-Command "winget")) {
        throw "winget is not available. Install App Installer from Microsoft Store first."
    }
    & winget install --id $Id -e --accept-package-agreements --accept-source-agreements
}

function Install-Tooling {
    Write-Info "Installing sops"
    Install-WingetPackage -Id "SecretsOPerationS.SOPS"

    Write-Info "Installing rage (age-compatible)"
    Install-WingetPackage -Id "str4d.rage"

    Write-Info "Installing go-task"
    Install-WingetPackage -Id "Task.Task"
}

function Resolve-Python {
    if (Ensure-Command "python") {
        return "python"
    }
    if (Ensure-Command "py") {
        return "py"
    }
    throw "Python is not installed or not available in PATH."
}

function Install-PythonDeps {
    if ($SkipPythonDeps) {
        Write-Info "Skipping Python dev dependencies installation."
        return
    }

    $py = Resolve-Python
    Write-Info "Installing Python dev dependencies in editable mode"
    Push-Location $repoRoot
    try {
        & $py -m pip install --upgrade pip
        & $py -m pip install -e ".[dev]"
    }
    finally {
        Pop-Location
    }
}

function Print-Versions {
    Write-Host ""
    if (Ensure-Command "python") { & python --version }
    if (Ensure-Command "sops") { & sops --version }
    if (Ensure-Command "rage") { & rage --version }
    if (Ensure-Command "task") { & task --version }
}

Install-Tooling
Install-PythonDeps
Print-Versions
Write-Info "Done."
