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

$repoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$keysDir = if ($IsWindows) {
    Join-Path $env:APPDATA "sops\\age"
} else {
    Join-Path $HOME ".config/sops/age"
}
$keysFile = Join-Path $keysDir "keys.txt"
$candidateKeys = @(
    (Join-Path $repoRoot "projects\\home-lab\\secrets\\masterkey.age"),
    (Join-Path $repoRoot "secrets\\masterkey.age")
)
$masterKey = $candidateKeys | Where-Object { Test-Path $_ } | Select-Object -First 1

if (Test-Path $keysFile) {
    Write-Error "Keys file already exists: $keysFile. Remove it first to use recovery mode."
    exit 1
}

if (-not $masterKey) {
    $searched = ($candidateKeys -join ", ")
    Write-Error "Master key not found. Searched: $searched"
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
Write-Host "Run './scripts/secrets/lock-secrets.ps1' when done."
