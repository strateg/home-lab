---
@pack: network-security
@version: 1.0
@tokens: ~600
@adr: [0109, 0110, 0111]
---

# AI Rule Pack: Network Security Matrix

## Quick Reference

| Rule | Key Point |
|------|-----------|
| Security Matrix | Zone-to-zone policies auto-derived from trust levels |
| Trust Zones | 7 zones with security_level (0-5) and isolated flag |
| IP Derivation | `vlan_ref` + `host` → computed IP (no hardcoding) |
| Firewall Rules | Generated from matrix, not manually written |
| Enforcement | Per-platform instances (mikrotik, proxmox) |

## Load When

- `**/security_matrix*`
- `**/trust_zone*`
- `**/vlan*` with `trust_zone_ref`
- Network segmentation or firewall policy discussion

## Security Matrix Hierarchy

| Level | Example | Purpose |
|-------|---------|---------|
| Class | `class.network.security_matrix` | Schema with zones, policy_overrides |
| Object | `obj.network.security_matrix.soho` | Zone refs, default overrides |
| Instance | `inst.security_matrix.mikrotik` | Enforcer-specific config |

## R1-R6 Matrix Calculation Rules

| Rule | Condition | Action |
|------|-----------|--------|
| R6 | Explicit policy_override exists | Use override (ALLOW/DENY) |
| R1 | Same zone (from == to) | ALLOW |
| R2 | Source is isolated | ALLOW→untrusted, DENY→others |
| R3 | Downhill (higher→lower level) | ALLOW |
| R4 | Uphill (lower→higher level) | DENY |
| R5 | Same security_level | DENY (needs override) |

**Evaluation order:** R6 → R1 → R2 → R3/R4/R5

## Trust Zones (SOHO Profile)

| Zone | security_level | isolated | Purpose |
|------|----------------|----------|---------|
| management | 5 | false | Router admin, SSH |
| servers | 4 | false | LXC, Docker hosts |
| user | 3 | false | Laptops, phones |
| vpn_tunnel | 2 | false | WireGuard exit |
| iot | 1 | **true** | Smart devices |
| guest | 0 | **true** | Visitors WiFi |
| untrusted | 0 | false | Internet/WAN |

## IP Derivation Pattern (ADR-0111)

```yaml
# Old (deprecated)
network:
  ip: 10.0.30.10/24      # Hardcoded - BAD

# New (correct)
network:
  vlan_ref: inst.vlan.servers
  host: 10                # IP = CIDR base + host
```

**Compiler** resolves to `_resolved_ip: 10.0.30.10/24`

## Validation Codes

| Code | Severity | Rule |
|------|----------|------|
| E7850 | Error | VLAN ID must be unique |
| E7851 | Error | VLAN CIDRs must not overlap |
| E7852 | Error | VLAN must have trust_zone_ref |
| E7861 | Error | Duplicate host in same vlan_ref |
| E7862 | Error | host: 1 reserved for gateway |
| W7864 | Warning | Hardcoded IP (migrate to vlan_ref) |

## Generated Artifacts

| Enforcer | Template | Output |
|----------|----------|--------|
| MikroTik | `zone_firewall.tf.j2` | Address lists, firewall rules |
| Proxmox | (future) | pve-firewall rules |

## Anti-Patterns

| Pattern | Why Wrong | Fix |
|---------|-----------|-----|
| Hardcode `ip:` in workload | Breaks derivation | Use `vlan_ref` + `host` |
| Manual firewall rules | Drift from matrix | Add policy_override |
| Skip trust_zone_ref on VLAN | Breaks matrix | Always add zone ref |
| Edit zone_firewall.tf | Overwritten on generate | Edit template or matrix |

## Key Files

| File | Purpose |
|------|---------|
| `topology-tools/plugins/compilers/security_matrix_compiler.py` | R1-R6 calculation |
| `topology-tools/plugins/compilers/ip_derivation_compiler.py` | IP resolution |
| `topology/object-modules/mikrotik/templates/terraform/zone_firewall.tf.j2` | Firewall generation |
| `projects/home-lab/topology/instances/network/inst.security_matrix.mikrotik.yaml` | Active matrix |
