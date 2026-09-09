# ADR 0118: Universal Container Network Model

- Status: Proposed
- Date: 2026-09-09
- Related: ADR-0107 (Host Placement Defaults), ADR-0111 (IP Derivation), ADR-0041 (Workload Network Attachments)
- Problem: D02 from 2026-09-09 topology audit (gateway mismatch)
- Analysis: SPC Protocol
- Scope: All container platforms (RouterOS, Docker, LXC, future K8s)

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

### Universal Applicability

This dual-network pattern exists across ALL container platforms, not just RouterOS:

| Platform | Host | Primary Network | Service Network | Exposure |
|----------|------|-----------------|-----------------|----------|
| RouterOS container | MikroTik | veth 172.18.x.x | VLAN 192.168.x.x | DNAT |
| Docker (Linux) | OrangePi/ARM | docker0 172.17.x.x | Host VLAN | port publish |
| LXC (Proxmox) | PVE | vmbr0 L2 direct | Same as primary | implicit |
| Docker-in-LXC | PVE→LXC | nested docker0 | LXC veth | nested NAT |
| Kubernetes Pod | K8s node | CNI network | Service/Ingress | ingress |

**Key Insight:** LXC containers are an exception — they attach directly to L2 bridge, so `primary = service`. All other container platforms have distinct runtime and service networks.

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

### D1: Universal `network.primary` and `network.service` Structure

Replace flat `network:` block with explicit dual-network model for ALL container platforms:

```yaml
# Universal dual-network model
network:
  # Primary: where container actually lives (runtime network)
  primary:
    type: bridge | dedicated_veth | host_network | l2_direct | cni
    bridge_ref: inst.bridge.containers     # For bridge/l2_direct types
    address: 172.18.0.210/24               # Static IP on primary network
    gateway: 172.18.0.1                    # Valid gateway for this network
    veth_name: veth-adguard                # For dedicated_veth
    cni_network: calico                    # For K8s CNI
    vlan_ref: inst.vlan.servers            # For l2_direct (LXC)
    host: 60                               # For l2_direct IP derivation

  # Service: how clients reach this container (exposure)
  service:
    exposure: dnat | port_publish | ingress | none
    vlan_ref: inst.vlan.lan                # Which VLAN clients are on
    host: 210                              # Host number for this service
    ports:                                 # For port_publish/dnat
      - "53:53/udp"
      - "80:80"
    # _resolved_ip derived from vlan_ref + host (client-facing)
```

### D2: Network Type Semantics (Universal)

| Type | Description | Primary Network | Platforms |
|------|-------------|-----------------|-----------|
| `bridge` | Shared container bridge | 172.17.x.x (Docker), 172.18.x.x (RouterOS) | Docker, RouterOS |
| `dedicated_veth` | Isolated /30 point-to-point | 172.18.x.x/30 | RouterOS |
| `host_network` | Host's network stack | Host IP | Docker, RouterOS |
| `l2_direct` | Direct L2 bridge attachment | VLAN IP | Proxmox LXC |
| `cni` | Kubernetes CNI plugin | Pod network | Kubernetes |

### D2a: Platform-Type Matrix

| Platform | Default `primary.type` | Requires `service`? | IP Derivation |
|----------|------------------------|---------------------|---------------|
| Proxmox LXC | `l2_direct` | No (implicit) | `primary.vlan_ref + host` |
| Docker (Linux) | `bridge` | Yes | `service.vlan_ref + host` |
| RouterOS (bridge) | `bridge` | Yes | `service.vlan_ref + host` |
| RouterOS (veth) | `dedicated_veth` | No | `primary.address` |
| Docker host_network | `host_network` | No | host IP |
| Kubernetes | `cni` | Yes (ingress) | Service ClusterIP |

### D3: Exposure Methods (Universal)

| Exposure | Mechanism | Platform | Generated Artifacts |
|----------|-----------|----------|---------------------|
| `dnat` | NAT destination rule | RouterOS | `dst-nat` in MikroTik firewall |
| `port_publish` | Docker -p flag | Docker | Compose `ports:` section |
| `ingress` | K8s Ingress/Service | Kubernetes | Ingress YAML |
| `routed` | Policy routing | RouterOS | Mangle rules, routing tables |
| `none` | No external exposure | All | Internal service only |
| (implicit) | L2 direct | LXC | Bridge port on VLAN |

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

### D6: Validator Rules (Universal)

| Code | Severity | Platform | Rule |
|------|----------|----------|------|
| `W7870` | Warning | All | Flat network structure with both bridge_ref and vlan_ref |
| `E7871` | Error | RouterOS | primary.gateway missing when primary.type = bridge |
| `E7872` | Error | All | service.vlan_ref without service.exposure |
| `E7873` | Error | All | service.exposure conflicts with primary.type |
| `W7874` | Warning | RouterOS | Derived _resolved_gateway differs from primary.gateway |
| `E7875` | Error | LXC | primary.type != l2_direct for Proxmox LXC |
| `E7876` | Error | Docker | service.ports missing when exposure = port_publish |
| `E7877` | Error | All | primary.type not supported by platform |
| `W7878` | Warning | Docker | service.exposure missing (defaults to port_publish) |

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

### D11: Proxmox LXC Model (l2_direct)

LXC containers use `l2_direct` — IP derivation happens at primary level:

```yaml
# lxc-grafana.yaml
@instance: lxc-grafana
@extends: obj.proxmox.lxc.debian12.grafana
host_ref: srv-gamayun
network:
  primary:
    type: l2_direct
    # Inherited from host via @on:
    # bridge_ref: inst.bridge.servers
    vlan_ref: inst.vlan.servers
    host: 60
  # No service block — L2 direct, primary IS the service IP
```

Compiler derives `_resolved_ip: 10.0.30.60/24` from `primary.vlan_ref + host`.

### D12: Docker on Linux Model (port_publish)

Docker containers on Linux hosts use `bridge` + `port_publish`:

```yaml
# docker-grafana.yaml (OrangePi)
@instance: docker-grafana
@extends: obj.docker.container.generic
host_ref: srv-orangepi5
network:
  primary:
    type: bridge
    network_name: docker0  # Or custom network
  service:
    exposure: port_publish
    vlan_ref: inst.vlan.servers
    host: 210
    ports:
      - "3000:3000"
runtime:
  image: grafana/grafana:latest
```

Generated `docker-compose.yml` includes:
```yaml
services:
  grafana:
    ports:
      - "10.0.30.210:3000:3000"  # Bind to service IP
```

### D13: Object Template Updates for All Platforms

**RouterOS container template:**
```yaml
# obj.routeros.container.generic.yaml
defaults:
  network:
    primary:
      type: bridge
      bridge_ref: "@on:host.network.bridge_ref?"
      gateway: "@on:host.network.gateway?"
```

**Docker container template:**
```yaml
# obj.docker.container.generic.yaml
defaults:
  network:
    primary:
      type: bridge
      network_name: "@on:host.docker.default_network?:bridge"
```

**Proxmox LXC template:**
```yaml
# obj.proxmox.lxc.debian12.base.yaml
defaults:
  network:
    primary:
      type: l2_direct
      bridge_ref: "@on:host.network.bridge_ref?"
      # vlan_ref + host at instance level
```

## Consequences

### Benefits

1. **Universal model** — same pattern for RouterOS, Docker, LXC, K8s
2. **No gateway conflict** — primary.gateway is always valid for container
3. **Explicit semantics** — clear separation of runtime vs exposure
4. **Extensible** — supports future platforms and exposure methods
5. **Generator clarity** — platform-specific artifacts derived from universal schema
6. **Reduced cognitive load** — one mental model for all containers

### Trade-offs

1. **Schema complexity** — nested network structure
2. **Migration effort** — ~30 instances need structural update
3. **Learning curve** — operators must understand dual-network model
4. **Compiler changes** — IP derivation must handle multiple patterns

### Implementation Estimate

| Component | Files | Effort |
|-----------|-------|--------|
| Base workload class schema | 1 | 1h |
| RouterOS container object template | 1 | 30m |
| Docker container object template | 1 | 30m |
| Proxmox LXC object template | 1 | 30m |
| IP derivation compiler (all types) | 1 | 3h |
| Validators (W7870-W7878) | 1 | 3h |
| MikroTik projection/generator | 2 | 3h |
| Docker Compose generator | 1 | 2h |
| Proxmox LXC projection | 1 | 1h |
| RouterOS instance migration | 5 | 1h |
| Docker instance migration | 10 | 2h |
| LXC instance migration | 9 | 2h |
| Tests (all platforms) | 5 | 3h |
| Documentation | 1 | 1h |
| **Total** | ~31 | **~24h** |

### Migration Path

| Phase | Scope | Action | Risk |
|-------|-------|--------|------|
| 1 | Schema | Add `primary`/`service` structure support | None |
| 2 | Objects | Update all platform object templates | None |
| 3 | Compiler | Support both flat and nested patterns | None |
| 4 | Validators | Add W7870 warning for flat structure | Warning only |
| 5a | RouterOS | Migrate 5 container instances | Low |
| 5b | Docker | Migrate 10 container instances | Low |
| 5c | LXC | Migrate 9 container instances | Low |
| 6 | Generators | Update all platform generators | Medium |
| 7 | Validators | Enable E7871-E7878 error validators | After migration |

## Alternatives Considered

### A1: Platform-Specific Models (Status Quo Extended)

Keep separate network schemas per platform, only fix RouterOS gateway conflict.

**Rejected because:**
- No unified mental model across platforms
- Duplicate concepts (exposure, IP derivation) per platform
- Harder to add new platforms (K8s, Podman, etc.)
- Each generator must understand its own network model

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

### A3: Capability-Based Network Traits

Define network capabilities, let platforms declare which they support:
```yaml
network_traits:
  - cap.network.primary.l2_direct
  - cap.network.service.dnat
```

**Rejected because:**
- Over-engineering for current needs
- Higher complexity without proportional benefit
- Can be added later if needed (ADR 0106 foundation exists)

## References

- ADR-0041: L4 Workload Network Attachment Typing (networks[] array pattern)
- ADR-0107: Host Placement Defaults (@on directive)
- ADR-0111: IP Address Derivation from VLAN
- [MikroTik Container Documentation](https://help.mikrotik.com/docs/display/ROS/Container)
- D02 audit finding: 2026-09-09-topology-remediation-review.md
