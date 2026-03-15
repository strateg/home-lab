# ADR 0072: Unified Secrets Management with SOPS and age

**Date:** 2026-03-15
**Status:** Proposed
**Supersedes:** ADR 0051 (secret storage sections), ADR 0054 (secret-bearing local inputs)

---

## Context

The repository currently uses multiple inconsistent mechanisms for secret storage:

| Mechanism | Location | Use Case | Problems |
|-----------|----------|----------|----------|
| Ansible Vault | `ansible/group_vars/*/vault.yml` | Ansible secrets | Requires vault password at every ansible run |
| local/ directory | `local/terraform/*.tfvars` | Terraform credentials | Not versioned, not portable |
| .gitignore patterns | Various | Ad-hoc secret exclusion | No encryption, data loss risk |
| Placeholder values | `v5/topology/instances/` | Hardware identities | Blocks production deployment |

This creates operational problems:

1. **No single source of truth** for secret management
2. **Key management fragmentation** - different passwords/keys per mechanism
3. **Hardware identities cannot be committed** - MAC addresses, serial numbers remain placeholders
4. **Ansible Vault requires password** at compile time if secrets are needed
5. **local/ files are not versioned** - risk of data loss, not portable across machines

### Hardware Identity Problem

Instance files contain sensitive hardware identifiers:

```yaml
# Current state - placeholders
hardware_identity:
  serial_number: <TODO_SERIAL_NUMBER>
  mac_addresses:
    ether1: "02:AA:20:00:00:01"  # Fake placeholder
```

These must be real values for production deployment but cannot be committed in plaintext to a public repository.

---

## Decision

### 1. Adopt SOPS + age as the Single Secret Management Solution

All secrets in the repository will be managed through [SOPS](https://github.com/getsops/sops) with [age](https://github.com/FiloSottile/age) encryption.

**Why SOPS + age:**

| Feature | SOPS + age | Ansible Vault | git-crypt |
|---------|------------|---------------|-----------|
| Per-file encryption | Yes | Yes | Yes |
| Selective field encryption | Yes | No | No |
| Key rotation | Simple | Manual re-encrypt | Complex |
| No GPG required | Yes | Yes | No |
| CI/CD friendly | Yes | Yes | Limited |
| Diff-friendly | Yes (keys visible) | No | No |
| Multi-recipient | Yes | No | Yes |

### 2. Deprecate All Other Secret Mechanisms

| Current Mechanism | Migration Target | Timeline |
|-------------------|------------------|----------|
| Ansible Vault | SOPS-encrypted YAML | Phase 2 |
| `local/*.tfvars` (secrets only) | SOPS-encrypted files | Phase 2 |
| Placeholder hardware IDs | SOPS-encrypted instance overlays | Phase 1 |

**Note:** `local/` directory remains for non-secret operator preferences (e.g., feature flags, environment selection). Only secret-bearing content migrates to SOPS.

### 3. Repository Secret Structure

```
secrets/                              # SOPS-encrypted files root
├── .sops.yaml                        # SOPS configuration (tracked)
├── age-recipients.txt                # Public keys for encryption (tracked)
├── hardware/                         # Hardware identities
│   ├── rtr-mikrotik-chateau.yaml    # Encrypted MAC/serial
│   ├── rtr-slate.yaml
│   ├── srv-gamayun.yaml
│   └── srv-orangepi5.yaml
├── terraform/                        # Terraform secrets
│   ├── proxmox.yaml                 # API tokens, passwords
│   └── mikrotik.yaml                # RouterOS credentials
├── ansible/                          # Ansible secrets
│   └── vault.yaml                   # Migrated from Ansible Vault
└── bootstrap/                        # Bootstrap secrets
    └── proxmox-root-password.yaml
```

### 4. SOPS Configuration

```yaml
# secrets/.sops.yaml
creation_rules:
  - path_regex: \.yaml$
    age: >-
      age1xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
    # Additional recipients can be added for team access
```

### 5. Key Management: Password-Protected Master Key in Repository

**Problem:** Where to store the age private key?
- External storage (1Password, etc.) creates dependency
- `~/.config/sops/age/keys.txt` is not versioned, risk of loss
- Different keys per machine breaks portability

**Solution:** Store the age private key IN the repository, encrypted with a passphrase.

#### 5.1 Two-Level Encryption Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    OPERATOR MEMORY                          │
│                                                             │
│                    ┌──────────────┐                         │
│                    │  Passphrase  │                         │
│                    └──────┬───────┘                         │
│                           │                                 │
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

#### 5.2 Repository Key Structure

```
secrets/
├── .sops.yaml              # SOPS configuration (tracked)
├── master.key.age          # Passphrase-encrypted age private key (tracked)
├── master.key.pub          # age public key (tracked, for reference)
├── hardware/               # SOPS-encrypted with master key
├── terraform/              # SOPS-encrypted with master key
├── ansible/                # SOPS-encrypted with master key
└── bootstrap/              # SOPS-encrypted with master key
```

| File | Encryption | Tracked |
|------|------------|---------|
| `master.key.age` | age passphrase (`age -p`) | Yes |
| `master.key.pub` | None (public) | Yes |
| `*.yaml` in subdirs | SOPS + age (master key) | Yes |
| Passphrase | Operator memory | No |

#### 5.3 Key Generation (One-Time Setup)

```bash
# 1. Generate age keypair
age-keygen > /tmp/master.key
# Output:
# # created: 2026-03-15T12:00:00Z
# # public key: age1xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
# AGE-SECRET-KEY-1XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX

# 2. Extract public key
grep "public key:" /tmp/master.key | cut -d: -f2 | tr -d ' ' > secrets/master.key.pub

# 3. Encrypt private key with passphrase
age -p -o secrets/master.key.age /tmp/master.key
# Enter passphrase (REMEMBER THIS!)

# 4. Securely delete plaintext key
shred -u /tmp/master.key

# 5. Verify decryption works
age -d secrets/master.key.age
# Enter passphrase → should show key content
```

#### 5.4 Daily Workflow: Unlocking Secrets

**Option A: Unlock once per session**
```bash
# Decrypt master key to temporary location
age -d secrets/master.key.age > ~/.config/sops/age/keys.txt
# Enter passphrase once

# Now all sops commands work
sops -d secrets/hardware/rtr-mikrotik-chateau.yaml

# End of session: remove plaintext key
rm ~/.config/sops/age/keys.txt
```

**Option B: Unlock script (recommended)**
```bash
#!/bin/bash
# scripts/unlock-secrets.sh

KEYS_FILE="${SOPS_AGE_KEY_FILE:-$HOME/.config/sops/age/keys.txt}"

if [ -f "$KEYS_FILE" ]; then
    echo "Secrets already unlocked"
    exit 0
fi

mkdir -p "$(dirname "$KEYS_FILE")"
age -d secrets/master.key.age > "$KEYS_FILE"
chmod 600 "$KEYS_FILE"
echo "Secrets unlocked. Run 'lock-secrets.sh' when done."
```

```bash
#!/bin/bash
# scripts/lock-secrets.sh

KEYS_FILE="${SOPS_AGE_KEY_FILE:-$HOME/.config/sops/age/keys.txt}"
[ -f "$KEYS_FILE" ] && shred -u "$KEYS_FILE"
echo "Secrets locked."
```

**Option C: Environment variable (CI/CD)**
```bash
# Passphrase in env, decrypt key inline
export SOPS_AGE_KEY=$(echo "$MASTER_KEY_PASSPHRASE" | age -d secrets/master.key.age)
sops -d secrets/hardware/rtr-mikrotik-chateau.yaml
```

#### 5.5 CI/CD Integration

GitHub Actions with single secret:

```yaml
# .github/workflows/deploy.yml
env:
  MASTER_KEY_PASSPHRASE: ${{ secrets.MASTER_KEY_PASSPHRASE }}

jobs:
  deploy:
    steps:
      - name: Unlock secrets
        run: |
          export SOPS_AGE_KEY=$(echo "$MASTER_KEY_PASSPHRASE" | age -d secrets/master.key.age)
          sops -d secrets/terraform/proxmox.yaml > /tmp/proxmox.yaml
```

#### 5.6 Passphrase Requirements

| Requirement | Minimum |
|-------------|---------|
| Length | 20+ characters |
| Entropy | High (passphrase, not password) |
| Storage | Human memory only (no digital copies) |
| Backup | Printed paper in secure location |

**Recommended format:** 5-6 random words (diceware)
```
correct-horse-battery-staple-router-network
```

#### 5.7 Key Rotation

```bash
# 1. Decrypt all secrets with old key
./scripts/unlock-secrets.sh  # old passphrase

# 2. Generate new keypair
age-keygen > /tmp/new-master.key

# 3. Re-encrypt all secrets with new key
for f in secrets/{hardware,terraform,ansible,bootstrap}/*.yaml; do
    sops -d "$f" | sops -e --age "$(cat /tmp/new-master.key.pub)" /dev/stdin > "$f.new"
    mv "$f.new" "$f"
done

# 4. Update SOPS config with new public key
# Edit secrets/.sops.yaml

# 5. Encrypt new key with new passphrase
age -p -o secrets/master.key.age /tmp/new-master.key

# 6. Update public key reference
grep "public key:" /tmp/new-master.key | cut -d: -f2 | tr -d ' ' > secrets/master.key.pub

# 7. Cleanup
shred -u /tmp/new-master.key

# 8. Commit
git add secrets/
git commit -m "chore(secrets): rotate master key"
```

#### 5.8 Recovery Scenarios

| Scenario | Recovery |
|----------|----------|
| Forgot passphrase | Cannot recover. Generate new key, re-collect all secrets. |
| Lost repo access | Clone from remote, enter passphrase. |
| Compromised passphrase | Rotate key immediately (5.7). |
| New team member | Share passphrase securely (in person, Signal, etc.). |

### 6. Encrypted File Format

SOPS encrypts values while keeping keys visible (diff-friendly):

```yaml
# secrets/hardware/rtr-mikrotik-chateau.yaml (encrypted)
hardware_identity:
    serial_number: ENC[AES256_GCM,data:xxxxx,iv:xxxxx,tag:xxxxx]
    mac_addresses:
        ether1: ENC[AES256_GCM,data:xxxxx,iv:xxxxx,tag:xxxxx]
        ether2: ENC[AES256_GCM,data:xxxxx,iv:xxxxx,tag:xxxxx]
sops:
    age:
        - recipient: age1xxxxxxxxx
          enc: |
            -----BEGIN AGE ENCRYPTED FILE-----
            ...
```

### 7. Compile-Time Secret Resolution

The v5 compiler will support secret injection:

```bash
# Option A: Decrypt at compile time
sops -d secrets/hardware/rtr-mikrotik-chateau.yaml | \
  python3 v5/topology-tools/compile-topology.py --hardware-overlay -

# Option B: Compiler with SOPS integration
python3 v5/topology-tools/compile-topology.py --secrets-dir secrets/
```

Instance files reference secrets by path:

```yaml
# v5/topology/instances/l1_devices/rtr-mikrotik-chateau.yaml
instance: rtr-mikrotik-chateau
hardware_identity:
  _secret_ref: secrets/hardware/rtr-mikrotik-chateau.yaml
```

### 8. Ansible Integration

Replace Ansible Vault with SOPS:

```yaml
# ansible/playbooks/site.yml
- hosts: all
  vars_files:
    - "{{ lookup('pipe', 'sops -d ../../secrets/ansible/vault.yaml') }}"
```

Or use the [sops-ansible](https://github.com/mozilla/sops#ansible) community integration.

### 9. Terraform Integration

Generate tfvars from SOPS at apply time:

```bash
# deploy/Makefile
terraform-apply-proxmox:
    sops -d secrets/terraform/proxmox.yaml > .work/terraform.tfvars
    terraform -chdir=.work/native/terraform/proxmox apply -var-file=terraform.tfvars
    rm .work/terraform.tfvars
```

### 10. CI/CD Integration

For GitHub Actions:

```yaml
# .github/workflows/deploy.yml
env:
  SOPS_AGE_KEY: ${{ secrets.SOPS_AGE_KEY }}

steps:
  - name: Decrypt secrets
    run: sops -d secrets/terraform/proxmox.yaml > /tmp/secrets.yaml
```

---

## Consequences

### Positive

1. **Single source of truth** for all secrets
2. **Versioned secrets** - hardware identities tracked in git (encrypted)
3. **Fully portable** - clone repo, enter passphrase, deploy (no external key storage)
4. **Auditable** - git history shows when secrets changed (not what)
5. **One passphrase** - memorize one passphrase instead of managing multiple keys
6. **No key loss risk** - master key is in repository, only passphrase needed
7. **Diff-friendly** - YAML keys visible in diffs
8. **CI/CD ready** - single secret (passphrase) to configure

### Negative

1. **New tooling** - operators must install `sops` and `age`
2. **Migration effort** - existing Ansible Vault files must be converted
3. **Passphrase critical** - forgetting passphrase = re-collect all secrets
4. **Learning curve** - team must learn SOPS workflow
5. **Session unlock** - must decrypt master key each session

### Risks and Mitigation

| Risk | Mitigation |
|------|------------|
| Forgot passphrase | Print passphrase on paper, store in secure physical location |
| Passphrase compromised | Rotate master key immediately (documented procedure) |
| Accidental plaintext commit | Pre-commit hook validates encryption |
| SOPS/age version drift | Pin versions in documentation |
| Temporary key file left behind | Lock script with `shred`; CI uses env var only |

---

## Migration Plan

### Phase 0: Tooling Setup

- [ ] Install `age` and `sops` on operator machine
- [ ] Generate master keypair with `age-keygen`
- [ ] Encrypt master key with passphrase (`age -p`)
- [ ] Create `secrets/master.key.age` (tracked)
- [ ] Create `secrets/master.key.pub` (tracked)
- [ ] Create `secrets/.sops.yaml` with public key
- [ ] Create `scripts/unlock-secrets.sh` and `scripts/lock-secrets.sh`
- [ ] Add pre-commit hook for SOPS validation
- [ ] Update `.gitignore` for temporary decrypted keys

### Phase 1: Hardware Identities (Priority)

- [ ] Create `secrets/hardware/*.yaml` structure
- [ ] Collect real hardware identities
- [ ] Encrypt and commit
- [ ] Update compiler to resolve `_secret_ref`
- [ ] Remove placeholder values from instances

### Phase 2: Terraform Secrets

- [ ] Migrate `local/terraform/*.tfvars` secrets to SOPS
- [ ] Update Makefile for SOPS decryption
- [ ] Keep non-secret preferences in `local/`

### Phase 3: Ansible Secrets

- [ ] Convert Ansible Vault files to SOPS format
- [ ] Update playbooks for SOPS lookup
- [ ] Remove `.vault_pass` workflow
- [ ] Update documentation

### Phase 4: Cleanup

- [ ] Remove deprecated secret patterns from `.gitignore`
- [ ] Update ADR 0051 status to "Superseded by ADR 0072"
- [ ] Update ADR 0054 to clarify `local/` is for non-secrets only
- [ ] Update CLAUDE.md

---

## Validation Criteria

1. [ ] `age -d secrets/master.key.age` decrypts with passphrase
2. [ ] `./scripts/unlock-secrets.sh` enables SOPS decryption
3. [ ] `sops -d secrets/hardware/*.yaml` works after unlock
4. [ ] `compile-topology.py` resolves hardware identities from SOPS
5. [ ] Terraform apply works with SOPS-decrypted credentials
6. [ ] Ansible playbooks work without `.vault_pass`
7. [ ] Pre-commit hook blocks plaintext secrets
8. [ ] CI/CD pipeline decrypts with `MASTER_KEY_PASSPHRASE` secret
9. [ ] `./scripts/lock-secrets.sh` removes temporary key file

---

## References

- [SOPS documentation](https://github.com/getsops/sops)
- [age encryption](https://github.com/FiloSottile/age)
- ADR 0051: Ansible Runtime, Inventory, and Secret Boundaries
- ADR 0054: Local Inputs Directory
- ADR 0068: Object YAML Template with Typed Placeholders
