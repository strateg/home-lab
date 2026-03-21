#!/bin/bash
set -e

# Recovery unlock script - uses masterkey instead of devkey
# Use this ONLY if devkey passphrase is lost

KEYS_DIR="${HOME}/.config/sops/age"
KEYS_FILE="${KEYS_DIR}/keys.txt"
WORKSPACE_ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
MASTERKEY="${WORKSPACE_ROOT}/v5/projects/home-lab/secrets/masterkey.age"

if [ -f "$KEYS_FILE" ]; then
    echo "⚠ Keys file already exists: $KEYS_FILE"
    echo "  Remove it first if you want to use masterkey recovery"
    exit 1
fi

if [ ! -f "$MASTERKEY" ]; then
    echo "✗ Master key not found: $MASTERKEY"
    exit 1
fi

mkdir -p "$KEYS_DIR"
echo "⚠ RECOVERY MODE - Decrypting masterkey..."
age -d "$MASTERKEY" > "$KEYS_FILE"
chmod 600 "$KEYS_FILE"
echo "✓ Secrets unlocked (via masterkey)"
echo "  Run './v5/scripts/secrets/lock-secrets.sh' when done"
