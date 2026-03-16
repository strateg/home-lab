# Secrets Management Guide

**ADR:** [0072-unified-secrets-management-sops-age.md](../adr/0072-unified-secrets-management-sops-age.md)
**Status:** Implemented
**Last Updated:** 2026-03-16

---

## Overview

This repository uses **SOPS + age** for unified secrets management. All sensitive data (hardware identities, credentials, API tokens) is encrypted and stored in the `secrets/` directory.

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    OPERATOR MEMORY                          │
│                    ┌──────────────┐                         │
│                    │  Passphrase  │                         │
│                    └──────┬───────┘                         │
└───────────────────────────┼─────────────────────────────────┘
                            │ unlocks
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                    REPOSITORY (tracked)                     │
│                                                             │
│  secrets/master.key.age ◄──── age private key (encrypted)  │
│         │                                                   │
│         │ unlocks                                           │
│         ▼                                                   │
│  secrets/hardware/*.yaml ◄──── hardware identities          │
│  secrets/terraform/*.yaml ◄─── terraform credentials        │
│  secrets/ansible/*.yaml ◄───── ansible secrets              │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

**One passphrase unlocks everything.**

---

## Installation

### Prerequisites

Install `age` and `sops` on your machine:

#### Ubuntu/Debian

```bash
# age
sudo apt install age

# sops (from GitHub releases)
SOPS_VERSION="3.9.4"
wget "https://github.com/getsops/sops/releases/download/v${SOPS_VERSION}/sops-v${SOPS_VERSION}.linux.amd64" -O sops
chmod +x sops
sudo mv sops /usr/local/bin/sops

# Verify
age --version   # Expected: 1.x.x
sops --version  # Expected: 3.9.x
```

#### macOS

```bash
brew install age sops
```

#### Windows (WSL)

Same as Ubuntu/Debian instructions above.

---

## Daily Workflow

### 1. Unlock Secrets (Start of Session)

Before working with encrypted files:

```bash
./scripts/unlock-secrets.sh
# Enter your passphrase when prompted
```

This decrypts the master key to `~/.config/sops/age/keys.txt`.

**Verification:**
```bash
ls -la ~/.config/sops/age/keys.txt
# Should show the file exists with 600 permissions
```

### 2. Work with Encrypted Files

#### View decrypted content

```bash
sops -d secrets/hardware/rtr-mikrotik-chateau.yaml
```

#### Edit encrypted file

Opens in your `$EDITOR` with decrypted content, re-encrypts on save:

```bash
sops secrets/hardware/rtr-mikrotik-chateau.yaml
```

#### Encrypt a new file

```bash
# Create plaintext file
cat > secrets/terraform/new-service.yaml << 'EOF'
api_key: "your-secret-key"
password: "your-password"
EOF

# Encrypt in place
sops -e -i secrets/terraform/new-service.yaml

# Verify encryption
head -5 secrets/terraform/new-service.yaml
# Should show: api_key: ENC[AES256_GCM,data:...,iv:...,tag:...]
```

### 3. Lock Secrets (End of Session)

When done working:

```bash
./scripts/lock-secrets.sh
```

This securely deletes the plaintext key from `~/.config/sops/age/keys.txt`.

---

## Directory Structure

```
secrets/
├── .sops.yaml              # SOPS configuration (public key)
├── master.key.age          # Encrypted master key (passphrase-protected)
├── master.key.pub          # Public key (for reference)
├── hardware/               # Hardware identities
│   ├── rtr-mikrotik-chateau.yaml
│   ├── rtr-slate.yaml
│   ├── srv-gamayun.yaml
│   └── srv-orangepi5.yaml
├── terraform/              # Terraform credentials
│   └── .gitkeep
├── ansible/                # Ansible secrets
│   └── .gitkeep
└── bootstrap/              # Bootstrap secrets
    └── .gitkeep
```

---

## Collecting Hardware Identities

### MikroTik RouterOS

```bash
# SSH to router
ssh admin@192.168.88.1

# Get serial and MACs
/system routerboard print
/interface print detail
```

Copy values to secrets file:
```bash
sops secrets/hardware/rtr-mikrotik-chateau.yaml
```

### GL.iNet (OpenWrt)

```bash
ssh root@192.168.8.1

# Serial number
cat /tmp/sysinfo/model
uci get system.@system[0].hostname

# MAC addresses
cat /sys/class/net/eth0/address
cat /sys/class/net/wlan0/address
cat /sys/class/net/wlan1/address
```

### Proxmox Server

```bash
ssh root@10.0.99.1

# Serial number
dmidecode -s system-serial-number

# MAC addresses
ip -o link show | awk '{print $2, $(NF-2)}'
```

### Orange Pi / ARM SBC

```bash
ssh root@10.0.10.5

# Serial (CPU serial)
cat /proc/cpuinfo | grep Serial

# MAC addresses
ip -o link show | awk '{print $2, $(NF-2)}'
```

---

## Troubleshooting

### "age: error: no identity matched any of the recipients"

**Cause:** Secrets not unlocked or wrong key.

**Fix:**
```bash
./scripts/unlock-secrets.sh
# Enter correct passphrase
```

### "sops: no matching creation rule"

**Cause:** File not in `secrets/` directory or wrong extension.

**Fix:** Ensure file is in `secrets/**/*.yaml` path.

### Pre-commit hook fails: "ERROR: file is not encrypted!"

**Cause:** Attempting to commit plaintext YAML in `secrets/`.

**Fix:**
```bash
./scripts/unlock-secrets.sh
sops -e -i secrets/path/to/file.yaml
```

### Forgot passphrase

**Recovery:** Not possible. You must:
1. Generate new master key
2. Re-collect all secrets from source systems
3. Re-encrypt with new key

**Prevention:** Write passphrase on paper, store in secure physical location.

---

## Key Rotation

Rotate the master key periodically or if compromised:

```bash
# 1. Unlock with current passphrase
./scripts/unlock-secrets.sh

# 2. Generate new keypair
age-keygen > /tmp/new-master.key
NEW_PUB=$(grep "public key:" /tmp/new-master.key | cut -d: -f2 | tr -d ' ')

# 3. Re-encrypt all secrets with new key
for f in secrets/{hardware,terraform,ansible,bootstrap}/*.yaml; do
    [ -f "$f" ] || continue
    sops -d "$f" | sops -e --age "$NEW_PUB" /dev/stdin > "$f.new"
    mv "$f.new" "$f"
done

# 4. Update .sops.yaml
sed -i "s/age1.*/$NEW_PUB/" secrets/.sops.yaml

# 5. Encrypt new key with NEW passphrase
age -p -o secrets/master.key.age /tmp/new-master.key
echo "$NEW_PUB" > secrets/master.key.pub

# 6. Cleanup
shred -u /tmp/new-master.key

# 7. Lock old session
./scripts/lock-secrets.sh

# 8. Commit
git add secrets/
git commit -m "chore(secrets): rotate master key"
```

---

## CI/CD Integration

### GitHub Actions

Add single secret `MASTER_KEY_PASSPHRASE` to repository secrets.

```yaml
# .github/workflows/deploy.yml
env:
  MASTER_KEY_PASSPHRASE: ${{ secrets.MASTER_KEY_PASSPHRASE }}

jobs:
  deploy:
    steps:
      - uses: actions/checkout@v4

      - name: Install age and sops
        run: |
          sudo apt-get update && sudo apt-get install -y age
          wget -q https://github.com/getsops/sops/releases/download/v3.9.4/sops-v3.9.4.linux.amd64 -O sops
          chmod +x sops && sudo mv sops /usr/local/bin/

      - name: Unlock secrets
        run: |
          mkdir -p ~/.config/sops/age
          echo "$MASTER_KEY_PASSPHRASE" | age -d secrets/master.key.age > ~/.config/sops/age/keys.txt
          chmod 600 ~/.config/sops/age/keys.txt

      - name: Use secrets
        run: |
          sops -d secrets/terraform/proxmox.yaml > /tmp/proxmox.yaml
          # ... use decrypted secrets

      - name: Cleanup
        if: always()
        run: rm -f ~/.config/sops/age/keys.txt /tmp/*.yaml
```

---

## Best Practices

1. **Lock secrets when not in use**
   ```bash
   ./scripts/lock-secrets.sh
   ```

2. **Never commit plaintext secrets**
   - Pre-commit hook will block unencrypted files
   - Always verify with `head -5 secrets/file.yaml` before commit

3. **Use `sops` command for editing**
   - Never manually edit encrypted files
   - Use `sops secrets/file.yaml` to edit

4. **Backup passphrase physically**
   - Write on paper
   - Store in safe/secure location
   - Do NOT store digitally

5. **Rotate keys periodically**
   - Recommended: annually or after team changes
   - Required: immediately if passphrase compromised

---

## Quick Reference

| Task | Command |
|------|---------|
| Unlock secrets | `./scripts/unlock-secrets.sh` |
| Lock secrets | `./scripts/lock-secrets.sh` |
| View file | `sops -d secrets/path/file.yaml` |
| Edit file | `sops secrets/path/file.yaml` |
| Encrypt new file | `sops -e -i secrets/path/file.yaml` |
| Check status | `ls ~/.config/sops/age/keys.txt` |

---

## References

- [SOPS Documentation](https://github.com/getsops/sops)
- [age Encryption](https://github.com/FiloSottile/age)
- [ADR 0072: Unified Secrets Management](../adr/0072-unified-secrets-management-sops-age.md)
