#!/bin/bash
set -e

KEYS_DIR="${HOME}/.config/sops/age"
KEYS_FILE="${KEYS_DIR}/keys.txt"
WORKSPACE_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
DEVKEY="${WORKSPACE_ROOT}/projects/home-lab/secrets/devkey.age"

if [ -s "$KEYS_FILE" ]; then
    echo "✓ Secrets already unlocked"
    exit 0
fi

# Clean up empty/corrupt keys file from previous failed attempts
if [ -f "$KEYS_FILE" ] && [ ! -s "$KEYS_FILE" ]; then
    rm -f "$KEYS_FILE"
fi

if [ ! -f "$DEVKEY" ]; then
    echo "✗ Dev key not found: $DEVKEY"
    exit 1
fi

mkdir -p "$KEYS_DIR"
echo "Decrypting devkey..."
age -d "$DEVKEY" > "$KEYS_FILE"
chmod 600 "$KEYS_FILE"
echo "✓ Secrets unlocked"
echo "  Run './scripts/secrets/lock-secrets.sh' when done"
