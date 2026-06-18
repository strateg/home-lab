# ADR 0030: L2 Network Layer Enhancements

- Status: Implemented
- Date: 2026-02-22
- Implemented: 2026-06-18 (v5 migration + vlan_ids schema)

## Context

L2-network layer lacks several features that would improve infrastructure clarity and validation:

1. **Syntax error**: `baseline.yaml:31` has leading space before `iot:` key
2. **No MTU specification**: Networks assume default MTU without explicit declaration
3. **No VLAN-to-zone mapping**: Trust zones don't declare which VLANs belong to them
4. **No reserved IP ranges**: No way to document infrastructure/DHCP/future IP reservations
5. **No default firewall policy**: Isolated zones don't reference their firewall policies directly

These gaps reduce:
- Validation coverage (can't check VLAN consistency)
- Documentation clarity (MTU, reserved ranges not visible)
- Cross-reference integrity (zones don't link to firewall policies)

## Decision

Implement 5 enhancements to L2-network layer:

### 1. Fix baseline.yaml syntax (Critical)

Remove leading space from `iot:` key at line 31.

### 2. Add MTU fields to Network schema

```yaml
# In network definitions:
mtu: 1500
jumbo_frames: false
```

Schema additions:
- `mtu`: integer, 576-9000, default 1500
- `jumbo_frames`: boolean, default false

Validation: if `jumbo_frames: true` then `mtu > 1500`.

### 3. Add vlan_ids to TrustZoneDefinition

```yaml
# In trust-zones/baseline.yaml:
servers:
  vlan_ids: [30]
management:
  vlan_ids: [99]
```

Schema addition:
- `vlan_ids`: array of integers (1-4094)

Validation: network's `vlan` must be in its `trust_zone_ref`'s `vlan_ids`.

### 4. Add reserved_ranges to Network

```yaml
# In network definitions:
reserved_ranges:
- start: 10.0.30.1
  end: 10.0.30.9
  purpose: infrastructure
- start: 10.0.30.200
  end: 10.0.30.254
  purpose: future-expansion
```

Schema addition:
- `reserved_ranges`: array of {start, end, purpose}
- `purpose`: enum [infrastructure, dhcp-pool, static-assignments, future-expansion]

Validation:
- start/end must be within network CIDR
- start <= end
- Ranges must not overlap
- ip_allocations should not conflict with non-infrastructure ranges

### 5. Add default_firewall_policy_ref to TrustZoneDefinition

```yaml
# In trust-zones/baseline.yaml:
guest:
  default_firewall_policy_ref: fw-guest-isolated
iot:
  default_firewall_policy_ref: fw-iot-isolated
```

Schema addition:
- `default_firewall_policy_ref`: string pattern `^fw-[a-z0-9-]+$`

Validation: referenced policy must exist in `firewall_policies`.

## Consequences

**Improves:**
- Validation coverage: VLAN consistency, IP range conflicts, firewall references
- Documentation: MTU visible in generated docs, reserved ranges documented
- Cross-layer integrity: zones explicitly link to VLANs and firewall policies

**Trade-offs:**
- Schema version bump required (minor)
- Existing networks need MTU field (can default to 1500)
- Trust zones need vlan_ids (optional field, no breaking change)

**Migration:**
- Add new optional fields with sensible defaults
- Fix baseline.yaml syntax immediately
- Run `regenerate-all.py` after changes

## Implementation Notes (2026-06-18)

v5 migration resolved most issues through schema-validator decoupling:

| Enhancement | Status | Notes |
|-------------|--------|-------|
| 1. Syntax fix | ✅ Resolved | File structure changed in v5 |
| 2. MTU fields | ✅ Implemented | `class.network.vlan` has `mtu` property |
| 3. vlan_ids | ✅ Implemented | Added to `class.network.trust_zone` |
| 4. reserved_ranges | ✅ Implemented | `class.network.vlan` has `reserved_ranges` |
| 5. default_firewall_policy_ref | ⚠️ Schema ready | Awaits `firewall_policy` instances |

**Remaining work**: Create `inst.network.firewall_policy.*` instances for isolated zones, then populate `default_firewall_policy_ref` in trust zone instances.

## References

- Class schemas: `topology/class-modules/L2-network/network/`
- Trust zone class: `class.network.trust_zone.yaml`
- Firewall policy class: `class.network.firewall_policy.yaml`
- Trust zone instances: `projects/home-lab/topology/instances/network/inst.trust_zone.*.yaml`
