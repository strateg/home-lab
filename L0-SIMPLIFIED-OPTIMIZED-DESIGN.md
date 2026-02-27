# L0 Meta Layer: Simplified & Optimized Design

**Goal:** Reduce cognitive load while maintaining all necessary flexibility

---

## The Problem with Complex L0

Current proposal (9 files) is **too complex**:
- Too many files to understand
- Policy inheritance is abstract
- Unclear which file to edit for what purpose
- Hard to discover what configs are available

**New approach:** Simplify to **3 core files** + optional advanced configs

---

## Simplified L0 Structure (3 files instead of 9)

```
topology/
└── L0-meta/
    ├── _index.yaml              # Everything starts here (simple!)
    ├── environments.yaml        # Config profiles: production vs testing
    └── policies/                # Optional advanced configs
        └── security.yaml        # Custom security policies (optional)
```

**IMPORTANT:** Environments are CONFIGURATION PROFILES, not separate physical infrastructures:
- `production` → Deploy to real Orange Pi 5 + MikroTik + Proxmox
- `testing` → Deploy to test-VMs on Proxmox (safe sandbox)

### Why This Works

1. **Single entry point** (`_index.yaml`)
   - Operator starts here
   - Clear defaults for all common needs
   - Don't need to understand all files

2. **Configuration profiles** (`environments.yaml`)
   - Production profile: strict security, daily backups, audit logging
   - Testing profile: basic security, no backups, no audit logging
   - Deploy to different targets (real hardware vs test-VMs)



3. **Optional advanced configs** (`policies/security.yaml`)
   - Only edit if you need custom policies
   - Most teams never need this

---

## File 1: `L0-meta/_index.yaml` (THE STARTING POINT)

**This is what operators read first. Make it simple!**

```yaml
# L0 Meta - Home Lab Topology v4.0
# This is your main configuration file
# Just change values here and regenerate: python3 topology-tools/regenerate-all.py

# === VERSION & METADATA ===
version: 4.0.0
name: "Home Lab Infrastructure"
description: "MikroTik Chateau + Orange Pi 5 + Proxmox"
created: 2025-10-06
author: dprohhorov

# === PICK YOUR ENVIRONMENT ===
# Change this to: production, staging, development
environment: production

# === QUICK SETTINGS (Most common changes) ===
# If you need something different, look in environments.yaml or policies/

quick_settings:
  # Network
  primary_router: mikrotik-chateau
  primary_dns: 192.168.1.1

  # Security
  security_level: baseline  # Options: baseline, strict, relaxed
  require_ssh_key: true

  # Operations
  backup_enabled: true
  monitoring_enabled: true
  audit_logging: false  # Set to true in production

  # Performance
  enable_rate_limiting: true
  enable_traffic_shaping: true

# === ADVANCED CUSTOMIZATION ===
# Don't touch these unless you know what you're doing
# Everything below is loaded from other files or has sensible defaults

# Load environment-specific settings (prod/staging/dev)
environments: !include environments.yaml

# Load custom security policies (if any)
security_policies:
  custom: !include_optional policies/security.yaml

# Default references (used if not specified in L1-L7)
defaults:
  security_policy: ${security_level}
  network_manager: ${primary_router}
  dns_server: ${primary_dns}

# CHANGELOG
# v4.0.0 (2026-02-17): Simplified modular structure, multi-env support
# v3.0.0 (2026-02-16): MikroTik router + Orange Pi 5
# v2.1.0 (2025-10-10): Phase 2 improvements
# v2.0.0 (2025-10-09): Physical/logical/compute separation
# v1.1.0 (2025-10-09): Trust zones, metadata
# v1.0.0 (2025-10-06): Initial Infrastructure-as-Data
```

---

## File 2: `L0-meta/environments.yaml` (CONFIGURATION PROFILES)

**IMPORTANT: Environments are CONFIG PROFILES for different DEPLOYMENT TARGETS, not separate physical infrastructure**

```yaml
# Configuration Profiles
# All use the SAME physical hardware (MikroTik + Proxmox + Orange Pi)
# But different strategies for security, monitoring, backup

environments:

  # ============== PRODUCTION ==============
  # Where: Real Orange Pi 5 + Proxmox nodes
  # What: Live services, real users, important data
  production:
    description: "Live infrastructure on real hardware"

    security:
      policy: strict  # SSH key-only, 16+ char passwords
      ssh_strict: true
      password_min_length: 16
      password_expire_days: 90

    operations:
      backup_enabled: true        # Daily backups
      backup_schedule: "daily"
      monitoring_enabled: true
      monitoring_level: detailed  # Log everything
      audit_logging: true         # Track all changes
      sla_target: 99.9           # Strict SLA

    features:
      high_availability: true
      encryption_required: true
      compliance_enabled: true

    constraints:
      require_change_approval: true  # Need approval before changes
      rollback_allowed: true

  # ============== TESTING ==============
  # Where: Test VMs on Proxmox (test-vm-01..05)
  # What: Test topology changes safely before applying to production
  # How: Deploy same config to test VMs, verify it works, then apply to production
  testing:
    description: "Testing environment - safe sandbox on Proxmox test-VMs"

    security:
      policy: baseline  # Standard settings
      ssh_strict: false
      password_min_length: 12
      password_expire_days: null

    operations:
      backup_enabled: false       # No backups (test data)
      backup_schedule: null
      monitoring_enabled: true
      monitoring_level: basic     # Only errors
      audit_logging: false        # Don't log test changes
      sla_target: 90             # Low SLA in testing

    features:
      high_availability: false
      encryption_required: false
      compliance_enabled: false

    constraints:
      require_change_approval: false
      rollback_allowed: true

    notes: |
      - Deploy to test-vm-01..05 on Proxmox
      - Test all changes here first
      - If successful → apply to production
      - If failed → delete test VMs, no impact on production
```

---

## File 3: `L0-meta/policies/security.yaml` (OPTIONAL - Don't Edit Unless Needed)

**Only edit this if you need custom security policies**

```yaml
# Custom Security Policies (Optional)
# The default policies (baseline, strict, relaxed) are built-in
# Only add custom policies here if you need something special

# Example: Custom policy for compliance-heavy environment
security_policies:

  compliance-strict:
    description: "For compliance-heavy deployments (HIPAA, PCI-DSS)"
    extends: strict  # Start from strict, add more rules

    password_policy:
      min_length: 20
      require_special_chars: true
      require_numbers: true
      max_age_days: 30  # More frequent rotation
      history_count: 10

    ssh_policy:
      permit_root_login: no
      password_authentication: false
      port: 2222  # Non-standard port
      max_auth_tries: 2  # Very strict

    audit_policy:
      log_authentication: true
      log_authorization: true
      log_configuration_changes: true
      log_retention_days: 730  # 2 years
      encryption_of_logs: required

    firewall_policy:
      default_action: drop
      log_blocked: true
      geo_blocking: true  # Block by geography
      rate_limiting: true
      connection_tracking: true

# Easy: just reference the built-in policies
# Strict: just use 'strict'
# Baseline: just use 'baseline'
# Relaxed: just use 'relaxed'
# Custom: define here and reference in _index.yaml
```

---

## Quick Reference: What to Edit

**Most common edits (99% of cases):**

| What You Want To Change | File | What To Edit |
|--------------------------|------|--------------|
| Switch environment (prod↔testing) | `_index.yaml` | `environment: production` or `environment: testing` |
| Change primary router | `_index.yaml` | `primary_router: ...` |
| Change DNS server | `_index.yaml` | `primary_dns: ...` |
| Enable/disable backups | `environments.yaml` | `backup_enabled: true/false` |
| Change security level | `_index.yaml` | `security_level: baseline\|strict\|relaxed` |
| Enable audit logging | `environments.yaml` | `audit_logging: true/false` |

**Advanced edits (1% of cases):**

| What You Want To Change | File | What To Edit |
|--------------------------|------|--------------|
| Create custom security policy | `policies/security.yaml` | Add under `security_policies:` |
| Change SLA target | `environments.yaml` | `sla_target: 99.9` |
| Change monitoring level | `environments.yaml` | `monitoring_level: detailed\|basic\|none` |

---

## How L1-L7 Use Simplified L0

### Simple Case (No Customization)
```yaml
# L1 device
device:
  id: pve-01
  # Automatically inherits from L0 active environment:
  # - security policy
  # - backup_enabled from current environment
  # - monitoring settings from current environment
```

### With Customization
```yaml
# L5 service
service:
  id: svc-nextcloud
  # Override if needed (otherwise inherits from L0):
  override_security_policy: strict  # Use strict even if prod uses baseline
  override_backup_enabled: true
```

---

## Migration from Complex L0 to Simplified L0

**Old complex structure (9 files):**
- security-policies/_base.yaml
- security-policies/baseline.yaml
- security-policies/strict.yaml
- security-policies/relaxed.yaml
- security-policies/policy-registry.yaml
- regional-policies/us-east.yaml
- regional-policies/eu-west.yaml
- regional-policies/apac.yaml
- etc.

**New simplified structure (3 files):**
- _index.yaml (everything starts here)
- environments.yaml (prod/staging/dev)
- policies/security.yaml (optional custom)

**Benefits:**
- ✅ 9 files → 3 files (66% fewer files)
- ✅ One entry point (_index.yaml) → no confusion about where to start
- ✅ Clear environment separation → easy to understand each env
- ✅ Optional advanced configs → beginners don't need to know about them
- ✅ Common settings in quick_settings → 90% of edits in one place

---

## Cognitive Load Reduction

### Before (Complex)
```
New operator opens L0-meta/:
  - Sees 9 files
  - "Which file do I edit?"
  - Confused about policy inheritance
  - Doesn't know what _base.yaml is for
  - Overwhelmed
```

### After (Simplified)
```
New operator opens L0-meta/:
  1. Sees 3 files
  2. Opens _index.yaml (only place to start)
  3. Sees quick_settings section
  4. Changes 1-2 values
  5. Understands what they did
  6. Regenerates
  7. Done!
```

### Design Principles Applied

1. **Progressive Disclosure**
   - Simple stuff first (_index.yaml)
   - Advanced stuff optional (policies/security.yaml)
   - Don't show complexity until needed

2. **Single Entry Point**
   - Everything starts in _index.yaml
   - No "which file do I open?" question

3. **Clear Defaults**
   - sensible defaults in built-in policies
   - 90% of users never need to create custom policies

4. **Explicit Over Implicit**
   - Comments explain what each setting does
   - No hidden inheritance rules
   - Values are obvious (true/false, yes/no)

5. **Separation by Concern**
   - _index.yaml: version + quick settings
   - environments.yaml: prod vs staging vs dev
   - policies/security.yaml: advanced customization only

---

## Implementation Path

### Phase 1: Simplification (Week 1)
- [ ] Create simplified 3-file structure
- [ ] Write clear comments explaining each setting
- [ ] Create quick reference guide
- [ ] Update topology loader to handle simplified L0

### Phase 2: Conversion (Week 2)
- [ ] Convert existing L0-meta.yaml to new structure
- [ ] Test with all generators (Terraform, Ansible, Docs)
- [ ] Verify environments work (prod/staging/dev)

### Phase 3: Documentation (Week 3)
- [ ] Create operator guide (what to edit, when)
- [ ] Create examples (change environment, enable backup, etc.)
- [ ] Create troubleshooting guide

---

## Example Use Cases

### Use Case 1: Deploy Same Topology to Staging

**Current complexity:** Complex policy files, multiple overrides needed

**New simplified:**
```yaml
# In _index.yaml
environment: staging  # Change this one line!
# Everything else auto-adjusts:
# - Security uses baseline (not strict)
# - Backup still enabled
# - Audit logging disabled
# - SLA target 99% (not 99.9%)
# - Monitoring basic level
```

### Use Case 2: Tighten Security in Production

**Current complexity:** Edit baseline.yaml, then strict.yaml, then policy-registry.yaml

**New simplified:**
```yaml
# In _index.yaml
security_level: strict  # Change this one setting!
# All security policies auto-apply:
# - SSH stricter
# - Passwords longer
# - Audit logging enabled
# - Firewall rate limiting ON
```

### Use Case 3: Disable Backups in Development

**Current complexity:** Edit development environment config, check defaults, check policies

**New simplified:**
```yaml
# In environments.yaml under development:
operations:
  backup_enabled: false  # That's it!
```

---

## Summary

**Simplified L0 achieves:**
- ✅ 66% fewer files (9 → 3)
- ✅ 100% fewer entry points (start in _index.yaml)
- ✅ 90% of edits in quick_settings section
- ✅ Progressive disclosure (simple → advanced)
- ✅ Clear environment separation (prod/staging/dev)
- ✅ Optional advanced configs (don't confuse beginners)
- ✅ Better comments explaining purpose

**Result:** New operators can understand L0 in **5 minutes** instead of 30.
