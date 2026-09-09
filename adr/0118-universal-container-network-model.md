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

**Key Insight:** ALL platforms have dual-network semantics. The difference is `service.exposure` type:
- `l2` (LXC): Service IP assigned directly to container interface (no NAT)
- `dnat` (RouterOS): NAT rule maps service IP → primary address
- `port_publish` (Docker): Host binds service IP:port → container port

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
  # Primary: HOW container attaches to network (runtime attachment)
  primary:
    type: bridge | dedicated_veth | host_network | cni
    bridge_ref: inst.bridge.containers     # For bridge type
    interface: eth0                        # Container interface name
    address: 172.18.0.210/24               # Static IP (for NAT-based)
    gateway: 172.18.0.1                    # Valid gateway (for NAT-based)
    veth_name: veth-adguard                # For dedicated_veth
    cni_network: calico                    # For K8s CNI

  # Service: HOW clients reach this container (exposure method)
  service:
    exposure: l2 | dnat | port_publish | routed | ingress | none
    vlan_ref: inst.vlan.lan                # VLAN for IP derivation
    host: 210                              # Host number for IP derivation
    ports:                                 # For port_publish/dnat
      - "53:53/udp"
      - "80:80"
    # _resolved_ip derived from vlan_ref + host
    # WHERE this IP goes depends on exposure type:
    #   l2 → primary.interface
    #   dnat → NAT rule target
    #   port_publish → host bind address
```

### D2: Network Type Semantics (Universal)

`primary.type` describes HOW the container attaches to the network:

| Type | Description | Platforms |
|------|-------------|-----------|
| `bridge` | Shared container/host bridge | Docker, RouterOS, **LXC** |
| `dedicated_veth` | Isolated /30 point-to-point | RouterOS |
| `host_network` | Host's network stack directly | Docker, RouterOS |
| `cni` | Kubernetes CNI plugin | Kubernetes |

### D2a: Exposure Method Semantics

`service.exposure` describes WHERE the derived IP is assigned:

| Exposure | IP Assignment | NAT Layer | Platforms |
|----------|---------------|-----------|-----------|
| `l2` | Container's primary interface | None | **LXC** |
| `dnat` | Virtual; NAT rule to primary.address | Yes | RouterOS |
| `port_publish` | Host bind; port map to container | Yes | Docker |
| `routed` | Policy routing table | None | RouterOS |
| `ingress` | K8s Ingress controller | Depends | Kubernetes |
| `none` | Not exposed externally | N/A | All |

### D2b: Platform-Type Matrix (Symmetric)

| Platform | `primary.type` | `service.exposure` | IP Derivation |
|----------|---------------|-------------------|---------------|
| Proxmox LXC | `bridge` | `l2` | `service.vlan_ref + host` → eth0 |
| Docker (Linux) | `bridge` | `port_publish` | `service.vlan_ref + host` → bind |
| RouterOS (bridge) | `bridge` | `dnat` | `service.vlan_ref + host` → NAT |
| RouterOS (veth) | `dedicated_veth` | `routed` | `primary.address` |
| Docker host_network | `host_network` | `none` | Host IP |
| Kubernetes | `cni` | `ingress` | ClusterIP |

**Symmetry:** All platforms use `service.vlan_ref + host` for IP derivation (except explicit `primary.address`).

### D3: Exposure Methods (Universal)

| Exposure | Mechanism | Platform | Generated Artifacts |
|----------|-----------|----------|---------------------|
| `l2` | IP on container interface | LXC | Proxmox network config |
| `dnat` | NAT destination rule | RouterOS | `dst-nat` in MikroTik firewall |
| `port_publish` | Docker -p flag | Docker | Compose `ports:` section |
| `ingress` | K8s Ingress/Service | Kubernetes | Ingress YAML |
| `routed` | Policy routing | RouterOS | Mangle rules, routing tables |
| `none` | No external exposure | All | Internal service only |

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
| `E7871` | Error | RouterOS | primary.gateway missing when service.exposure = dnat |
| `E7872` | Error | All | service.vlan_ref without service.exposure |
| `E7873` | Error | All | service.exposure not valid for platform |
| `W7874` | Warning | RouterOS | Derived _resolved_gateway differs from primary.gateway |
| `E7875` | Error | LXC | service.exposure != l2 for Proxmox LXC |
| `E7876` | Error | Docker | service.ports missing when exposure = port_publish |
| `E7877` | Error | All | primary.type not supported by platform |
| `W7878` | Warning | All | service block missing (platform default applied) |

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

### D11: Proxmox LXC Model (l2 exposure)

LXC containers use `exposure: l2` — service IP assigned directly to container interface:

```yaml
# lxc-grafana.yaml
@instance: lxc-grafana
@extends: obj.proxmox.lxc.debian12.grafana
host_ref: srv-gamayun
network:
  primary:
    type: bridge
    bridge_ref: inst.bridge.vmbr0   # Inherited via @on
    interface: eth0
  service:
    exposure: l2                    # L2 direct - IP goes to eth0
    vlan_ref: inst.vlan.servers
    host: 60
```

Compiler derives `_resolved_ip: 10.0.30.60/24` from `service.vlan_ref + host`.
For `exposure: l2`, this IP is assigned to `primary.interface` (eth0).

**Symmetry with other platforms:**
- LXC: `service._resolved_ip` → `primary.interface`
- Docker: `service._resolved_ip` → host bind address
- RouterOS: `service._resolved_ip` → NAT rule destination

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
      type: bridge
      bridge_ref: "@on:host.network.bridge_ref?"
      interface: "@on:host.network.interface?:eth0"
    service:
      exposure: l2    # LXC default: IP on container interface
      # vlan_ref + host at instance level
```

### D14: Security Matrix Integration (ADR 0110)

Container network model must integrate with zone-based firewall (ADR 0110).

#### D14a: Container Runtime Zone

Containers with NAT-based exposure (`dnat`, `port_publish`) run on internal networks
not visible to security matrix. Solution: define container runtime zone.

```yaml
# New trust zone for container internal networks
inst.trust_zone.container_runtime:
  security_level: 4        # Same as servers (internal infrastructure)
  isolated: true           # Cannot initiate to external zones
  description: "Container runtime internal networks (bridges, veths)"

# Internal network (not a real VLAN)
inst.network.container_bridge:
  cidr: 172.18.0.0/24
  trust_zone_ref: inst.trust_zone.container_runtime
  internal_only: true      # Not in VLAN table, internal bridge only
```

#### D14b: Zone Assignment by Exposure Type

| Exposure | Container Zone | Service Zone | Firewall Path |
|----------|---------------|--------------|---------------|
| `l2` | Same as service | service.vlan_ref → zone | Direct forward |
| `dnat` | container_runtime | service.vlan_ref → zone | NAT + forward |
| `port_publish` | container_runtime | Host zone | Host INPUT + forward |
| `routed` | container_runtime | Policy routes | Mangle + forward |

#### D14c: Generated Firewall Artifacts

For `exposure: dnat`:

```hcl
# 1. Address list entry for container
resource "routeros_ip_firewall_addr_list" "container_docker_adguard" {
  list    = "zone-container_runtime"
  address = "172.18.0.210"           # primary.address
  comment = "ADR-0118: docker-adguard container IP"
}

# 2. dst-nat rule: service IP → primary IP
resource "routeros_ip_firewall_nat" "dnat_docker_adguard_dns" {
  chain        = "dstnat"
  action       = "dst-nat"
  dst_address  = "192.168.88.210"    # service._resolved_ip
  to_addresses = "172.18.0.210"      # primary.address
  protocol     = "udp"
  dst_port     = "53"
  comment      = "ADR-0118: DNAT docker-adguard DNS"
}

# 3. Forward rule for NAT'd traffic
resource "routeros_ip_firewall_filter" "forward_dnat_docker_adguard_dns" {
  chain       = "forward"
  action      = "accept"
  dst_address = "172.18.0.210"
  protocol    = "udp"
  dst_port    = "53"
  comment     = "ADR-0118: Allow NAT'd traffic to docker-adguard"
  place_before = routeros_ip_firewall_filter.zone_drop_all_forward.id
}
```

For `exposure: l2`:

```hcl
# No NAT rules needed - container IP is directly in zone address list
# Zone forward rules from ADR 0110 apply directly
```

#### D14d: Security Matrix Extension

```yaml
# inst.security_matrix.mikrotik.yaml extension
address_space:
  vlan_refs:
    - inst.vlan.lan
    - inst.vlan.servers
    # ... existing VLANs

  # NEW: Internal container networks (not VLANs)
  internal_networks:
    - network_ref: inst.network.container_bridge
      zone_ref: inst.trust_zone.container_runtime

# Policy override for container access
policy_overrides:
  - name: user-to-container-services
    from_zone_ref: inst.trust_zone.user
    to_zone_ref: inst.trust_zone.container_runtime
    action: accept
    comment: Allow users to reach container services via DNAT
```

#### D14e: Validator Rules for Security Integration

| Code | Severity | Rule |
|------|----------|------|
| `E7880` | Error | `exposure: dnat` requires `service.ports` |
| `E7881` | Error | `primary.address` must be within known internal network |
| `W7882` | Warning | Container zone not in security matrix address_space |
| `E7883` | Error | NAT to zone with higher security_level without policy_override |

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
| **Subtotal (network model)** | ~31 | **~24h** |
| | | |
| **Security Integration (D14)** | | |
| Trust zone: container_runtime | 2 | 1h |
| Internal network class/instance | 2 | 1h |
| Security matrix extension | 1 | 1h |
| NAT rule generator (dnat exposure) | 1 | 3h |
| Forward rule generator for DNAT | 1 | 2h |
| Validators (E7880-E7883) | 1 | 2h |
| Security integration tests | 2 | 2h |
| **Subtotal (security)** | ~10 | **~12h** |
| | | |
| **Grand Total** | ~41 | **~36h** |

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
| | | | |
| **Security Integration (D14)** | | | |
| 8 | Trust Zone | Create inst.trust_zone.container_runtime | None |
| 9 | Network | Create inst.network.container_bridge | None |
| 10 | Matrix | Extend security_matrix with internal_networks | Low |
| 11 | Generator | Add NAT rule generation for dnat exposure | Medium |
| 12 | Generator | Add forward rules for NAT'd traffic | Medium |
| 13 | Validators | Enable E7880-E7883 security validators | After phase 11 |
| 14 | Deploy | Apply Terraform with new NAT/forward rules | **High** |

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
- ADR-0109: Network Segmentation with Zone-Based Architecture
- ADR-0110: Security Matrix and Trust Zone Configuration
- ADR-0111: IP Address Derivation from VLAN
- [MikroTik Container Documentation](https://help.mikrotik.com/docs/display/ROS/Container)
- D02 audit finding: 2026-09-09-topology-remediation-review.md
