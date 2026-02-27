# L0 Security Policies: How They Work

**Дата:** 26 февраля 2026 г.
**Тема:** Understanding and using security policies in simplified L0

---

## Three Built-in Policies

L0 поставляется с тремя готовыми security политиками:

### 1. Baseline (Default)

```yaml
# L0-meta/security/built-in/baseline.yaml

For: Standard production use
When: You want good security without overkill

Features:
  ✅ SSH key-based authentication (no passwords)
  ✅ 16-character minimum passwords
  ✅ 90-day password rotation
  ✅ Firewall drops by default
  ✅ No audit logging (optional)

Use when: Most production deployments
```

**Пример:** Home lab with Nextcloud, databases, users

### 2. Strict

```yaml
# L0-meta/security/built-in/strict.yaml

For: High-security requirements
When: Sensitive data, compliance needs

Features:
  ✅ No root SSH login allowed
  ✅ SSH on non-standard port (2222)
  ✅ 20-character minimum passwords
  ✅ 60-day password rotation (more frequent)
  ✅ Full audit logging enabled
  ✅ Geo-blocking on firewall
  ✅ All configuration changes logged

Use when: Financial data, medical info, confidential projects
```

**Пример:** Lab with sensitive business data

### 3. Relaxed

```yaml
# L0-meta/security/built-in/relaxed.yaml

For: Development and testing
When: Not production, internal testing only

Features:
  ✅ SSH password authentication allowed
  ✅ Root login via SSH allowed
  ✅ 8-character minimum passwords
  ✅ Passwords don't expire
  ✅ Firewall accepts by default
  ✅ No audit logging

Use when: Development machines, testing, learning
```

**Пример:** Dev VMs on Proxmox, testing containers

---

## How to Use Security Policies

### Option 1: Use Default (Baseline)

```yaml
# In L0-meta/_index.yaml
security_policy: baseline

# That's it! Baseline applies everywhere
# No extra files needed
```

### Option 2: Switch to Strict

```yaml
# In L0-meta/_index.yaml
security_policy: strict

# Now regenerate
python3 topology-tools/regenerate-all.py

# All L1-L7 layers will use strict security
# SSH key-only, strict passwords, audit logging
```

### Option 3: Create Custom Policy (Rare)

**Only if built-in policies don't fit!**

```yaml
# Create: L0-meta/security/custom/hipaa-compliant.yaml

id: hipaa-compliant
description: "HIPAA-compliant security policy"
extends: strict

password_policy:
  min_length: 24        # HIPAA requires 16+, we do 24
  expire_days: 30       # Change password monthly
  history_count: 24     # Remember last 24 passwords

audit_policy:
  log_retention_days: 2555  # 7 years for compliance
  encryption_of_logs: required
```

Then use it:

```yaml
# In L0-meta/_index.yaml
security_policy: hipaa-compliant
```

---

## Real-World Scenarios

### Scenario 1: Home Lab with Personal Data

```yaml
# You have Nextcloud with family photos

security_policy: baseline
# Good enough for home use
# 16-char passwords, SSH key-only, firewall drop default
```

### Scenario 2: Business Data

```yaml
# You have client records in your lab

security_policy: strict
# No root SSH, strict passwords, audit logging
# Protects sensitive data
```

### Scenario 3: Dev/Test Environment

```yaml
# Creating containers for learning/testing

security_policy: relaxed
# Password auth OK, easier for testing
# Not for production!
```

### Scenario 4: HIPAA/PCI-DSS Compliance

```yaml
# You need to maintain compliance

# Create custom:
# L0-meta/security/custom/pci-compliant.yaml

security_policy: pci-compliant
# 20+ char passwords, strict audit, geo-blocking
```

---

## How Policies Work (Technical)

### File Structure

```
L0-meta/
├── _index.yaml
│   security_policy: baseline  ← You reference policy here
│
└── security/
    ├── built-in/
    │   ├── baseline.yaml
    │   ├── strict.yaml
    │   └── relaxed.yaml
    └── custom/
        ├── hipaa-compliant.yaml   ← If you create one
        └── pci-compliant.yaml
```

### What Happens When You Set Policy

```bash
# 1. You set in _index.yaml
security_policy: baseline

# 2. Topology-tools finds the policy file
# Looks for: L0-meta/security/built-in/baseline.yaml

# 3. Loads all settings:
# password_min_length: 16
# ssh_permit_root: no
# firewall_default: drop
# audit_logging: false

# 4. Applies to all L1-L7 layers
# Every device gets these settings
# Every service gets these settings

# 5. Generates Terraform/Ansible with policy settings
# terraform apply → everything uses baseline policy
```

---

## Changing Policies (Safely)

### Test Baseline → Strict Switch

```bash
# 1. Create branch (isolated experiment)
git checkout -b feature/stricter-security

# 2. Change policy
vim topology/L0-meta/_index.yaml
# Change: security_policy: baseline → security_policy: strict

# 3. See what changes
terraform plan
# Output shows stricter password rules, no root SSH, etc.

# 4. If looks good → apply
git commit
terraform apply

# 5. If something breaks → revert instantly
git revert <commit-hash>
terraform apply
# Back to baseline, no harm done!
```

---

## When to Create Custom Policies

### DO create custom if:
- ✅ Built-in policies don't meet compliance requirements
- ✅ You need HIPAA/PCI-DSS/SOC-2 compliance
- ✅ Organization has specific security rules
- ✅ You need unique combination (e.g., strict passwords + password auth)

### DON'T create custom if:
- ❌ Baseline/strict/relaxed already fit
- ❌ You just want "a bit stricter" than baseline
- ❌ You're not sure what you need

**Most home labs:** Use baseline (90%), strict (9%), relaxed (1%)

---

## Policy Comparison Table

| Feature | Baseline | Strict | Relaxed |
|---------|----------|--------|---------|
| **Min password length** | 16 | 20 | 8 |
| **Password rotation** | 90 days | 60 days | Never |
| **SSH root login** | Prohibited-password | No | Yes |
| **SSH auth method** | Key only | Key only | Key or password |
| **Firewall default** | Drop | Drop | Accept |
| **Audit logging** | No | Yes | No |
| **Geo-blocking** | No | Yes | No |
| **Best for** | Production | Sensitive data | Development |

---

## Quick Selection Guide

```
What's your use case?

└─ Is it PRODUCTION?
   ├─ Yes, standard home lab → Use: baseline
   ├─ Yes, sensitive data → Use: strict
   ├─ Yes, compliance req → Use: custom (HIPAA/PCI-DSS/etc)
   └─ No, just testing/dev → Use: relaxed

When in doubt → baseline (safe default)
```

---

## Implementation

### Step 1: Choose Policy

```yaml
# L0-meta/_index.yaml
security_policy: baseline  # Your choice here
```

### Step 2: Regenerate

```bash
python3 topology-tools/regenerate-all.py
# Loads baseline policy and applies to all layers
```

### Step 3: Apply

```bash
terraform apply
# All resources now have baseline security
```

### Step 4: Later, If You Need Stricter

```bash
git checkout -b feature/stricter
# Change security_policy: strict
terraform plan && terraform apply
```

---

## Files Location

```
Your home lab:

topology/
└── L0-meta/
    ├── _index.yaml                          ← Edit this!
    └── security/
        ├── built-in/
        │   ├── baseline.yaml                ← Pre-loaded
        │   ├── strict.yaml                  ← Pre-loaded
        │   └── relaxed.yaml                 ← Pre-loaded
        └── custom/                          ← Your custom (if needed)
            └── (empty at first)
```

---

## Troubleshooting

### "I changed policy but nothing happened"

```bash
# After changing _index.yaml:
python3 topology-tools/regenerate-all.py  # Must regenerate
terraform plan                             # Check what changes
terraform apply                            # Apply changes
```

### "I want baseline but with 20-char passwords"

Option A: Use strict (which has 20-char requirement)
Option B: Create custom that extends baseline with only that change

```yaml
# L0-meta/security/custom/baseline-strict-passwords.yaml
id: baseline-strict-passwords
extends: baseline

password_policy:
  min_length: 20  # Override baseline's 16
```

### "Should I use strict for production?"

**Depends:**
- ✅ Use strict if: Financial data, medical records, client data
- ✅ Use baseline if: Personal home lab, non-sensitive
- ❌ Don't use relaxed for production ever!

---

## Summary

**Security policies are EASY:**

1. Choose one: baseline, strict, or relaxed
2. Set in _index.yaml: `security_policy: baseline`
3. Regenerate: `python3 topology-tools/regenerate-all.py`
4. Apply: `terraform apply`
5. Done! All L1-L7 layers have that security level

**Advanced:** Create custom policy only if you really need it (rare).

**Testing:** Use git branches + terraform plan to test policy changes safely.
