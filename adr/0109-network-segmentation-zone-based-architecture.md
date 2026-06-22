# ADR 0109: Network Segmentation with Zone-Based Architecture

- Status: Proposed
- Date: 2026-06-22
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
- Trust zone class and objects defined but NOT instantiated
- Firewall policy class exists (ADR-0004) but not deployed

## Decision

### 1. Implement 4-zone VLAN architecture

| Zone | VLAN ID | CIDR | Purpose | Trust Level |
|------|---------|------|---------|-------------|
| Management | 10 | 192.168.10.0/24 | Router, switches, admin access | 5 (highest) |
| User | 20 | 192.168.20.0/24 | Laptops, phones, workstations | 3 |
| IoT | 30 | 192.168.30.0/24 | Smart home devices | 1 (isolated) |
| Guest | 40 | 192.168.40.0/24 | Visitor devices | 0 (untrusted) |

Existing VLANs preserved:
- VLAN 1 (192.168.88.0/24) — legacy LAN, migrate devices gradually
- VLAN 55 (192.168.55.0/24) — VPN Germany, unchanged

### 2. Deploy deny-by-default inter-zone policies

```yaml
zone_policies:
  # Guest isolation — internet only
  - from: guest
    to: [user, iot, servers, management]
    action: drop
    log: true

  # IoT isolation — cannot initiate to internal zones
  - from: iot
    to: [user, servers, management]
    action: drop
    log: true

  # User cannot access management
  - from: user
    to: management
    action: drop
    log: true

  # Internet access for all
  - from: any
    to: untrusted
    action: accept
```

### 3. Create topology instances

New files to create:
```
projects/home-lab/topology/instances/network/
├── inst.vlan.user.yaml
├── inst.vlan.iot.yaml
├── inst.vlan.guest.yaml
├── inst.vlan.mgmt.yaml
├── inst.trust_zone.user.yaml
├── inst.trust_zone.iot.yaml
├── inst.trust_zone.guest.yaml
└── inst.trust_zone.mgmt.yaml
```

### 4. Update router topology

Add to `rtr-mikrotik-chateau.yaml`:
- `vlans` section with 4 new VLAN definitions
- `firewall.zone_policies` section with deny rules
- WiFi SSID mappings for Guest and IoT

### 5. Migration phases

| Phase | Action | Risk |
|-------|--------|------|
| 0 | Current state | Baseline |
| 1 | Add VLANs to router | Low — additive only |
| 2 | Add WiFi SSIDs (Guest, IoT) | Medium — test first |
| 3 | Migrate devices to proper VLANs | High — plan carefully |
| 4 | Deploy firewall rules | Critical — test in lab |
| 5 | Deprecate VLAN 1 flat LAN | Final cleanup |

## Consequences

### Benefits

- **Reduced attack surface** — compromised IoT cannot access user devices
- **Guest isolation** — visitors cannot access internal resources
- **Management protection** — admin interfaces not exposed to users
- **Lateral movement prevention** — zone boundaries limit spread
- **Audit trail** — logging on deny rules for forensics
- **Topology-driven** — all config generated from source of truth

### Trade-offs

- **Migration complexity** — devices must be reassigned to proper VLANs
- **WiFi proliferation** — 5 SSIDs (Chateau, Chateau*, VPN-Germany, Guest, IoT)
- **DHCP management** — 6 DHCP pools to maintain
- **Potential disruption** — misconfigured rules can break connectivity

### Accepted risks

- **P8: Single router** — hardware budget constraint, home-lab scope
- **P9: No IDS/IPS** — RouterOS limitation, mitigate with external syslog

### Compatibility

- Existing VPN Germany VLAN 55 unchanged
- Legacy VLAN 1 preserved during migration
- Bridge VLAN filtering already enabled

## Implementation checklist

- [ ] Create VLAN instance files
- [ ] Create trust zone instance files
- [ ] Update rtr-mikrotik-chateau.yaml with vlans section
- [ ] Create firewall policy generator plugin
- [ ] Add WiFi SSID generator for Guest/IoT
- [ ] Write Ansible playbook for zone policy deployment
- [ ] Test in isolated environment before production
- [ ] Document rollback procedure

## References

- Analysis: SPC 7-step protocol (2026-06-22)
- Source: Habr article on NGFW network segmentation (ideco/1049514)
- Schema: `topology/class-modules/L2-network/network/class.network.trust_zone.yaml`
- Schema: `topology/class-modules/L2-network/network/class.network.vlan.yaml`
- Related: ADR-0004 (Firewall Policy References and Validation)
- Commit: (pending implementation)
