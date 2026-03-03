# Workstream 1D: Secret Integration - Input Matrix

**Date:** 2026-03-03 (Day 3)
**Owner:** Security
**Status:** 🚧 IN PROGRESS

---

## 🎯 Objective

Define how secrets flow from vault to bootstrap rendering, ensuring no secrets in tracked files.

---

## 📊 Input Classification Matrix

### Public Inputs (Tracked in Topology)

| Input | Source | Example | Usage |
|-------|--------|---------|-------|
| `router_name` | topology.yaml | `rtr-mikrotik-chateau` | System identity |
| `router_ip` | topology.yaml | `192.168.88.1` | Management IP |
| `api_port` | topology.yaml | `8443` | REST API port |
| `terraform_user` | topology.yaml | `terraform` | Username |
| `terraform_group` | topology.yaml | `terraform` | User group |
| `mgmt_network` | topology.yaml | `192.168.88.0/24` | Firewall rule |
| `topology_version` | generator | `v1.2.3` | Documentation |
| `generation_timestamp` | generator | `2026-03-03 15:30:00` | Documentation |

**Status:** ✅ Safe to track in git

---

### Secret Inputs (From Vault)

| Input | Source | Type | Usage | Path C Only |
|-------|--------|------|-------|-------------|
| `terraform_password` | Vault | Password | Terraform user auth | **Required** |
| `wifi_passphrase` | Vault | Passphrase | WiFi security (Path C) | Optional |
| `wireguard_private_key` | Vault | Key | VPN security (Path C) | Optional |

**Status:** ⚠️ MUST come from vault, never tracked

---

### Local Execution Parameters (Runtime Only)

| Parameter | Source | Example | Usage |
|-----------|--------|---------|-------|
| `mikrotik_bootstrap_mac` | CLI argument | `00:11:22:33:44:55` | Netinstall target |
| `mikrotik_netinstall_interface` | CLI argument | `enp3s0` | Netinstall interface |
| `mikrotik_netinstall_client_ip` | CLI argument | `192.168.88.3` | Netinstall client |
| `mikrotik_routeros_package` | CLI argument | `./routeros-7.21.3.npk` | Package file path |
| `restore_path_flag` | CLI argument | `minimal\|backup\|rsc` | Bootstrap strategy |

**Status:** ✅ Never tracked, provided at runtime

---

## 🔐 Vault Options

### Option 1: Ansible Vault (Current - Simple)

**Status:** ✅ READY
**Complexity:** Low
**Integration:** Native Ansible

**Storage:**
```yaml
# ansible/group_vars/all/vault.yml (encrypted)
# NOTE: These are EXAMPLES ONLY - not real secrets
terraform_password: "EXAMPLE_SecurePassword123_REPLACE_ME"  # pragma: allowlist secret
wifi_passphrase: "EXAMPLE_MyWiFiSecret_REPLACE_ME"  # pragma: allowlist secret
wireguard_private_key: "EXAMPLE_base64key_REPLACE_WITH_REAL_KEY"  # pragma: allowlist secret
```

**Usage in Playbook:**
```yaml
- name: Render bootstrap template
  template:
    src: init-terraform-minimal.rsc.j2
    dest: .work/native/bootstrap/init-terraform.rsc
  vars:
    terraform_password: "{{ vault_terraform_password }}"
```

**Pros:**
- Native Ansible integration
- Simple to implement
- No external dependencies
- Already familiar

**Cons:**
- Per-file encryption (all or nothing)
- Less granular access control
- Rotation requires re-encryption

---

### Option 2: SOPS (ADR 0058 - Recommended)

**Status:** ⏳ PLANNED (ADR 0058)
**Complexity:** Medium
**Integration:** Requires tooling

**Storage:**
```yaml
# secrets/bootstrap/mikrotik.sops.yaml (SOPS encrypted)
terraform_password: ENC[AES256_GCM,data:...,tag:...,type:str]
wifi_passphrase: ENC[AES256_GCM,data:...,tag:...,type:str]
wireguard_private_key: ENC[AES256_GCM,data:...,tag:...,type:str]
```

**Usage in Playbook:**
```yaml
- name: Load secrets from SOPS
  include_vars:
    file: secrets/bootstrap/mikrotik.sops.yaml
    name: mikrotik_secrets

- name: Render bootstrap template
  template:
    src: init-terraform-minimal.rsc.j2
    dest: .work/native/bootstrap/init-terraform.rsc
  vars:
    terraform_password: "{{ mikrotik_secrets.terraform_password }}"
```

**Pros:**
- Per-value encryption (granular)
- Better access control
- Easier rotation
- Git-friendly diffs
- Integrates with cloud KMS

**Cons:**
- Requires SOPS installation
- More complex setup
- Need key management

---

## 🎯 Decision: Hybrid Approach

### Phase 2-3: Ansible Vault
- **Why:** Quick to implement, unblocks Phase 2
- **When:** Immediate (this week)
- **Scope:** Terraform password only

### Phase 4+: Migrate to SOPS (ADR 0058)
- **Why:** Better long-term solution
- **When:** After ADR 0058 implementation
- **Scope:** All secrets

---

## 📋 Secret Rendering Flow

### Path A: Minimal Bootstrap
```
Topology YAML → Generator → Template (init-terraform-minimal.rsc.j2)
                    ↓
Ansible Vault → Jinja2 render → .work/native/bootstrap/init-terraform.rsc
                    ↓
            Netinstall → Device
```

**Secrets needed:** `terraform_password` only

---

### Path B: Backup Restoration
```
Topology YAML → Generator → (no rendering)
                    ↓
Backup file (.backup binary) → Netinstall → Device → Restore
                    ↓
Ansible Vault → Post-restore overrides → Device
```

**Secrets needed:** `terraform_password` (for overrides)

---

### Path C: RSC Script Execution
```
Topology YAML → Generator → (no rendering)
                    ↓
RSC file (sanitized) → Netinstall → Device → Import
                    ↓
Ansible Vault → Post-import overrides → Device (apply real secrets)
```

**Secrets needed:**
- `terraform_password` (override)
- `wifi_passphrase` (override)
- `wireguard_private_key` (override)

---

## 🔧 Implementation Plan

### Phase 2 (Week 3-4): Ansible Vault

**Tasks:**
1. Create `ansible/group_vars/all/vault.yml`
2. Encrypt with `ansible-vault encrypt`
3. Update playbook to use vault variables
4. Test template rendering with secrets
5. Document vault password management

**Deliverable:** Working Ansible Vault integration

---

### Phase 4+ (Post-ADR 0058): SOPS Migration

**Tasks:**
1. Install SOPS
2. Generate/configure encryption keys
3. Create `secrets/bootstrap/mikrotik.sops.yaml`
4. Encrypt with SOPS
5. Update playbook to use SOPS loader
6. Test rendering
7. Migrate existing Ansible Vault secrets

**Deliverable:** SOPS-based secret management

---

## 🛡️ Security Requirements

### Must Have
- ✅ No secrets in tracked files (git)
- ✅ Secrets encrypted at rest
- ✅ Secrets decrypted only during rendering
- ✅ Rendered files in ignored directories only
- ✅ Access control for vault password/keys

### Should Have
- ⏳ Per-value encryption (SOPS)
- ⏳ Audit logging of secret access
- ⏳ Automatic rotation support
- ⏳ Integration with cloud KMS

### Nice to Have
- ⏳ Multiple vault backends
- ⏳ Secret versioning
- ⏳ Emergency access procedures

---

## 📝 Rendering Destinations

### Allowed Locations (Ignored by git)
- ✅ `.work/native/bootstrap/` - Primary rendering target
- ✅ `.work/` - All generated execution artifacts
- ✅ `local/` - User-specific overrides (if exists)

### Forbidden Locations (Tracked in git)
- ❌ `generated/` - Old location, now ignored
- ❌ `topology-tools/templates/` - Source files only
- ❌ `ansible/` - Playbooks only, no rendered secrets
- ❌ Root directory - No generated files

---

## 🧪 Testing Strategy

### Unit Tests
- [ ] Template renders without secrets → errors appropriately
- [ ] Template renders with secrets → produces valid RSC
- [ ] Rendered file contains no placeholder strings
- [ ] Rendered file contains actual secret values

### Integration Tests
- [ ] Ansible vault decryption works
- [ ] Template rendering pipeline works end-to-end
- [ ] Rendered script imports successfully on device
- [ ] Terraform can authenticate with rendered password

### Security Tests
- [ ] No secrets in git history
- [ ] Rendered files in ignored directories
- [ ] Vault file properly encrypted
- [ ] Access controls work

---

## 📊 Secret Lifecycle

### 1. Creation
```bash
# Generate random password
openssl rand -base64 32

# Store in vault
ansible-vault edit ansible/group_vars/all/vault.yml
# Add: terraform_password: "YOUR_GENERATED_PASSWORD_HERE"  # pragma: allowlist secret
```

### 2. Rendering
```bash
# Generator uses vault-decrypted variables
ansible-playbook bootstrap-netinstall.yml --ask-vault-pass
```

### 3. Usage
```bash
# Netinstall applies rendered script with secrets
netinstall-cli -s .work/native/bootstrap/init-terraform.rsc ...
```

### 4. Rotation
```bash
# Update vault
ansible-vault edit ansible/group_vars/all/vault.yml

# Re-render
ansible-playbook bootstrap-netinstall.yml --ask-vault-pass

# Apply to device (manual or via Terraform)
```

---

## 📋 Secret Input Matrix Summary

| Input Type | Count | Storage | Access |
|------------|-------|---------|--------|
| Public | 8 | topology.yaml | Anyone |
| Secret | 3 | Vault (encrypted) | Authorized only |
| Runtime | 5 | CLI arguments | Operator |
| **Total** | **16** | | |

---

## ✅ Deliverables

### Phase 2 (Immediate)
- [x] Secret input matrix defined
- [x] Ansible Vault chosen for Phase 2
- [x] Rendering flow documented
- [x] Security requirements defined
- [ ] Ansible Vault implementation (Week 3)

### Phase 4+ (Future)
- [ ] SOPS migration plan
- [ ] ADR 0058 integration
- [ ] Advanced secret management

---

## 🎯 Exit Criteria

**Workstream 1D Complete when:**
- [x] Input matrix defined
- [x] Vault source decided
- [x] Rendering process documented
- [ ] Ansible Vault implementation ready (Week 3)

**Status:** 75% COMPLETE (documentation done, implementation in Phase 2)

---

**Next:** Phase 2 Week 3 - Implement Ansible Vault integration
