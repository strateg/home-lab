# ADR 0049-CORRECTED: L0 Meta Layer - Abstract Policies Only

**Date:** 2026-02-26
**Status:** Proposed
**Replaces:** ADR 0049-l0-simplified-with-security-policies.md

---

## Context

**Principle:** L0 defines ABSTRACT POLICIES, L1 implements them with concrete details

- ✅ L0: Global policies, security levels, monitoring strategies, device roles
- ❌ L0: NO IP addresses, NO specific device names, NO concrete hardware details

**Previous error:** Including IP addresses in L0 violated architecture

**This ADR:** Corrects L0 to be pure policy layer

---

## Decision

### Structure

```
L0-meta/
├── _index.yaml                   # Abstract policies only
└── security/                     # Security polícy modules
    ├── built-in/
    │   ├── baseline.yaml
    │   ├── strict.yaml
    │   └── relaxed.yaml
    └── custom/
```

### L0-meta/_index.yaml

```yaml
version: 4.0.0
name: "Home Lab Infrastructure"

# ABSTRACT DEFAULTS (policies, not implementations)
defaults:
  primary_network_manager_device_ref: network-gateway  # Role!
  primary_dns_resolver_ref: default-dns               # Role!
  ntp_source_ref: pool-ntp                            # Role!

  firewall_default_action: drop    # Policy!
  tls_minimum_version: "1.2"       # Policy!
  default_sla_target: 99.0         # Policy!
  default_backup_retention_days: 30  # Policy!

security_policy: baseline  # baseline/strict/relaxed

operations:
  backup_enabled: true
  backup_schedule: daily
  monitoring_enabled: true
  audit_logging_enabled: false
```

---

## Key Difference: Policy vs Implementation

### ❌ WRONG (Previous)

```yaml
# L0-meta/_index.yaml
network:
  primary_router_ip: 192.168.88.1      # IP ADDRESS!!! 🚫
  primary_dns: 192.168.88.1            # IP ADDRESS!!! 🚫
  ntp_server: pool.ntp.org             # CONCRETE SERVER!!! 🚫
```

### ✅ CORRECT (This)

```yaml
# L0-meta/_index.yaml
defaults:
  primary_network_manager_device_ref: network-gateway  # ROLE!
  primary_dns_resolver_ref: default-dns               # ROLE!
  ntp_source_ref: pool-ntp                            # ROLE!

# IMPLEMENTATION (L1):
# L1-foundation/devices/network-services/network-gateway.yaml
device:
  id: network-gateway
  ip: 192.168.88.1          # IP HERE! ✅
```

---

## Layer Responsibilities

| What | L0 | L1 | L2 | L5 |
|-----|----|----|----|----|
| **Device role** | ✅ network-gateway | Impl with IP | - | - |
| **IP address** | ❌ | ✅ 192.168.88.1 | - | - |
| **Security policy** | ✅ baseline | Use policy | - | - |
| **SSH settings** | ❌ | ✅ port 22 | - | - |
| **Service port** | ❌ | ❌ | ✅ port 443 | - |
| **App config** | ❌ | ❌ | ❌ | ✅ |

---

## Consequences

**Positive:**
- Clear layer separation
- L0 is reusable (same policies for different hardware)
- L1 can change IPs without touching L0
- Follows architectural principles

**Negative:**
- Must understand device roles vs implementations
- More indirection (role → implementation)

---

## Implementation

1. Create L0-meta/_index.yaml with abstract policies only
2. Ensure L1 defines all concrete IPs and devices
3. L1 references L0 policies via security_policy, defaults
4. No IP addresses in L0

---

**Status: READY**
