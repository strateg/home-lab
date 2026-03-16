#!/bin/bash
set -e

KEYS_DIR="${HOME}/.config/sops/age"
KEYS_FILE="${KEYS_DIR}/keys.txt"
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEVKEY="${REPO_ROOT}/secrets/devkey.age"

if [ -f "$KEYS_FILE" ]; then
    echo "✓ Secrets already unlocked"
    exit 0
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
echo "  Run './scripts/lock-secrets.sh' when done"
