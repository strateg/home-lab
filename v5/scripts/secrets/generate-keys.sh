#!/bin/bash
set -e

WORKSPACE_ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
SECRETS_DIR="${WORKSPACE_ROOT}/v5/projects/home-lab/secrets"

echo "=== SOPS/age Key Generator ==="
echo ""

# Generate devkey
echo "Generating devkey (daily operations)..."
age-keygen 2>/dev/null > /tmp/devkey.txt

DEVKEY_PUB=$(grep "public key:" /tmp/devkey.txt | cut -d: -f2 | tr -d ' ')
echo "  Public key: $DEVKEY_PUB"

echo ""
echo "Enter passphrase for DEVKEY (daily use, can be shorter):"
age -p -o "${SECRETS_DIR}/devkey.age" /tmp/devkey.txt
echo "$DEVKEY_PUB" > "${SECRETS_DIR}/devkey.pub"
shred -u /tmp/devkey.txt
echo "✓ devkey.age created"

echo ""

# Generate masterkey
echo "Generating masterkey (recovery only)..."
age-keygen 2>/dev/null > /tmp/masterkey.txt

MASTERKEY_PUB=$(grep "public key:" /tmp/masterkey.txt | cut -d: -f2 | tr -d ' ')
echo "  Public key: $MASTERKEY_PUB"

echo ""
echo "Enter passphrase for MASTERKEY (recovery, should be LONG):"
age -p -o "${SECRETS_DIR}/masterkey.age" /tmp/masterkey.txt
echo "$MASTERKEY_PUB" > "${SECRETS_DIR}/masterkey.pub"
shred -u /tmp/masterkey.txt
echo "✓ masterkey.age created"

# Update .sops.yaml
cat > "${SECRETS_DIR}/.sops.yaml" << EOF
creation_rules:
  # All YAML files encrypted with both keys (devkey + masterkey)
  # devkey: daily operations (shorter passphrase)
  # masterkey: recovery only (long passphrase, stored securely)
  - path_regex: \\.yaml\$
    age: >-
      ${DEVKEY_PUB},
      ${MASTERKEY_PUB}
EOF

echo ""
echo "✓ .sops.yaml updated with both keys"
echo ""
echo "=== Keys generated successfully ==="
echo ""
echo "Next steps:"
echo "  1. ./v5/scripts/secrets/unlock-secrets.sh"
echo "  2. Re-encrypt secrets: cd v5/projects/home-lab/secrets && for f in */*.yaml; do sops updatekeys -y \"\$f\"; done"
echo ""
echo "IMPORTANT: Store masterkey passphrase securely (paper, safe)!"
