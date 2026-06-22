# Network Security Matrix Guide

Zone-based network segmentation with automatic firewall rule generation from topology.

**Related ADRs**: [ADR-0109](../../adr/0109-network-segmentation-zone-based-architecture.md), [ADR-0110](../../adr/0110-universal-network-zone-vlan-mechanism.md), [ADR-0111](../../adr/0111-ip-address-derivation-from-vlan.md)

---

## Overview

The security matrix provides:

- **Trust Zones** with security levels (0-5) and isolation flags
- **Automatic Rule Calculation** using R1-R6 logic
- **IP Address Derivation** from VLAN CIDR + host number
- **Terraform Generation** for MikroTik firewall rules

### Architecture

```
Class                    Object                      Instance
─────────────────────    ────────────────────────    ─────────────────────────
class.network.           obj.network.                inst.security_matrix.
  security_matrix   →      security_matrix.soho  →     mikrotik
  (schema)                 (zone refs, overrides)      (enforcer-specific)
                                  ↓
                     security_matrix_compiler.py
                                  ↓
                     zone_firewall.tf (generated)
```

---

## Trust Zones

### SOHO Profile (7 Zones)

| Zone | Level | Isolated | VLAN | CIDR | Purpose |
|------|-------|----------|------|------|---------|
| management | 5 | No | 99 | 10.0.99.0/24 | Router admin, SSH |
| servers | 4 | No | — | 10.0.30.0/24 | LXC, Docker (Proxmox) |
| user | 3 | No | 10 | 192.168.10.0/24 | Laptops, phones |
| vpn_tunnel | 2 | No | 55 | 192.168.55.0/24 | WireGuard exit |
| iot | 1 | **Yes** | 30 | 192.168.30.0/24 | Smart devices |
| guest | 0 | **Yes** | 20 | 192.168.20.0/24 | Visitors WiFi |
| untrusted | 0 | No | — | 0.0.0.0/0 | Internet/WAN |

### Isolation Behavior

- **Isolated zones** (guest, iot) can reach **untrusted** (internet) but NOT other internal zones
- Non-isolated zones follow **security level** rules (downhill=allow, uphill=deny)

---

## R1-R6 Matrix Calculation

Rules are evaluated in order; first match wins:

| Rule | Condition | Action | Example |
|------|-----------|--------|---------|
| **R6** | Explicit policy_override | Use override | management→servers: ALLOW |
| **R1** | Same zone | ALLOW | user→user: ALLOW |
| **R2** | Source is isolated | ALLOW→untrusted, DENY→others | guest→internet: ALLOW |
| **R3** | Downhill (higher→lower) | ALLOW | management→user: ALLOW |
| **R4** | Uphill (lower→higher) | DENY | user→management: DENY |
| **R5** | Same security_level | DENY | guest→untrusted: DENY |

### Generated Firewall Rules

```
1. established/related        → ACCEPT
2. policy_override ACCEPTs    → ACCEPT (R6)
3. matrix DENY (isolated)     → DROP + log (R2)
4. matrix DENY (uphill)       → DROP + log (R4)
5. matrix DENY (same level)   → DROP + log (R5)
6. FINAL DROP-ALL             → DROP + log
```

---

## Policy Overrides

Override default matrix behavior for specific zone pairs:

```yaml
# obj.network.security_matrix.soho.yaml
policy_overrides:
  - from_zone_ref: inst.trust_zone.management
    to_zone_ref: inst.trust_zone.servers
    action: allow
    description: Management plane has full access to servers zone

  - from_zone_ref: inst.trust_zone.user
    to_zone_ref: inst.trust_zone.servers
    action: allow
    ports: [5432, 6379]  # PostgreSQL, Redis only
    protocol: tcp
    description: PostgreSQL and Redis access from user zone
```

---

## IP Address Derivation (ADR-0111)

### Pattern

```yaml
# Old (deprecated)
network:
  ip: 10.0.30.10/24      # Hardcoded - BAD

# New (correct)
network:
  vlan_ref: inst.vlan.servers
  host: 10                # IP = CIDR base + host
```

### How It Works

1. `vlan_ref` points to VLAN instance (e.g., `inst.vlan.servers`)
2. VLAN instance has `cidr: 10.0.30.0/24`
3. Compiler resolves: `_resolved_ip: 10.0.30.10/24`
4. Gateway derived: `_resolved_gateway: 10.0.30.1`

### Validation

| Code | Severity | Description |
|------|----------|-------------|
| E7861 | Error | Duplicate host in same vlan_ref |
| E7862 | Error | host: 1 reserved for gateway |
| E7863 | Error | host exceeds CIDR range |
| W7864 | Warning | Hardcoded IP (migrate to vlan_ref) |

---

## Configuration Files

### Trust Zone Instance

```yaml
# projects/home-lab/topology/instances/network/inst.trust_zone.user.yaml
@instance: inst.trust_zone.user
@extends: obj.network.trust_zone.user
@group: network

# Zone properties (from object)
# security_level: 3
# isolated: false
```

### VLAN Instance

```yaml
# projects/home-lab/topology/instances/network/inst.vlan.user.yaml
@instance: inst.vlan.user
@extends: obj.network.vlan.user
@group: network

trust_zone_ref: inst.trust_zone.user   # Required!
dhcp_range: 192.168.10.100-192.168.10.254
```

### Security Matrix Instance

```yaml
# projects/home-lab/topology/instances/network/inst.security_matrix.mikrotik.yaml
@instance: inst.security_matrix.mikrotik
@extends: obj.network.security_matrix.soho
@group: network

managed_by_ref: rtr-mikrotik-chateau
enforcer_type: routeros

policy_overrides:
  # Instance-level overrides (merged with object-level)
```

---

## Deployment

### Generate and Apply

```bash
# 1. Compile topology (generates zone_firewall.tf)
task build

# 2. Review generated rules
cat generated/home-lab/terraform/mikrotik/zone_firewall.tf

# 3. Plan Terraform changes
cd generated/home-lab/terraform/mikrotik
terraform plan

# 4. Apply (with backup!)
ssh admin@192.168.88.1 '/system backup save name=pre-matrix'
terraform apply
```

### Verify on Router

```bash
# Check zone address lists
ssh admin@192.168.88.1 '/ip firewall address-list print where list~"zone-"'

# Check firewall rules
ssh admin@192.168.88.1 '/ip firewall filter print where comment~"ADR-0110"'
```

---

## Generated Terraform Resources

### Address Lists (per zone)

```hcl
resource "routeros_ip_firewall_addr_list" "zone_user_1" {
  list    = "zone-user"
  address = "192.168.10.0/24"
  comment = "inst.vlan.user CIDR - managed by topology"
}
```

### Firewall Rules

```hcl
# Established/related
resource "routeros_ip_firewall_filter" "zone_established_related" {
  chain            = "forward"
  action           = "accept"
  connection_state = "established,related"
  comment          = "ADR-0110: Accept established/related"
}

# Policy override
resource "routeros_ip_firewall_filter" "zone_override_user_to_servers_db_tcp" {
  chain            = "forward"
  action           = "accept"
  protocol         = "tcp"
  src_address_list = "zone-user"
  dst_address_list = "zone-servers"
  dst_port         = "5432,6379"
  comment          = "ADR-0110 R6: PostgreSQL and Redis access"
}

# Matrix DENY rule
resource "routeros_ip_firewall_filter" "zone_deny_guest_to_user" {
  chain            = "forward"
  action           = "drop"
  src_address_list = "zone-guest"
  dst_address_list = "zone-user"
  log              = true
  log_prefix       = "DENY:guest→user"
  comment          = "ADR-0110 R2: isolated zone cannot reach user"
}

# Final DROP-ALL
resource "routeros_ip_firewall_filter" "zone_drop_all_forward" {
  chain      = "forward"
  action     = "drop"
  log        = true
  log_prefix = "DROP:final"
  comment    = "ADR-0110: Final drop-all (implicit deny)"
}
```

---

## Troubleshooting

### Rule Not Working

1. Check address list membership:
   ```routeros
   /ip firewall address-list print where list="zone-user"
   ```

2. Check rule order (established/related must be first):
   ```routeros
   /ip firewall filter print chain=forward
   ```

3. Enable logging and check:
   ```routeros
   /log print where topics~"firewall"
   ```

### IP Derivation Errors

```bash
# Check for validation errors
task build 2>&1 | grep -E "E786|W786"

# Verify resolved IPs in compiled output
python -c "
import json
data = json.load(open('generated/home-lab/compiled.json'))
for k, v in data.get('instances', {}).items():
    if '_resolved_ip' in v:
        print(f'{k}: {v[\"_resolved_ip\"]}')"
```

---

## Device Capabilities

Capabilities for security matrix enforcement (defined in `capability-catalog.yaml`):

| Capability | Purpose |
|------------|---------|
| `cap.firewall.security_matrix` | Device can enforce zone-to-zone policies |
| `cap.firewall.security_matrix.routeros` | MikroTik RouterOS enforcement |
| `cap.firewall.security_matrix.pve` | Proxmox pve-firewall enforcement |
| `cap.firewall.address_lists` | Device supports named address lists |

### Data vs Capabilities

| Type | Example | Location |
|------|---------|----------|
| **Data** | `security_level: 5` | `inst.trust_zone.*.yaml` |
| **Data** | `isolated: true` | `inst.trust_zone.*.yaml` |
| **Data** | `trust_zone_ref: inst.trust_zone.user` | `inst.vlan.*.yaml` |
| **Capability** | `cap.firewall.security_matrix.routeros` | Device object |

Capabilities describe what devices CAN DO. Data properties describe configuration values.

---

## Key Files

| File | Purpose |
|------|---------|
| `topology-tools/plugins/compilers/security_matrix_compiler.py` | R1-R6 calculation |
| `topology-tools/plugins/compilers/ip_derivation_compiler.py` | IP resolution |
| `topology-tools/plugins/validators/network_security_validator.py` | E7850-E7853 validation |
| `topology/object-modules/mikrotik/templates/terraform/zone_firewall.tf.j2` | Terraform template |
| `projects/home-lab/topology/instances/network/inst.security_matrix.mikrotik.yaml` | Active matrix |
| `topology/class-modules/capability-catalog.yaml` | `cap.firewall.*` definitions |

---

**Last Updated**: 2026-06-22
