$ErrorActionPreference = "Stop"

$keysDir = if ($IsWindows) {
    Join-Path $env:APPDATA "sops\\age"
} else {
    Join-Path $HOME ".config/sops/age"
}
$keysFile = Join-Path $keysDir "keys.txt"

if (Test-Path $keysFile) {
    Remove-Item -Force $keysFile
    Write-Host "Secrets locked."
} else {
    Write-Host "Secrets were not unlocked."
}
