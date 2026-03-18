$ErrorActionPreference = "Stop"

function Resolve-AgeBinary {
    if (Get-Command age -ErrorAction SilentlyContinue) {
        return "age"
    }
    if (Get-Command rage -ErrorAction SilentlyContinue) {
        return "rage"
    }
    throw "Neither 'age' nor 'rage' is installed or available in PATH."
}

$repoRoot = Split-Path -Parent $PSScriptRoot
$keysDir = if ($IsWindows) {
    Join-Path $env:APPDATA "sops\\age"
} else {
    Join-Path $HOME ".config/sops/age"
}
$keysFile = Join-Path $keysDir "keys.txt"
$devKey = Join-Path $repoRoot "secrets\\devkey.age"

if (Test-Path $keysFile) {
    Write-Host "Secrets are already unlocked."
    exit 0
}

if (-not (Test-Path $devKey)) {
    Write-Error "Dev key not found: $devKey"
    exit 1
}

New-Item -ItemType Directory -Path $keysDir -Force | Out-Null
$ageBin = Resolve-AgeBinary
Write-Host "Decrypting devkey..."
$keyMaterial = & $ageBin -d $devKey
if ($LASTEXITCODE -ne 0) {
    Write-Error "Failed to decrypt devkey using '$ageBin'."
    exit 1
}

$keyMaterial | Out-File -FilePath $keysFile -Encoding ascii -NoNewline
Write-Host "Secrets unlocked."
Write-Host "Run './scripts/lock-secrets.ps1' when done."
