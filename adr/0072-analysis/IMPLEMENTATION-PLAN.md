# ADR 0072 Implementation Plan

**ADR:** `adr/0072-unified-secrets-management-sops-age.md`
**Date:** 2026-03-15
**Status:** Phase 0 - Tooling Setup

---

## Overview

Migrate all secrets to SOPS + age encryption, eliminating:
- Ansible Vault
- Untracked `local/` secret files
- Placeholder hardware identities

---

## Phase 0: Tooling Setup

### 0.1 Install Dependencies

**Operator machine:**
```bash
# macOS
brew install sops age

# Ubuntu/Debian
sudo apt install age
# SOPS from GitHub releases:
wget https://github.com/getsops/sops/releases/download/v3.8.1/sops-v3.8.1.linux.amd64
sudo mv sops-v3.8.1.linux.amd64 /usr/local/bin/sops
sudo chmod +x /usr/local/bin/sops

# Verify
sops --version
age --version
```

### 0.2 Generate age Key

```bash
# Create key directory
mkdir -p ~/.config/sops/age

# Generate keypair
age-keygen -o ~/.config/sops/age/keys.txt

# Output shows public key:
# Public key: age1xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

**CRITICAL:** Backup `~/.config/sops/age/keys.txt` securely.

### 0.3 Create Repository Structure

```bash
mkdir -p secrets/{hardware,terraform,ansible,bootstrap}
```

### 0.4 Create SOPS Configuration

**File:** `secrets/.sops.yaml`

```yaml
creation_rules:
  # Hardware identities
  - path_regex: hardware/.*\.yaml$
    age: >-
      age1YOUR_PUBLIC_KEY_HERE

  # Terraform secrets
  - path_regex: terraform/.*\.yaml$
    age: >-
      age1YOUR_PUBLIC_KEY_HERE

  # Ansible secrets
  - path_regex: ansible/.*\.yaml$
    age: >-
      age1YOUR_PUBLIC_KEY_HERE

  # Bootstrap secrets
  - path_regex: bootstrap/.*\.yaml$
    age: >-
      age1YOUR_PUBLIC_KEY_HERE
```

### 0.5 Create Recipients File

**File:** `secrets/age-recipients.txt`

```text
# SOPS age recipients
# Add public keys here for multi-user access
# Format: age1... # username/purpose

age1YOUR_PUBLIC_KEY_HERE # primary operator
```

### 0.6 Update .gitignore

```gitignore
# age private keys (NEVER commit)
*.age-key
keys.txt

# Decrypted secret files (temporary)
secrets/**/*.dec.yaml
secrets/**/*.dec.json
.work/*.tfvars
```

### 0.7 Add Pre-commit Hook

**File:** `.pre-commit-config.yaml` (update)

```yaml
repos:
  - repo: https://github.com/getsops/sops
    rev: v3.8.1
    hooks:
      - id: sops-diff
        name: Detect unencrypted secrets
        entry: bash -c 'for f in secrets/**/*.yaml; do sops -d "$f" > /dev/null 2>&1 || echo "WARNING: $f may not be encrypted"; done'
        language: system
        files: ^secrets/.*\.yaml$
```

### 0.8 Verification

```bash
# Create test secret
echo "test_secret: hello_world" > secrets/test.yaml

# Encrypt
sops -e -i secrets/test.yaml

# Verify encryption
cat secrets/test.yaml  # Should show ENC[AES256_GCM,...]

# Decrypt
sops -d secrets/test.yaml  # Should show plaintext

# Cleanup
rm secrets/test.yaml
```

---

## Phase 1: Hardware Identities

### 1.1 Create Hardware Secret Files

**Template:** `secrets/hardware/DEVICE.yaml`

```yaml
# secrets/hardware/rtr-mikrotik-chateau.yaml (before encryption)
instance: rtr-mikrotik-chateau
hardware_identity:
  serial_number: "ACTUAL_SERIAL"
  mac_addresses:
    ether1: "AA:BB:CC:DD:EE:01"
    ether2: "AA:BB:CC:DD:EE:02"
    ether3: "AA:BB:CC:DD:EE:03"
    ether4: "AA:BB:CC:DD:EE:04"
    ether5: "AA:BB:CC:DD:EE:05"
    wlan1_5ghz: "AA:BB:CC:DD:EE:11"
    wlan2_2_4ghz: "AA:BB:CC:DD:EE:12"
    lte1: "AA:BB:CC:DD:EE:21"
```

### 1.2 Collect Hardware Data

**MikroTik Chateau (192.168.88.1):**
```bash
ssh admin@192.168.88.1 '/system routerboard print; /interface print detail'
```

**GL.iNet Slate (192.168.8.1):**
```bash
ssh root@192.168.8.1 'cat /sys/class/net/*/address; cat /tmp/sysinfo/model'
```

**Proxmox srv-gamayun:**
```bash
ssh root@10.0.99.1 'dmidecode -s system-serial-number; ip -o link show'
```

**Orange Pi 5:**
```bash
ssh root@10.0.10.5 'cat /proc/cpuinfo | grep Serial; ip -o link show'
```

### 1.3 Encrypt Hardware Files

```bash
cd secrets/hardware

# Create and encrypt each file
sops -e -i rtr-mikrotik-chateau.yaml
sops -e -i rtr-slate.yaml
sops -e -i srv-gamayun.yaml
sops -e -i srv-orangepi5.yaml
```

### 1.4 Update Instance Files

Replace placeholders with secret references:

```yaml
# v5/topology/instances/l1_devices/rtr-mikrotik-chateau.yaml
instance: rtr-mikrotik-chateau
# ...
hardware_identity:
  _sops_ref: secrets/hardware/rtr-mikrotik-chateau.yaml
```

### 1.5 Implement Compiler Secret Resolution

**File:** `v5/topology-tools/plugins/compilers/sops_secret_resolver.py`

Plugin that:
1. Finds `_sops_ref` fields in instances
2. Decrypts referenced SOPS files
3. Merges decrypted values into effective model

---

## Phase 2: Terraform Secrets

### 2.1 Create Terraform Secret Files

```yaml
# secrets/terraform/proxmox.yaml (before encryption)
proxmox:
  api_url: "https://10.0.99.1:8006/api2/json"
  api_token_id: "terraform@pve!terraform"
  api_token_secret: "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
  ssh_password: "actual_password"
```

```yaml
# secrets/terraform/mikrotik.yaml (before encryption)
mikrotik:
  host: "192.168.88.1"
  username: "admin"
  password: "actual_password"
```

### 2.2 Encrypt and Commit

```bash
sops -e -i secrets/terraform/proxmox.yaml
sops -e -i secrets/terraform/mikrotik.yaml
git add secrets/terraform/
git commit -m "feat(secrets): add encrypted Terraform credentials"
```

### 2.3 Update Makefile

```makefile
# deploy/Makefile
.PHONY: terraform-proxmox-plan
terraform-proxmox-plan:
	@sops -d secrets/terraform/proxmox.yaml | \
		yq -o=json | \
		jq -r 'to_entries | map("\(.key) = \"\(.value)\"") | .[]' > .work/proxmox.auto.tfvars
	cd .work/native/terraform/proxmox && terraform plan
	@rm -f .work/proxmox.auto.tfvars
```

---

## Phase 3: Ansible Secrets

### 3.1 Convert Ansible Vault to SOPS

```bash
# Decrypt existing vault
ansible-vault decrypt ansible/group_vars/all/vault.yml --output=secrets/ansible/vault.yaml

# Encrypt with SOPS
sops -e -i secrets/ansible/vault.yaml

# Remove old vault file
rm ansible/group_vars/all/vault.yml
```

### 3.2 Update Ansible Configuration

**Option A: vars_files with lookup**

```yaml
# ansible/playbooks/site.yml
- hosts: all
  vars_files:
    - "{{ lookup('community.sops.sops', '../../secrets/ansible/vault.yaml') }}"
```

**Option B: Environment variable**

```bash
export ANSIBLE_VARS_PLUGINS=community.sops.vars
ansible-playbook playbooks/site.yml
```

### 3.3 Remove Vault Password Workflow

```bash
rm ansible/.vault_pass
# Update .gitignore to remove vault references
```

---

## Phase 4: Cleanup

### 4.1 Update ADR Statuses

- ADR 0051: Add "Secret storage superseded by ADR 0072"
- ADR 0054: Clarify `local/` is for non-secrets only

### 4.2 Update Documentation

- CLAUDE.md: Add `secrets/` directory description
- README.md: Add SOPS setup instructions

### 4.3 Remove Deprecated Patterns

```bash
# Remove from .gitignore (no longer needed)
# *.vault
# .vault_pass
# .vault_password
```

---

## Verification Checklist

- [ ] `age --version` works
- [ ] `sops --version` works
- [ ] `secrets/.sops.yaml` configured with correct public key
- [ ] `sops -d secrets/hardware/rtr-mikrotik-chateau.yaml` decrypts
- [ ] Compiler resolves `_sops_ref` fields
- [ ] `make terraform-proxmox-plan` works with SOPS
- [ ] Ansible playbooks work without vault password
- [ ] Pre-commit hook catches unencrypted files
- [ ] CI/CD can decrypt with `SOPS_AGE_KEY` secret

---

## Rollback

If SOPS migration fails:

1. Keep `local/` files until Phase 2 verified
2. Keep Ansible Vault until Phase 3 verified
3. Revert `_sops_ref` to placeholder values if needed

Each phase is independently reversible.
