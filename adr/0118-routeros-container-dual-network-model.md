# ADR 0118: RouterOS Container Dual Network Model

- Status: Proposed
- Date: 2026-09-09
- Related: ADR-0107 (Host Placement Defaults), ADR-0111 (IP Derivation), ADR-0041 (Workload Network Attachments)
- Problem: D02 from 2026-09-09 topology audit (gateway mismatch)
- Analysis: SPC Protocol

## Context

### Problem Statement

RouterOS containers on MikroTik have conflicting network configuration in the topology model:

```yaml
# docker-adguard effective state (after compile)
network:
  bridge_ref: inst.bridge.containers   # From host workload_defaults (@on)
  gateway: 172.18.0.1                  # From host workload_defaults (@on)
  vlan_ref: inst.vlan.lan              # Explicit in instance
  host: 210                            # Explicit in instance
  _resolved_ip: 192.168.88.210/24      # Derived from vlan_ref
  _resolved_gateway: 192.168.88.1      # Derived from vlan_ref
```

**Conflict:** `gateway` (172.18.0.1) ≠ `_resolved_gateway` (192.168.88.1)

### Root Cause Analysis

MikroTik RouterOS containers have a dual-network reality:

1. **Runtime network** — container physically exists on an internal bridge (172.18.0.0/24)
2. **Service network** — clients reach the container via VLAN IP (192.168.88.x) through NAT

Current model conflates these two distinct concepts into a single `network:` block.

### Working Example: AmneziaWG Containers

AmneziaWG containers use a cleaner model without VLAN derivation:

```yaml
# docker-amneziawg-russia.yaml
network:
  type: dedicated_veth
  veth_name: veth-awg-ru
  address: 172.18.22.2/30
  gateway: 172.18.22.1
  # No vlan_ref — traffic routing handled by MikroTik routing tables

serves_vlan_ref: inst.vlan.vpn_amnezia  # Declarative: which VLAN's traffic flows here
```

This works because:
- No IP derivation conflict (no vlan_ref)
- `serves_vlan_ref` declares routing relationship, not network attachment
- Gateway is valid for actual container network

### Affected Containers

| Container | Current Model | Gateway Conflict |
|-----------|---------------|------------------|
| docker-adguard | bridge + vlan_ref | YES |
| docker-mosquitto | bridge + vlan_ref | YES |
| docker-tailscale | bridge + vlan_ref | YES |
| docker-amneziawg-russia | dedicated_veth only | NO |
| docker-amneziawg-sweden | dedicated_veth only | NO |

## Decision

### D1: Introduce `network.primary` and `network.service` Structure

Replace flat `network:` block with explicit dual-network model:

```yaml
# NEW: Dual-network model
network:
  # Primary: where container actually lives (runtime network)
  primary:
    type: bridge | dedicated_veth | host_network
    bridge_ref: inst.bridge.containers     # For bridge type
    address: 172.18.0.210/24               # Static IP on bridge
    gateway: 172.18.0.1                    # Valid gateway for this network
    veth_name: veth-adguard                # Optional: dedicated veth

  # Service: how clients reach this container (exposure)
  service:
    vlan_ref: inst.vlan.lan                # Which VLAN clients are on
    host: 210                              # Host number for this service
    exposure: dnat | bridged | routed      # How traffic reaches container
    # _resolved_ip derived from vlan_ref + host (client-facing)
    # _resolved_gateway derived but NOT used for container routing
```

### D2: Network Type Semantics

| Type | Primary Network | Service Exposure | Use Case |
|------|-----------------|------------------|----------|
| `bridge` | Container bridge (172.18.x.x) | DNAT to bridge IP | AdGuard, Mosquitto |
| `dedicated_veth` | Isolated /30 subnet | Routing rules | AmneziaWG, VPN proxies |
| `host_network` | Host's network stack | Direct binding | Tailscale |
| `bridged` | VLAN-attached veth | L2 connectivity | Future: L2-dependent services |

### D3: Exposure Methods

| Exposure | Mechanism | Generated Artifacts |
|----------|-----------|---------------------|
| `dnat` | NAT destination rule | `dst-nat` in MikroTik firewall |
| `routed` | Policy routing | Mangle rules, routing tables |
| `bridged` | Bridge port on VLAN | VLAN interface configuration |
| `none` | No external exposure | Internal service only |

### D4: Backward Compatibility

Flat `network:` structure triggers migration warning:

```yaml
# DEPRECATED: Flat structure with mixed semantics
network:
  bridge_ref: inst.bridge.containers
  gateway: 172.18.0.1
  vlan_ref: inst.vlan.lan
  host: 210
```

Compiler emits `W7870: Deprecated flat network structure, migrate to primary/service model`.

### D5: IP Derivation Modification

Extend ADR-0111 IP derivation:

| Pattern | Source | Target Field |
|---------|--------|--------------|
| `network.vlan_ref + host` | Legacy | `network._resolved_ip` |
| `network.service.vlan_ref + host` | New | `network.service._resolved_ip` |
| `network.primary.address` | Explicit | No derivation needed |

Gateway derivation:
- `network._resolved_gateway` — derived from `vlan_ref` (legacy, may conflict)
- `network.service._resolved_gateway` — derived, for documentation only
- `network.primary.gateway` — explicit, used for container routing

### D6: Validator Rules

| Code | Severity | Rule |
|------|----------|------|
| `W7870` | Warning | Flat network structure with both bridge_ref and vlan_ref |
| `E7871` | Error | primary.gateway missing when primary.type = bridge |
| `E7872` | Error | service.vlan_ref without service.exposure |
| `E7873` | Error | service.exposure = bridged but primary.type != bridged |
| `W7874` | Warning | Derived _resolved_gateway differs from primary.gateway (expected for DNAT) |

### D7: Object Template Update

```yaml
# obj.routeros.container.generic.yaml
defaults:
  trust_zone_ref: "@on:host.trust_zone_ref?"
  network:
    primary:
      type: bridge
      bridge_ref: "@on:host.network.bridge_ref?"
      gateway: "@on:host.network.gateway?"
    # service: defined in instance if needed
```

### D8: Instance Migration

**Before:**
```yaml
# docker-adguard.yaml
@instance: docker-adguard
@extends: obj.routeros.container.generic
host_ref: rtr-mikrotik-chateau
network:
  vlan_ref: inst.vlan.lan
  host: 210
runtime:
  image: adguard/adguardhome
```

**After:**
```yaml
# docker-adguard.yaml
@instance: docker-adguard
@extends: obj.routeros.container.generic
host_ref: rtr-mikrotik-chateau
network:
  primary:
    # Inherited from host via @on
    address: 172.18.0.210/24  # Explicit static IP
  service:
    vlan_ref: inst.vlan.lan
    host: 210
    exposure: dnat
runtime:
  image: adguard/adguardhome
```

### D9: MikroTik Generator Updates

Generator produces NAT rules from service exposure:

```hcl
# For exposure: dnat
resource "routeros_ip_firewall_nat" "dnat_docker_adguard" {
  chain       = "dstnat"
  action      = "dst-nat"
  dst_address = "192.168.88.210"   # From service._resolved_ip
  to_addresses = "172.18.0.210"    # From primary.address
  comment     = "DNAT: docker-adguard (LAN -> container bridge)"
}
```

### D10: AmneziaWG Pattern Preserved

Containers with `primary` only (no `service`) remain valid:

```yaml
# docker-amneziawg-russia.yaml — no changes needed
network:
  primary:
    type: dedicated_veth
    veth_name: veth-awg-ru
    address: 172.18.22.2/30
    gateway: 172.18.22.1
  # No service block — routing handled via routing_policy_ref

serves_vlan_ref: inst.vlan.vpn_amnezia  # Unchanged
```

## Consequences

### Benefits

1. **Model accuracy** — topology reflects actual MikroTik networking
2. **No gateway conflict** — primary.gateway is always valid for container
3. **Explicit semantics** — clear separation of runtime vs exposure
4. **Extensible** — supports future exposure methods (bridged, routed)
5. **Unified pattern** — works for all RouterOS container types
6. **Generator clarity** — NAT rules derived from explicit exposure type

### Trade-offs

1. **Schema complexity** — nested network structure
2. **Migration effort** — 3 instances need updating
3. **Learning curve** — operators must understand dual-network model
4. **Compiler changes** — IP derivation must handle both patterns

### Implementation Estimate

| Component | Files | Effort |
|-----------|-------|--------|
| Class schema | 1 | 1h |
| Object template | 1 | 30m |
| IP derivation compiler | 1 | 2h |
| Validators (W7870-W7874) | 1 | 2h |
| MikroTik projection | 1 | 2h |
| MikroTik generator (NAT) | 1 | 2h |
| Instance migration | 3 | 1h |
| Tests | 3 | 2h |
| Documentation | 1 | 1h |
| **Total** | ~13 | **~14h** |

### Migration Path

| Phase | Action | Risk |
|-------|--------|------|
| 1 | Add schema support for both patterns | None |
| 2 | Update object template with primary block | None |
| 3 | Add W7870 warning for flat structure | Warning only |
| 4 | Migrate 3 container instances | Low |
| 5 | Add generator NAT rule support | Medium |
| 6 | Enable E7871-E7873 validators | After migration |

## Alternatives Considered

### A2a: Bridge-only (remove vlan_ref)

Remove VLAN derivation, use NAT for all access.

**Rejected because:**
- Loses declarative "service on VLAN X" semantics
- All IPs must be manually assigned
- No client-facing IP in topology model

### A2b: VLAN-only (remove bridge_ref)

Attach containers directly to VLAN.

**Rejected because:**
- Doesn't match MikroTik container reality (separate bridge)
- Breaks container isolation
- Would require reconfiguring actual MikroTik networking

## References

- ADR-0041: L4 Workload Network Attachment Typing (networks[] array pattern)
- ADR-0107: Host Placement Defaults (@on directive)
- ADR-0111: IP Address Derivation from VLAN
- [MikroTik Container Documentation](https://help.mikrotik.com/docs/display/ROS/Container)
- D02 audit finding: 2026-09-09-topology-remediation-review.md
