param(
    [switch]$SkipPythonDeps
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)

function Write-Info {
    param([string]$Message)
    Write-Host "[setup-dev] $Message"
}

function Ensure-Command {
    param([string]$Name)
    return [bool](Get-Command $Name -ErrorAction SilentlyContinue)
}

function Refresh-SessionPath {
    $machinePath = [Environment]::GetEnvironmentVariable("Path", "Machine")
    $userPath = [Environment]::GetEnvironmentVariable("Path", "User")
    $combined = @($machinePath, $userPath) -join ";"

    $knownRuntimePaths = @(
        (Join-Path $env:LOCALAPPDATA "Microsoft\\WinGet\\Links"),
        (Join-Path $env:LOCALAPPDATA "Microsoft\\WindowsApps")
    )
    foreach ($path in $knownRuntimePaths) {
        if ((Test-Path $path) -and ($combined -notlike "*$path*")) {
            $combined = "$combined;$path"
        }
    }

    $env:Path = $combined
}

function Ensure-TaskPathFromWingetPackage {
    if (Ensure-Command "task") {
        return
    }

    $taskExe = Get-ChildItem "$env:LOCALAPPDATA\\Microsoft\\WinGet\\Packages\\Task.Task*" -Recurse -Filter "task.exe" -ErrorAction SilentlyContinue |
        Select-Object -First 1 -ExpandProperty FullName
    if (-not $taskExe) {
        return
    }

    $taskDir = Split-Path -Parent $taskExe
    if (-not $taskDir) {
        return
    }

    if ($env:Path -notlike "*$taskDir*") {
        $env:Path = "$taskDir;$env:Path"
    }

    $userPath = [Environment]::GetEnvironmentVariable("Path", "User")
    if ($userPath -notlike "*$taskDir*") {
        [Environment]::SetEnvironmentVariable("Path", "$userPath;$taskDir", "User")
        Write-Info "Added task install directory to User PATH: $taskDir"
    }
}

function Invoke-Checked {
    param(
        [Parameter(Mandatory = $true)][string]$Label,
        [Parameter(Mandatory = $true)][string[]]$Command
    )

    & $Command[0] $Command[1..($Command.Length - 1)]
    if ($LASTEXITCODE -ne 0) {
        throw "$Label failed with exit code $LASTEXITCODE"
    }
}

function Install-WingetPackage {
    param(
        [Parameter(Mandatory = $true)][string]$Id
    )
    if (-not (Ensure-Command "winget")) {
        throw "winget is not available. Install App Installer from Microsoft Store first."
    }

    $installed = & winget list --id $Id --exact 2>$null
    if ($LASTEXITCODE -eq 0 -and $installed -match [Regex]::Escape($Id)) {
        Write-Info "Package '$Id' is already installed."
        return
    }

    & winget install --id $Id -e --accept-package-agreements --accept-source-agreements
    if ($LASTEXITCODE -ne 0) {
        $installedAfter = & winget list --id $Id --exact 2>$null
        if ($LASTEXITCODE -eq 0 -and $installedAfter -match [Regex]::Escape($Id)) {
            Write-Info "Package '$Id' appears installed despite non-zero winget exit code."
            return
        }
        throw "winget install failed for package '$Id' (exit code $LASTEXITCODE)."
    }
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
        Invoke-Checked -Label "pip upgrade" -Command @($py, "-m", "pip", "install", "--upgrade", "pip")
        Invoke-Checked -Label "pip dev install" -Command @($py, "-m", "pip", "install", "-e", ".[dev]")
    }
    finally {
        Pop-Location
    }
}

function Assert-RequiredTools {
    $missing = @()
    foreach ($name in @("sops", "rage", "task")) {
        if (-not (Ensure-Command $name)) {
            $missing += $name
        }
    }
    if ($missing.Count -gt 0) {
        throw "Missing required tools in PATH: $($missing -join ', '). Restart terminal and rerun script if they were just installed."
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
Refresh-SessionPath
Ensure-TaskPathFromWingetPackage
Assert-RequiredTools
Install-PythonDeps
Print-Versions
Write-Info "Done."
Write-Info "If 'task' is not available in your current terminal, restart PowerShell or run:"
Write-Info '$env:Path = [Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [Environment]::GetEnvironmentVariable("Path","User")'
