# Secrets Management Guide

**ADR:** [0072-unified-secrets-management-sops-age.md](../adr/0072-unified-secrets-management-sops-age.md), [0073-field-annotations-and-secret-conflict-resolution.md](../adr/0073-field-annotations-and-secret-conflict-resolution.md)
**Status:** Implemented
**Last Updated:** 2026-03-18

---

## Overview

This repository uses **SOPS + age** for unified secrets management. All sensitive data (hardware identities, credentials, API tokens) is encrypted and stored in the `v5/secrets/` directory.

At compile time, secrets are merged into instance rows by the plugin pipeline:

- `base.compiler.annotation_resolver` parses field annotations and publishes annotation metadata.
- `base.compiler.instance_rows` decrypts side-car files and resolves secret fields in `inject/strict`.

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
│  v5/secrets/devkey.age ◄────── age private key (encrypted)    │
│         │                                                   │
│         │ unlocks                                           │
│         ▼                                                   │
│  v5/secrets/instances/*.yaml ◄── instance secrets (side-car)  │
│  v5/secrets/terraform/*.yaml ◄── terraform credentials        │
│  v5/secrets/ansible/*.yaml ◄──── ansible secrets              │
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

#### Windows (PowerShell)

```powershell
winget install --id SecretsOPerationS.SOPS -e --accept-package-agreements --accept-source-agreements
winget install --id str4d.rage -e --accept-package-agreements --accept-source-agreements

sops --version
rage --version
rage-keygen --version
```

---

## Daily Workflow

### 1. Unlock Secrets (Start of Session)

Before working with encrypted files:

```bash
./v5/scripts/unlock-secrets.sh
# Enter your passphrase when prompted
```

```powershell
./v5/scripts/unlock-secrets.ps1
```

This decrypts the devkey to the default SOPS age key path (`~/.config/sops/age/keys.txt` on Linux/macOS, `%APPDATA%\sops\age\keys.txt` on Windows).

**Verification:**
```bash
ls -la ~/.config/sops/age/keys.txt
# Should show the file exists with 600 permissions
```

### 2. Work with Encrypted Files

#### View decrypted content

```bash
sops -d v5/secrets/instances/rtr-mikrotik-chateau.yaml
```

#### Edit encrypted file

Opens in your `$EDITOR` with decrypted content, re-encrypts on save:

```bash
sops v5/secrets/instances/rtr-mikrotik-chateau.yaml
```

#### Encrypt a new file

```bash
# Create plaintext file
cat > v5/secrets/terraform/new-service.yaml << 'EOF'
api_key: "your-secret-key"
password: "your-password"
EOF

# Encrypt in place
sops -e -i v5/secrets/terraform/new-service.yaml

# Verify encryption
head -5 v5/secrets/terraform/new-service.yaml
# Should show: api_key: ENC[AES256_GCM,data:...,iv:...,tag:...]
```

### 3. Lock Secrets (End of Session)

When done working:

```bash
./v5/scripts/lock-secrets.sh
```

```powershell
./v5/scripts/lock-secrets.ps1
```

This removes the plaintext key from the default SOPS age key path.

---

## Directory Structure

```
v5/secrets/
├── .sops.yaml              # SOPS configuration (age recipients)
├── devkey.age              # Dev key (daily operations, passphrase-protected)
├── devkey.pub              # Dev public key
├── masterkey.age           # Recovery key (offline backup, passphrase-protected)
├── masterkey.pub           # Recovery public key
├── instances/              # Instance-level secrets (side-car files)
│   ├── rtr-mikrotik-chateau.yaml
│   ├── rtr-slate.yaml
│   ├── srv-gamayun.yaml
│   └── srv-orangepi5.yaml
├── terraform/              # Terraform credentials
│   ├── proxmox.yaml
│   └── mikrotik.yaml
├── ansible/                # Ansible secrets
│   └── vault.yaml
└── bootstrap/              # Bootstrap secrets
```

Each file in `v5/secrets/instances/` corresponds to an instance in `v5/topology/instances/` by matching `instance` ID.

Naming rule:

- side-car file name MUST be exactly `<instance>.yaml`
- for `instance: rtr-slate` the side-car path is `v5/secrets/instances/rtr-slate.yaml`

Secret resolution rule:

- use annotations near the field (`@secret`, `@required_secret:<type>`, `@optional_secret:<type>`)
- compiler resolves annotated secret paths from decrypted side-car payload
- deep merge is generic (no hardcoded domain paths)
- side-car may materialize missing nested keys during merge

Conflict and validation policy:

- `E7212`: plaintext value conflicts with side-car value on same path
- `E7211`: secret annotation/placeholder unresolved in strict semantics
- `E7213`: decrypted secret value does not satisfy typed annotation format (for example `@optional_secret:mac`)

## Secret Annotations (ADR 0073)

Use one annotation token per field:

- `@secret` - secret value without explicit type
- `@required_secret:<type>` - required secret with typed format
- `@optional_secret:<type>` - optional secret with typed format

Examples:

```yaml
hardware_identity:
  serial_number: "@secret"
  mac_addresses:
    wan: "@optional_secret:mac"
```

Typed formats are resolved via `v5/topology-tools/data/instance-field-formats.yaml`.

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
sops v5/secrets/instances/rtr-mikrotik-chateau.yaml
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
./v5/scripts/unlock-secrets.sh
# Enter correct passphrase
```

### "sops: no matching creation rule"

**Cause:** File not in `v5/secrets/` directory or wrong extension.

**Fix:** Ensure file is in `v5/secrets/**/*.yaml` path.

### Pre-commit hook fails: "ERROR: file is not encrypted!"

**Cause:** Attempting to commit plaintext YAML in `v5/secrets/`.

**Fix:**
```bash
./v5/scripts/unlock-secrets.sh
sops -e -i v5/secrets/path/to/file.yaml
```

### Forgot passphrase

**Recovery:** Not possible. You must:
1. Generate new devkey
2. Re-collect all secrets from source systems
3. Re-encrypt with new key

**Prevention:** Write passphrase on paper, store in secure physical location.

---

## Key Rotation

Rotate the devkey periodically or if compromised:

```bash
# 1. Unlock with current passphrase
./v5/scripts/unlock-secrets.sh

# 2. Generate new keypair
age-keygen > /tmp/new-devkey.key
NEW_PUB=$(grep "public key:" /tmp/new-devkey.key | cut -d: -f2 | tr -d ' ')

# 3. Re-encrypt all secrets with new key
for f in v5/secrets/{instances,terraform,ansible,bootstrap}/*.yaml; do
    [ -f "$f" ] || continue
    sops -d "$f" | sops -e --age "$NEW_PUB" /dev/stdin > "$f.new"
    mv "$f.new" "$f"
done

# 4. Update .sops.yaml
sed -i "s/age1.*/$NEW_PUB/" v5/secrets/.sops.yaml

# 5. Encrypt new key with NEW passphrase
age -p -o v5/secrets/devkey.age /tmp/new-devkey.key
echo "$NEW_PUB" > v5/secrets/devkey.pub

# 6. Cleanup
shred -u /tmp/new-devkey.key

# 7. Lock old session
./v5/scripts/lock-secrets.sh

# 8. Commit
git add v5/secrets/
git commit -m "chore(secrets): rotate devkey"
```

---

## CI/CD Integration

### GitHub Actions

Add single secret `DEVKEY_PASSPHRASE` to repository secrets.

```yaml
# .github/workflows/deploy.yml
env:
  DEVKEY_PASSPHRASE: ${{ secrets.DEVKEY_PASSPHRASE }}

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
          echo "$DEVKEY_PASSPHRASE" | age -d v5/secrets/devkey.age > ~/.config/sops/age/keys.txt
          chmod 600 ~/.config/sops/age/keys.txt

      - name: Compile with secrets
        run: |
          python v5/topology-tools/compile-topology.py --secrets-mode inject

      - name: Cleanup
        if: always()
        run: rm -f ~/.config/sops/age/keys.txt
```

---

## Best Practices

1. **Lock secrets when not in use**
   ```bash
   ./v5/scripts/lock-secrets.sh
   ```

2. **Never commit plaintext secrets**
   - Pre-commit hook will block unencrypted files
   - Always verify with `head -5 v5/secrets/file.yaml` before commit

3. **Use `sops` command for editing**
   - Never manually edit encrypted files
   - Use `sops v5/secrets/file.yaml` to edit

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
| Unlock secrets | `./v5/scripts/unlock-secrets.sh` or `./v5/scripts/unlock-secrets.ps1` |
| Lock secrets | `./v5/scripts/lock-secrets.sh` or `./v5/scripts/lock-secrets.ps1` |
| View file | `sops -d v5/secrets/instances/rtr-mikrotik-chateau.yaml` |
| Edit file | `sops v5/secrets/instances/rtr-mikrotik-chateau.yaml` |
| Encrypt new file | `sops -e -i v5/secrets/instances/new-device.yaml` |
| Check status | `ls ~/.config/sops/age/keys.txt` |
| Compile with secrets | `python v5/topology-tools/compile-topology.py --secrets-mode inject` |
| Compile with strict secret policy | `python v5/topology-tools/compile-topology.py --secrets-mode strict` |
| Compile without secrets | `python v5/topology-tools/compile-topology.py --secrets-mode passthrough` |
| Generate Terraform tfvars | `python v5/scripts/generate-tfvars.py all` |
| Cleanup Terraform tfvars | `python v5/scripts/generate-tfvars.py all --cleanup` |

---

## References

- [SOPS Documentation](https://github.com/getsops/sops)
- [age Encryption](https://github.com/FiloSottile/age)
- [ADR 0072: Unified Secrets Management](../adr/0072-unified-secrets-management-sops-age.md)
