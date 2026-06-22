# ADR 0109: Network Segmentation with Zone-Based Architecture

- Status: Implemented
- Date: 2026-06-22
- Revised: 2026-06-22 (SPC analysis — aligned with existing topology objects)
- Deployed: 2026-06-22 (Phase 1 VLANs + Phase 4 Firewall)
- Related: ADR-0004 (Firewall Policy References)

## Context

Current network topology has critical security weaknesses identified via SPC analysis against NGFW best practices (Habr article on network segmentation):

**Problems identified:**

| ID | Problem | Severity |
|----|---------|----------|
| P1 | Flat LAN topology — all devices on single VLAN 1 (192.168.88.0/24) | Critical |
| P2 | No inter-zone firewall policies — allow-all by default | Critical |
| P3 | IoT devices not isolated — can access all LAN resources | High |
| P4 | No guest network — visitors share main network | High |
| P5 | Management access from user VLAN — no separation | Medium |
| P6 | Lateral movement possible between all devices | Critical |
| P7 | No logging on firewall rules | Medium |
| P8 | Single router — no redundancy | Low (accepted) |
| P9 | No IDS/IPS capability | Low (RouterOS limitation) |

**Current state:**
- MikroTik Chateau with bridge_vlan_filtering: true (capability exists)
- VPN Germany VLAN 55 already segmented (proof of concept)
- Trust zone classes, objects, and instances defined in topology (all 6 zones staged)
- VLAN objects and instances defined but not yet deployed on MikroTik
- Firewall policy instances exist (guest_isolated, iot_isolated) but not deployed

## Decision

### 1. Implement 6-zone VLAN architecture

**RFC1918 principle:** User-facing zones use `192.168.x.0/24`; infrastructure zones use `10.0.x.0/24`.
**VLAN ID convention:** VLAN ID matches CIDR 3rd octet for all user-facing zones.

| Zone | VLAN ID | CIDR | Purpose | Security Level |
|------|---------|------|---------|----------------|
| User | 10 | 192.168.10.0/24 | Laptops, phones, workstations | 3 |
| Guest | 20 | 192.168.20.0/24 | Visitor devices (isolated) | 0 (untrusted) |
| IoT | 30 | 192.168.30.0/24 | Smart home devices (isolated) | 1 |
| VPN block | 50–59 | 192.168.5x.0/24 | VPN tunnel devices (reserved range) | 2 |
| VPN Germany | 55 | 192.168.55.0/24 | Geo-routing via WireGuard (active) | 2 |
| Management | 99 | 10.0.99.0/24 | Router, switches, admin access | 5 (highest) |

Out-of-scope (Proxmox-internal, not MikroTik VLAN):
- Servers zone: 10.0.0.0/24 (managed by Proxmox vmbr0 bridge directly)

VLANs preserved unchanged:
- VLAN 1 (192.168.88.0/24) — legacy LAN, migrate devices gradually to VLAN 10
- VLAN 55 (192.168.55.0/24) — VPN Germany, active and unchanged

### 2. Deploy deny-by-default inter-zone policies

```yaml
zone_policies:
  # Guest isolation — internet only, deny all internal zones
  - from: guest
    to: [user, iot, servers, management]
    action: drop
    log: true

  # IoT isolation — cannot initiate to user or management
  - from: iot
    to: [user, management]
    action: drop
    log: true

  # User cannot access management plane
  - from: user
    to: management
    action: drop
    log: true

  # User can reach servers on specific ports only
  - from: user
    to: servers
    action: accept
    ports: [80, 443, 5432, 6379]

  # VPN zone — internet only, isolated from all internal zones
  - from: vpn_tunnel
    to: [user, iot, guest, servers, management]
    action: drop
    log: true

  # Allow internet access for all zones
  - from: any
    to: untrusted
    action: accept

  # Allow established/related return traffic
  - from: any
    to: any
    state: [established, related]
    action: accept
```

### 3. Topology instance state

All trust zone and VLAN instances are already present in the topology. This ADR
updates their VLAN IDs, CIDRs, and security levels to the canonical scheme above.

Files created/updated by this ADR:
```
topology/object-modules/network/
├── obj.network.vlan.user.yaml          ← CREATED (VLAN 10)
├── obj.network.vlan.guest.yaml         ← UPDATED (VLAN 20, CIDR 20.x)
├── obj.network.vlan.iot.yaml           ← UPDATED (VLAN 30, CIDR 30.x)
├── obj.network.vlan.servers.yaml       ← UPDATED (CIDR 10.0.0.0/24)
├── obj.network.trust_zone.user.yaml    ← UPDATED (security_level: 3)
├── obj.network.trust_zone.management.yaml ← UPDATED (security_level: 5)
└── obj.network.trust_zone.servers.yaml ← UPDATED (security_level: 4)

projects/home-lab/topology/instances/network/
├── inst.vlan.user.yaml                 ← CREATED
├── inst.vlan.guest.yaml                ← UPDATED (dhcp_range 20.x)
├── inst.vlan.iot.yaml                  ← UPDATED (dhcp_range 30.x)
├── inst.vlan.servers.yaml              ← UPDATED (ip_allocation 10.0.0.x)
├── inst.vlan.vpn_germany.yaml          ← UPDATED (comment: VLAN 55 ∈ VPN block 50-59)
└── inst.trust_zone.vpn_tunnel.yaml     ← UPDATED (security_level: 2, blocked_destinations)
```

### 4. Update router topology

Add to `rtr-mikrotik-chateau.yaml`:
- `vlans` section: VLAN 10 (user), 20 (guest), 30 (iot) definitions
- `firewall.zone_policies` section with deny rules from Section 2
- WiFi SSID mappings: Guest SSID → VLAN 20, IoT SSID → VLAN 30
- DNS: new VLAN interfaces (.10.1, .20.1, .30.1) forward to AdGuard container

### 5. Migration phases

| Phase | Action | Risk |
|-------|--------|------|
| 0 | Current state — VLAN 1 only active | Baseline |
| 1 | Add VLAN 10/20/30 interfaces to router | Low — additive only |
| 2 | Add Guest and IoT WiFi SSIDs | Medium — test DHCP first |
| 3 | Migrate devices to proper VLANs | High — per-device, plan MAC assignments |
| 4 | Deploy inter-zone firewall rules | Critical — validate in stages, have rollback ready |
| 5 | Deprecate VLAN 1 (192.168.88.0/24) | Final cleanup after Phase 3 complete |

**Rollback procedure (Phase 4):** remove zone_policies from firewall forward chain; VLAN interfaces remain intact; connectivity restores to pre-Phase-4 state without device reboots.

## Consequences

### Benefits

- **Reduced attack surface** — compromised IoT cannot access user devices
- **Guest isolation** — visitors cannot access internal resources
- **Management protection** — admin interfaces not exposed to users
- **Lateral movement prevention** — zone boundaries limit spread
- **Audit trail** — logging on deny rules for forensics
- **Topology-driven** — all config generated from source of truth
- **Consistent addressing** — VLAN ID = CIDR 3rd octet for all user-facing zones

### Trade-offs

- **Migration complexity** — devices must be reassigned to proper VLANs
- **WiFi proliferation** — 5 SSIDs (Chateau, Chateau*, VPN-Germany, Guest, IoT)
- **DHCP management** — 5 DHCP pools on MikroTik + 1 Proxmox-managed
- **Potential disruption** — misconfigured rules can break connectivity

### Accepted risks

- **P8: Single router** — hardware budget constraint, home-lab scope
- **P9: No IDS/IPS** — RouterOS limitation, mitigate with external syslog

### Compatibility

- Existing VPN Germany VLAN 55 unchanged (∈ VPN block 50–59)
- Legacy VLAN 1 preserved during migration
- Bridge VLAN filtering already enabled on MikroTik
- Servers zone (Proxmox vmbr0) unaffected by MikroTik VLAN changes

## Implementation checklist

- [x] Create/update VLAN object modules (user, guest, iot, servers)
- [x] Create/update trust zone security levels (user=3, management=5, servers=4, vpn=2)
- [x] Create inst.vlan.user.yaml
- [x] Update inst.vlan.guest.yaml, inst.vlan.iot.yaml, inst.vlan.servers.yaml
- [x] Fix inst.trust_zone.vpn_tunnel.yaml (security_level, blocked_destinations)
- [x] Update rtr-mikrotik-chateau.yaml with vlans section and zone_policies
- [x] Add WiFi SSID definitions for Guest (VLAN 20) and IoT (VLAN 30)
- [x] Write Ansible playbook for zone policy deployment
- [x] Validate topology compilation after all changes
- [x] Test in isolated environment before production (Phase 4)
- [x] Execute migration Phases 1–4 (VLANs + Firewall deployed 2026-06-22)
- [ ] Phase 5: Deprecate legacy VLAN 1 after device migration

## References

- Analysis: SPC 7-step protocol (2026-06-22)
- Source: Habr article on NGFW network segmentation (ideco/1049514)
- Schema: `topology/class-modules/L2-network/network/class.network.trust_zone.yaml`
- Schema: `topology/class-modules/L2-network/network/class.network.vlan.yaml`
- Schema: `topology/class-modules/L2-network/network/class.network.firewall_policy.yaml`
- Related: ADR-0004 (Firewall Policy References and Validation)
