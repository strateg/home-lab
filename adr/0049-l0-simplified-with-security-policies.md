# ADR 0049: L0 Meta Layer - Simplified with Minimal Modularity

**Date:** 2026-02-26
**Status:** Proposed
**Replaces:** ADR 0049-SIMPLIFIED (oversimplified)
**Audience:** All team members

---

## Context

**Previous approaches were problematic:**
- ADR 0049 (original): 9 files, too complex for small team
- ADR 0049-Simplified: 1 file, too rigid for security policies

**Current situation:**
- Proxmox is weak, can't run extra test VMs
- Need simple L0 but with flexibility for security policies
- Don't want to duplicate configurations across environments
- Want clear security strategy

**Solution:** Simple L0 with ONE main file + OPTIONAL modular security policies

---

## Decision

### Structure: Minimal but Modular

```
L0-meta/
├── _index.yaml                   # Main config (ALWAYS USED)
└── security/                     # Optional security policies
    ├── built-in/                 # Pre-defined policies
    │   ├── baseline.yaml         # Standard production
    │   ├── strict.yaml           # High-security variant
    │   └── relaxed.yaml          # Development-friendly
    └── custom/                   # Your custom policies (optional)
        └── .gitkeep
```

### Principles

1. **One entry point:** `_index.yaml` is all you need to start
2. **Built-in security policies:** baseline/strict/relaxed included by default
3. **Optional customization:** Create custom policies only if needed
4. **No environment duplication:** Single production config, test via git + terraform plan
5. **Minimal cognitive load:** Most users only edit _index.yaml

---

## L0 Architecture

### File 1: `L0-meta/_index.yaml` (MAIN CONFIGURATION)

```yaml
# === VERSION ===
version: 4.0.0
name: "Home Lab Infrastructure"
description: "MikroTik Chateau + Orange Pi 5 + Proxmox"

# === NETWORK SETTINGS ===
network:
  primary_router: mikrotik-chateau
  primary_router_ip: 192.168.88.1
  primary_dns: 192.168.88.1
  backup_dns: 1.1.1.1
  ntp_server: pool.ntp.org

# === SECURITY POLICY SELECTION ===
# Choose one: baseline, strict, or relaxed
security:
  policy: baseline  # Will load from security/built-in/baseline.yaml

# === OPERATIONS SETTINGS ===
operations:
  backup_enabled: true
  backup_schedule: daily
  backup_retention_days: 30
  monitoring_enabled: true
  monitoring_level: detailed
  audit_logging: false

# === DEFAULTS FOR L1-L7 ===
defaults:
  sla_target: 99.0
  firewall_default_action: drop
  encryption_tls_minimum: "1.2"

# === TESTING STRATEGY ===
testing_notes: |
  TESTING WORKFLOW (No Extra VMs):

  1. git checkout -b feature/your-change
  2. Edit topology files
  3. terraform plan (see what changes)
  4. terraform apply (if plan is good)
  5. git revert if something breaks

  NO test-VMs needed! Git + terraform = safe testing
```

### File 2: `L0-meta/security/built-in/baseline.yaml` (DEFAULT)

```yaml
# Baseline Security Policy
# Standard production security for home lab

id: baseline
description: "Standard production security"
version: 1.0.0

password_policy:
  min_length: 16
  require_special_chars: true
  require_numbers: true
  require_uppercase: true
  expire_days: 90
  history_count: 5

ssh_policy:
  permit_root_login: prohibit-password
  password_authentication: false
  pubkey_authentication: true
  port: 22
  max_auth_tries: 3
  idle_timeout: 600

firewall_policy:
  default_action: drop
  log_blocked: true
  rate_limiting: true
  connection_tracking: true
  established_allow: true

audit_policy:
  log_authentication: false  # Set to true if needed
  log_authorization: false
  log_configuration_changes: false
  retention_days: 30

encryption_policy:
  tls_minimum_version: "1.2"
  cipher_suites:
    - TLS_ECDHE_RSA_WITH_AES_256_GCM_SHA384
    - TLS_ECDHE_RSA_WITH_AES_128_GCM_SHA256
  certificate_validation: true

```

### File 3: `L0-meta/security/built-in/strict.yaml` (OPTIONAL)

```yaml
# Strict Security Policy
# For sensitive environments, overrides baseline

id: strict
description: "High-security variant (extends baseline)"
extends: baseline
version: 1.0.0

password_policy:
  min_length: 20        # Stricter
  expire_days: 60       # More frequent rotation
  history_count: 10

ssh_policy:
  permit_root_login: no  # No root login at all
  password_authentication: false
  port: 2222            # Non-standard port
  max_auth_tries: 2

firewall_policy:
  default_action: drop
  log_blocked: true
  rate_limiting: true
  geo_blocking: true    # Block by geography

audit_policy:
  log_authentication: true     # Full audit
  log_authorization: true
  log_configuration_changes: true
  retention_days: 365  # 1 year

```

### File 4: `L0-meta/security/built-in/relaxed.yaml` (DEVELOPMENT)

```yaml
# Relaxed Security Policy
# For development/testing, less strict

id: relaxed
description: "Development-friendly variant (extends baseline)"
extends: baseline
version: 1.0.0

password_policy:
  min_length: 8         # Less strict
  require_special_chars: false
  expire_days: null     # Never expire
  history_count: 0

ssh_policy:
  permit_root_login: yes  # Allow for convenience
  password_authentication: true
  port: 22
  max_auth_tries: 10

firewall_policy:
  default_action: accept  # Default accept
  log_blocked: false
  rate_limiting: false

audit_policy:
  log_authentication: false
  log_authorization: false
  log_configuration_changes: false
  retention_days: 7  # Short retention

```

---

## How Security Policies Work

### Option 1: Use Built-in Policy (99% of cases)

```yaml
# In _index.yaml
security:
  policy: baseline  # Automatically loads security/built-in/baseline.yaml
```

**That's it!** Baseline security applies to all L1-L7 layers.

### Option 2: Choose Different Built-in Policy

```yaml
# In _index.yaml
security:
  policy: strict  # For high-security needs
```

Or:

```yaml
security:
  policy: relaxed  # For development/testing
```

### Option 3: Create Custom Policy (Rare)

If built-in policies don't fit:

```yaml
# Create: L0-meta/security/custom/my-policy.yaml
id: compliance-strict
description: "Custom policy for HIPAA compliance"
extends: strict

password_policy:
  min_length: 24        # Even stricter
  expire_days: 30       # Monthly rotation
  history_count: 24

audit_policy:
  log_authentication: true
  log_authorization: true
  log_configuration_changes: true
  retention_days: 730  # 2 years for compliance
```

Then reference in _index.yaml:

```yaml
security:
  policy: compliance-strict  # Loads security/custom/my-policy.yaml
```

---

## Testing Strategy (No Extra VMs)

### Workflow: Test Changes Safely

```bash
# Want to tighten security?

# 1. Create isolated branch
git checkout -b feature/stricter-security

# 2. Change security policy in _index.yaml
vim topology/L0-meta/_index.yaml
# Change: policy: baseline → policy: strict

# 3. Validate changes
python3 topology-tools/validate-topology.py
terraform plan
# See what will change

# 4. If plan looks good → apply
git commit topology/L0-meta/_index.yaml
git merge feature/stricter-security
terraform apply

# 5. If something breaks → revert instantly
git revert <commit-hash>
terraform apply
# Back to baseline, no downtime!
```

### Why This Works

- ✅ terraform plan shows exactly what changes
- ✅ git branches isolate experiments
- ✅ git revert = instant rollback (no manual work)
- ✅ No test-VMs needed (testing on real production with safety net)
- ✅ No extra resources consumed

---

## Consequences

### Positive

1. **Simplicity:** One main config file (_index.yaml), most users never look at security/
2. **Flexibility:** Built-in policies for 90% of cases, custom policies for edge cases
3. **No duplication:** One production config, tested via git branches
4. **Low cognitive load:** Start with _index.yaml, explore security/ only if needed
5. **Scalability:** Can add more custom policies without complexity

### Trade-offs

1. **Less explicit:** Security policies are "hidden" in separate files (by design)
2. **Requires git literacy:** Team needs to understand git branches and terraform plan
3. **No multiple environments:** Single production config (but testing via git is safer)

### Backward Compatibility

Can migrate from old L0-meta.yaml:
1. Extract values into _index.yaml
2. Identify which security policy matches current settings
3. Set `policy: baseline` (or strict/relaxed as appropriate)
4. Delete old L0-meta.yaml

---

## Directory Structure

```
topology/
└── L0-meta/
    ├── _index.yaml                    # Main config (always used)
    └── security/                      # Security policies (modular)
        ├── built-in/                  # Pre-defined
        │   ├── baseline.yaml          # Standard
        │   ├── strict.yaml            # High-security
        │   └── relaxed.yaml           # Development
        └── custom/                    # Your policies
            └── .gitkeep
```

---

## Implementation

### Phase 1 (Week 1): Create L0 Structure

- [ ] Create L0-meta/_index.yaml with all settings
- [ ] Create L0-meta/security/built-in/ with 3 policies
- [ ] Update topology-tools to load security policies
- [ ] Test that policy selection works

### Phase 2 (Week 2): Migration

- [ ] Convert old L0-meta.yaml to new structure
- [ ] Choose appropriate built-in policy
- [ ] Test with all generators (Terraform, Ansible, Docs)
- [ ] Verify everything still works

### Phase 3 (Week 3): Documentation

- [ ] Document how to use _index.yaml
- [ ] Document how to choose security policy
- [ ] Document git-based testing workflow
- [ ] Document how to create custom policy (rare)

---

## Success Criteria

- [x] One main L0 file (_index.yaml) with all common settings
- [x] Modular security policies (built-in + custom)
- [x] No environment duplication (production only)
- [x] No extra VMs needed for testing (git + terraform plan)
- [x] Clear security policy selection
- [x] Backward compatible with git history
- [x] Simple to understand for non-technical users

---

## Comparison: Complex vs This Simplified Approach

| Aspect | Complex (9 files) | This Approach | Winner |
|--------|-------------------|---------------|--------|
| **L0 files** | 9 | 1 main + optional security/ | This ✅ |
| **Security policies** | 5 files | 3 built-in + custom/ | Same flexibility ✅ |
| **Extra VMs** | 5 test-VMs | 0 (use git instead) | This ✅ |
| **Cognitive load** | High | Low | This ✅ |
| **Duplcation** | ~30% | 0% | This ✅ |
| **Testing safety** | test-VMs on weak Proxmox | git + terraform plan | This ✅ |
| **Flexibility** | High | High | Tie |

**Winner: This approach** wins on 5/7 criteria for production-ready infrastructure

---

## References

- L0-FINAL-SIMPLE-PRACTICAL.md (detailed _index.yaml)
- L0-PRACTICAL-SIMPLE-APPROACH.md (philosophy)
- TESTING-WITHOUT-EXTRA-VMS-FINAL.md (git-based testing)

---

## Decision

**Adopt this simplified L0 design with modular security policies:**

- ✅ Simple entry point (_index.yaml for 90% of edits)
- ✅ Modular security policies (baseline/strict/relaxed built-in)
- ✅ Optional customization (custom/ folder if needed)
- ✅ No extra VMs (git-based testing instead)
- ✅ No configuration duplication
- ✅ Easy to understand and maintain

This is production-ready, simple, and practical for your home lab infrastructure.

---

**Approval:** Ready for implementation

**Next:** Week 1 implementation (create L0 structure)
