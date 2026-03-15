#!/bin/bash
set -e

KEYS_DIR="${HOME}/.config/sops/age"
KEYS_FILE="${KEYS_DIR}/keys.txt"
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
MASTER_KEY="${REPO_ROOT}/secrets/master.key.age"

if [ -f "$KEYS_FILE" ]; then
    echo "✓ Secrets already unlocked"
    exit 0
fi

if [ ! -f "$MASTER_KEY" ]; then
    echo "✗ Master key not found: $MASTER_KEY"
    exit 1
fi

mkdir -p "$KEYS_DIR"
echo "Decrypting master key..."
age -d "$MASTER_KEY" > "$KEYS_FILE"
chmod 600 "$KEYS_FILE"
echo "✓ Secrets unlocked"
echo "  Run './scripts/lock-secrets.sh' when done"
