#!/bin/bash
set -e

KEYS_FILE="${HOME}/.config/sops/age/keys.txt"

if [ -f "$KEYS_FILE" ]; then
    shred -u "$KEYS_FILE" 2>/dev/null || rm -f "$KEYS_FILE"
    echo "✓ Secrets locked"
else
    echo "✓ Secrets were not unlocked"
fi
