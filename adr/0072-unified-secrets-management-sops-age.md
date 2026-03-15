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

### 5. Key Management

| Key Type | Location | Tracked |
|----------|----------|---------|
| age private key | `~/.config/sops/age/keys.txt` or `$SOPS_AGE_KEY_FILE` | No (operator-local) |
| age public keys | `secrets/age-recipients.txt` | Yes |
| SOPS config | `secrets/.sops.yaml` | Yes |

**Key generation:**
```bash
age-keygen -o ~/.config/sops/age/keys.txt
# Add public key to secrets/age-recipients.txt
```

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
3. **Portable** - clone repo, add key, deploy
4. **Auditable** - git history shows when secrets changed (not what)
5. **Multi-recipient** - team members can have their own keys
6. **Diff-friendly** - YAML keys visible in diffs
7. **No Ansible Vault password** required at compile time
8. **CI/CD ready** - single secret (age key) to configure

### Negative

1. **New tooling** - operators must install `sops` and `age`
2. **Migration effort** - existing Ansible Vault files must be converted
3. **Key backup critical** - losing age private key = losing access to secrets
4. **Learning curve** - team must learn SOPS workflow

### Risks and Mitigation

| Risk | Mitigation |
|------|------------|
| Key loss | Document key backup procedure; multiple recipients |
| Accidental plaintext commit | Pre-commit hook validates encryption |
| SOPS/age version drift | Pin versions in documentation |

---

## Migration Plan

### Phase 0: Tooling Setup

- [ ] Document age key generation
- [ ] Create `secrets/.sops.yaml`
- [ ] Create `secrets/age-recipients.txt`
- [ ] Add pre-commit hook for SOPS validation
- [ ] Update `.gitignore` for age keys

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

1. [ ] `sops -d secrets/hardware/*.yaml` works with operator key
2. [ ] `compile-topology.py` resolves hardware identities from SOPS
3. [ ] Terraform apply works with SOPS-decrypted credentials
4. [ ] Ansible playbooks work without `.vault_pass`
5. [ ] Pre-commit hook blocks plaintext secrets
6. [ ] CI/CD pipeline can decrypt with repository secret

---

## References

- [SOPS documentation](https://github.com/getsops/sops)
- [age encryption](https://github.com/FiloSottile/age)
- ADR 0051: Ansible Runtime, Inventory, and Secret Boundaries
- ADR 0054: Local Inputs Directory
- ADR 0068: Object YAML Template with Typed Placeholders
