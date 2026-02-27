# ADR 0049-FINAL: L0 Meta Layer - Abstract Policies and Defaults Only

**Date:** 2026-02-26
**Status:** Proposed
**Audience:** Architecture team

---

## Context

**Architectural Principle:** L0 is ABSTRACT - defines what, not how

**Previous errors:**
- Including device references (primary_network_manager_device_ref)
- Including IP addresses
- Creating dependencies on L1-L7

**Correct principle:**
- L0 defines POLICIES and DEFAULTS
- L0 has NO references to L1-L7
- L1-L7 use L0, not vice versa
- One-way dependency: L1-L7 → L0 only

---

## Decision

### L0 Structure (6 Functional Modules)

```
L0-meta/
├── _index.yaml                 # Version + metadata only
├── security/                   # Security policy module
│   ├── built-in/
│   │   ├── baseline.yaml       # Standard production
│   │   ├── strict.yaml         # High-security
│   │   └── relaxed.yaml        # Development
│   └── custom/                 # User-defined (if needed)
└── defaults/                   # Global defaults (abstract!)
    ├── network.yaml           # Network strategy defaults
    ├── storage.yaml           # Backup/replication defaults
    ├── compute.yaml           # Resource defaults
    ├── application.yaml       # SLA/monitoring defaults
    ├── observability.yaml     # Alert/log defaults
    └── operations.yaml        # Incident response defaults
```

### Principle: Only Abstract, Never Concrete

```yaml
# ✅ ALLOWED (abstract)
sla_target: 99.0              # What SLA?
backup_schedule: daily        # When to backup?
monitoring_level: detailed    # How much detail?
encryption_required: true     # Policy: is encryption required?

# ❌ NOT ALLOWED (concrete)
primary_router_ip: 192.168.88.1    # Concrete IP!
device_ref: network-gateway         # Reference to L1!
vm_count: 5                         # Specific count!
redis_port: 6379                   # Specific port!
```

---

## File 1: `L0-meta/_index.yaml` (Abstract Metadata)

```yaml
# VERSION & METADATA (no dependencies on upper layers!)
version: 4.0.0
name: "Home Lab Infrastructure"
description: "Layered topology - abstract policies"

# ACTIVE SECURITY POLICY
active_security_policy: baseline  # Which security level to use

# Include modules
defaults: !include_dir_sorted defaults/
security_policies: !include_dir_sorted security/

# NOTES
notes: |
  L0 is ABSTRACT meta layer:

  ✅ Contains:
    - Version and metadata
    - Security policies (baseline/strict/relaxed)
    - Global defaults and strategies
    - Policy requirements
    - Abstract values (99.0%, daily, detailed)

  ❌ Does NOT contain:
    - Device references
    - IP addresses
    - Port numbers
    - Specific hostnames
    - References to L1-L7
    - Concrete values
```

---

## File 2: `L0-meta/security/built-in/baseline.yaml`

```yaml
id: baseline
description: "Standard production security policy"

password_policy:
  min_length: 16
  require_special_chars: true
  require_numbers: true
  expire_days: 90
  history_count: 5

ssh_policy:
  permit_root_login: prohibit-password
  password_authentication: false
  pubkey_authentication: true
  idle_timeout: 600

firewall_policy:
  default_action: drop
  log_blocked: true
  rate_limiting: true

audit_policy:
  log_authentication: false
  log_authorization: false
  retention_days: 30

encryption_policy:
  tls_minimum_version: "1.2"
  certificate_validation: required
```

---

## File 3: `L0-meta/defaults/network.yaml`

```yaml
# Network strategy defaults (abstract, no IPs!)

network:
  # Design strategy
  mtu_default: 1500
  routing_policy: static
  dns_ttl_default: 300

  # No IP addresses
  # No device names
  # No port numbers

firewall:
  default_action: drop  # From security policy
  enable_logging: true
  enable_rate_limiting: true

encryption:
  tls_minimum_version: "1.2"
  require_encryption_in_transit: true
```

---

## File 4: `L0-meta/defaults/storage.yaml`

```yaml
# Backup and replication strategy (abstract!)

storage:
  backup:
    enabled: true
    schedule: daily       # WHEN (abstract!)
    retention_days: 30    # HOW LONG (abstract!)

  replication:
    enabled: false
    replication_factor: 2

  encryption:
    encrypt_backups: true

# NO:
# - storage device names
# - mount points
# - specific storage amounts
```

---

## File 5: `L0-meta/defaults/compute.yaml`

```yaml
# Resource strategy defaults (abstract!)

compute:
  # Default sizes (abstract!)
  vm_default_memory_mb: 2048
  vm_default_cpus: 2

  # Resource limits (policy!)
  max_vms_per_node: 10
  max_memory_per_node_percent: 80

  # Availability policy
  high_availability_required: false

# NO:
# - node names
# - specific CPU counts
# - specific memory amounts (just defaults!)
```

---

## File 6: `L0-meta/defaults/application.yaml`

```yaml
# Service defaults (abstract!)

application:
  sla:
    target_uptime_percent: 99.0

  monitoring:
    level: detailed  # detailed/basic/minimal
    metrics_interval_seconds: 60

  logging:
    level: info  # info/debug/warn
    retention_days: 30

  audit:
    enabled: false
    retention_days: 30

# NO:
# - service names
# - specific port numbers
# - specific resource amounts
```

---

## File 7: `L0-meta/defaults/observability.yaml`

```yaml
# Alert and logging defaults (abstract!)

observability:
  alerting:
    # Alert strategy (abstract!)
    default_severity: warning
    critical_escalation_delay_minutes: 1
    warning_escalation_delay_minutes: 5

  dashboards:
    # Dashboard strategy
    default_refresh_interval: 30s

  logging:
    retention_days: 30
    compression: enabled

  metrics:
    retention_days: 90
    scrape_interval: 60s

# NO:
# - alert names
# - dashboard names
# - specific metric queries
```

---

## File 8: `L0-meta/defaults/operations.yaml`

```yaml
# Incident response strategy (abstract!)

operations:
  escalation:
    # Escalation policy (abstract!)
    first_response_sla_minutes: 15
    escalation_levels: 3

  incident_response:
    auto_restart_enabled: false
    auto_failover_enabled: false
    manual_approval_required: true

  change_management:
    change_approval_required: true
    rollback_enabled: true

  mttr_targets:
    critical: 5      # 5 minutes
    major: 30        # 30 minutes
    minor: 120       # 2 hours

# NO:
# - runbook names
# - escalation contact names
# - incident ticket references
```

---

## How L1-L7 Use L0

Each layer reads ONLY what it needs:

```yaml
# L1 (Foundation)
security_policy: ${L0.active_security_policy}
ssh_timeout: ${L0.security[baseline].ssh_policy.idle_timeout}

# L2 (Network)
firewall_default: ${L0.defaults.network.firewall.default_action}
encryption_required: ${L0.defaults.network.encryption.require_encryption_in_transit}

# L3 (Storage)
backup_schedule: ${L0.defaults.storage.backup.schedule}
backup_retention: ${L0.defaults.storage.backup.retention_days}

# L5 (Application)
sla_target: ${L0.defaults.application.sla.target_uptime_percent}
monitoring_level: ${L0.defaults.application.monitoring.level}

# L7 (Operations)
escalation_policy: ${L0.defaults.operations.escalation}
mttr_critical: ${L0.defaults.operations.mttr_targets.critical}
```

**Key:** L0 has NO knowledge of which L5 services exist, which L7 runbooks exist, etc.

---

## Correct Layering

```
L0: ABSTRACT POLICY LAYER
├─ Version & metadata
├─ Security policies (baseline/strict/relaxed)
├─ Operational defaults (backup daily, monitoring detailed)
├─ Resource defaults (2GB VM, 2 CPU)
├─ SLA targets (99%, MTTR 5min)
└─ Feature flags (HA off, encryption on)
   (No references to L1-L7!)

     ↓↓↓ L1-L7 USE L0 ↓↓↓

L1: CONCRETE FOUNDATION
├─ Implements security policy from L0
├─ Creates specific devices (not in L0!)
├─ Assigns IP addresses (not in L0!)
└─ Sets hostnames (not in L0!)

L2: CONCRETE NETWORK
├─ Implements firewall policy from L0
├─ Configures specific routes (not in L0!)
└─ Assigns specific ports (not in L0!)

... etc for L3-L7
```

---

## Success Criteria

- [x] L0 contains only abstract policies
- [x] L0 has NO device references
- [x] L0 has NO IP addresses
- [x] L0 has NO hostnames
- [x] L0 is modular (6 functional domains)
- [x] Each module is focused (network, storage, compute, etc.)
- [x] L1-L7 can read what they need from L0
- [x] One-way dependency: L1-L7 → L0 only

---

## Implementation

### Phase 1: Create L0 Structure
- Create _index.yaml (version + metadata)
- Create 6 default files (network, storage, compute, application, observability, operations)
- Create security/ with baseline/strict/relaxed

### Phase 2: Remove All References
- Remove any device references
- Remove any IP addresses
- Remove any port numbers
- Remove any L1-L7 specific knowledge

### Phase 3: Validate
- Ensure L0 only contains abstract policies
- Test that L1-L7 can read L0
- Verify no circular dependencies

---

## References

- L0-CORRECT-ANALYSIS-FROM-SCRATCH.md (detailed analysis)
- All ADRs should reference this principle

---

**Status:** Ready for implementation

**Key Principle:** L0 is ABSTRACT. It knows NOTHING about specific devices, IPs, or services. L1-L7 implement L0's policies with concrete values.
