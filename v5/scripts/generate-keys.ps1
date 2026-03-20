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

function Resolve-KeygenBinary {
    if (Get-Command age-keygen -ErrorAction SilentlyContinue) {
        return "age-keygen"
    }
    if (Get-Command rage-keygen -ErrorAction SilentlyContinue) {
        return "rage-keygen"
    }
    throw "Neither 'age-keygen' nor 'rage-keygen' is installed or available in PATH."
}

function Read-PublicKey([string]$path) {
    $matchLine = Select-String -Path $path -Pattern "public key:\\s*(\\S+)" | Select-Object -First 1
    if (-not $matchLine) {
        throw "Failed to extract public key from: $path"
    }
    return $matchLine.Matches[0].Groups[1].Value
}

$repoRoot = Split-Path -Parent $PSScriptRoot
$secretsDir = Join-Path $repoRoot "secrets"
$devKeyEnc = Join-Path $secretsDir "devkey.age"
$devKeyPubFile = Join-Path $secretsDir "devkey.pub"
$masterKeyEnc = Join-Path $secretsDir "masterkey.age"
$masterKeyPubFile = Join-Path $secretsDir "masterkey.pub"
$sopsConfigFile = Join-Path $secretsDir ".sops.yaml"

$ageBin = Resolve-AgeBinary
$keygenBin = Resolve-KeygenBinary
$tmpDev = [System.IO.Path]::GetTempFileName()
$tmpMaster = [System.IO.Path]::GetTempFileName()

try {
    Write-Host "Generating devkey (daily operations)..."
    & $keygenBin -o $tmpDev
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to generate devkey with '$keygenBin'."
    }
    $devPub = Read-PublicKey $tmpDev
    Write-Host "Dev public key: $devPub"
    Write-Host "Enter passphrase for DEVKEY:"
    & $ageBin -p -o $devKeyEnc $tmpDev
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to encrypt devkey with '$ageBin'."
    }
    Set-Content -Path $devKeyPubFile -Value $devPub -Encoding ascii

    Write-Host ""
    Write-Host "Generating masterkey (recovery only)..."
    & $keygenBin -o $tmpMaster
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to generate masterkey with '$keygenBin'."
    }
    $masterPub = Read-PublicKey $tmpMaster
    Write-Host "Master public key: $masterPub"
    Write-Host "Enter passphrase for MASTERKEY:"
    & $ageBin -p -o $masterKeyEnc $tmpMaster
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to encrypt masterkey with '$ageBin'."
    }
    Set-Content -Path $masterKeyPubFile -Value $masterPub -Encoding ascii

    $sopsConfig = @"
creation_rules:
  # All YAML files encrypted with both keys (devkey + masterkey)
  # devkey: daily operations (shorter passphrase)
  # masterkey: recovery only (long passphrase, stored securely)
  - path_regex: \.yaml$
    age: >-
      $devPub,
      $masterPub
"@
    Set-Content -Path $sopsConfigFile -Value $sopsConfig -Encoding utf8

    Write-Host ""
    Write-Host "Keys generated successfully."
    Write-Host "Next steps:"
    Write-Host "  1. ./v5/scripts/unlock-secrets.ps1"
    Write-Host "  2. Re-encrypt secrets (PowerShell): Get-ChildItem v5/projects/home-lab/secrets -Recurse -Filter *.yaml | ForEach-Object { sops updatekeys -y $_.FullName }"
} finally {
    if (Test-Path $tmpDev) {
        Remove-Item -Force $tmpDev
    }
    if (Test-Path $tmpMaster) {
        Remove-Item -Force $tmpMaster
    }
}
