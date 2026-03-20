#!/bin/bash
set -e

KEYS_DIR="${HOME}/.config/sops/age"
KEYS_FILE="${KEYS_DIR}/keys.txt"
WORKSPACE_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
DEVKEY="${WORKSPACE_ROOT}/v5/projects/home-lab/secrets/devkey.age"

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
echo "  Run './v5/scripts/lock-secrets.sh' when done"
