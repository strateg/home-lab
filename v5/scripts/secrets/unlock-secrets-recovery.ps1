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

$v5Root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$keysDir = if ($IsWindows) {
    Join-Path $env:APPDATA "sops\\age"
} else {
    Join-Path $HOME ".config/sops/age"
}
$keysFile = Join-Path $keysDir "keys.txt"
$masterKey = Join-Path $v5Root "secrets\\masterkey.age"

if (Test-Path $keysFile) {
    Write-Error "Keys file already exists: $keysFile. Remove it first to use recovery mode."
    exit 1
}

if (-not (Test-Path $masterKey)) {
    Write-Error "Master key not found: $masterKey"
    exit 1
}

New-Item -ItemType Directory -Path $keysDir -Force | Out-Null
$ageBin = Resolve-AgeBinary
Write-Host "RECOVERY MODE: decrypting masterkey..."
$keyMaterial = & $ageBin -d $masterKey
if ($LASTEXITCODE -ne 0) {
    Write-Error "Failed to decrypt masterkey using '$ageBin'."
    exit 1
}

$keyMaterial | Out-File -FilePath $keysFile -Encoding ascii -NoNewline
Write-Host "Secrets unlocked via masterkey."
Write-Host "Run './v5/scripts/secrets/lock-secrets.ps1' when done."
