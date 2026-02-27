# L0 Environments - CORRECTED INTERPRETATION

**Important:** Environments are CONFIG PROFILES, NOT separate physical infrastructures

Your infrastructure is SINGLE (MikroTik + Proxmox + Orange Pi)
Environments are different CONFIGURATIONS for that same hardware

---

## Scenario

You have ONE physical infrastructure (PRODUCTION):
  - 1x MikroTik Chateau (router/gateway)
  - 1x Orange Pi 5 (app server)
  - 1x Proxmox node (storage/VMs/dev)

You want to:
  1. Run PRODUCTION workloads (Nextcloud, databases, etc) with STRICT security
  2. Test CHANGES safely before applying to production (in test VMs, not affecting live)

Solution: Use environment PROFILES in the same topology

---

## Correct environments.yaml

```yaml
# ENVIRONMENT CONFIGURATIONS
# All use the SAME physical hardware, different strategies

environments:

  # ============== PRODUCTION ==============
  # For: Live services, real users, important data
  # Where: Real workloads on actual Orange Pi 5 + Proxmox nodes
  production:
    description: "Live infrastructure - STRICT and SAFE"

    security:
      policy: strict           # SSH key-only, 16+ char passwords
      password_min_length: 16
      password_expire_days: 90
      ssh_strict: true         # No root login

    operations:
      backup_enabled: true     # Daily backups
      backup_schedule: daily
      monitoring_enabled: true
      monitoring_level: detailed  # Log everything
      audit_logging: true      # Track all changes
      sla_target: 99.9         # Must have 99.9% uptime
      change_approval: required  # Need approval before changes

    features:
      high_availability: true
      encryption_required: true
      compliance_enabled: true

    # Real services run here
    active_services:
      - svc-nextcloud          # Real Nextcloud
      - svc-postgres           # Real database
      - svc-redis              # Real cache
      - svc-monitoring         # Real monitoring

  # ============== TESTING ==============
  # For: Testing topology changes safely
  # Where: Test VMs on Proxmox (does NOT affect production workloads)
  # How: Create test-vm-01 to test-vm-05 on Proxmox, run same topology there
  testing:
    description: "Testing environment - safe sandbox for changes"

    security:
      policy: baseline         # Standard security
      password_min_length: 12
      password_expire_days: null  # Don't expire in testing
      ssh_strict: false

    operations:
      backup_enabled: false    # No backups (test data)
      backup_schedule: null
      monitoring_enabled: true
      monitoring_level: basic  # Only log errors
      audit_logging: false     # Don't log test changes
      sla_target: 90           # Low SLA in testing
      change_approval: not_required

    features:
      high_availability: false
      encryption_required: false
      compliance_enabled: false

    # Same services, but in test VMs (won't affect real production)
    active_services:
      - test-svc-nextcloud
      - test-svc-postgres
      - test-svc-redis
      - test-svc-monitoring

    notes: |
      - Create test-vm-01..05 on Proxmox
      - Run this configuration on test VMs
      - Test all changes here first
      - If successful → apply to production
      - If failed → delete test VMs, no impact on production
```

---

## How To Use This

### Scenario: Test Nextcloud upgrade before production

**Step 1: Prepare Testing Environment**
```bash
# Switch topology to testing config
environment: testing

# This changes strategy to:
# - No backups (don't need for test)
# - No audit logging (test data)
# - Basic monitoring only
# - No SLA requirements
```

**Step 2: Create Test Infrastructure**
```bash
# Create test VMs on Proxmox for testing
prlxc create test-vm-01  # Test Nextcloud container
prlxc create test-vm-02  # Test database

# Regenerate topology for testing
python3 topology-tools/regenerate-all.py
# This generates Terraform/Ansible for TEST environment

# Deploy to test VMs
terraform apply  # Applies to test-vm-01, test-vm-02 (NOT production!)
ansible-playbook site.yml  # Configures test VMs only
```

**Step 3: Test Nextcloud Upgrade**
```bash
# In test VM: perform Nextcloud upgrade
# Test all features
# Verify it works

# If SUCCESS:
#   Switch back to production config
#   Apply same changes to real Nextcloud
# If FAILURE:
#   Delete test VMs
#   Fix issue
#   Try again
```

**Step 4: Switch Back to Production**
```bash
environment: production  # Back to strict config

# Regenerate and apply to real production
python3 topology-tools/regenerate-all.py
terraform apply
ansible-playbook site.yml
```

---

## What Environments Are NOT

❌ **NOT:** Separate MikroTik routers for each environment
❌ **NOT:** Separate physical hardware for staging
❌ **NOT:** Different network segments that can't talk to each other

---

## What Environments ARE

✅ **ARE:** Configuration profiles for your topology
✅ **ARE:** Different security/monitoring/backup strategies
✅ **ARE:** Different Terraform/Ansible deployments
✅ **ARE:** Ways to test safely without affecting production

---

## Summary

| Concept | Reality |
|---------|---------|
| **Your hardware** | ONE (MikroTik + Proxmox + Orange Pi) |
| **Your production** | Lives on real hardware |
| **Your testing** | Uses test-vm-01..05 on Proxmox |
| **environment: production** | Config for real Nextcloud, real DB |
| **environment: testing** | Config for test-vm, test containers |
| **Switch environment** | Change config profile + regenerate |
| **Deploy to testing** | Terraform/Ansible → test-vm-01..05 |
| **Deploy to production** | Terraform/Ansible → real Orange Pi + Proxmox |

---

## Corrected Statement

**WRONG:** "You can't make MikroTik router staging"
**RIGHT:** "You can't make physical hardware staging, but you can have different CONFIGURATION PROFILES and deploy them to different targets"

- Profile: `production` → Deploy to real Orange Pi 5 (production Nextcloud)
- Profile: `testing` → Deploy to test-vm-01 on Proxmox (test Nextcloud)

Same configuration code, different deployments, different targets.

---

**Does this clarification make sense?**

You don't need separate hardware for staging.
You use the SAME topology code with different ENV configurations + different deployment targets (test-VMs vs real hardware).
