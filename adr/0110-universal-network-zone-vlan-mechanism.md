# ADR 0110: Security Matrix and Trust Zone Configuration

- Status: Proposed
- Date: 2026-06-22
- Revised: 2026-06-22 (SPC analysis + Class→Object→Instance + Multi-platform adapters)
- Revised: 2026-06-22 (SPC Step 6 — M1-B two-matrix + Trust Zone/VLAN separation)
- Revised: 2026-06-22 (Split: IP derivation moved to ADR-0111)
- Related: ADR-0109 (Network Segmentation), ADR-0111 (IP Address Derivation), ADR-0063 (Plugin Microkernel), ADR-0074 (V5 Generator Architecture)
- Implementation: [Network Security Implementation Plan](../docs/plans/network-security-implementation-plan.md)

## SPC Revision Note (2026-06-22)

SPC Step 6 incorporates two architectural decisions (IP derivation moved to ADR-0111):

**M1-B — One matrix per enforcer:**
The `managed_by_ref` field remains a single reference. Each enforcement plane
gets its own `inst.security_matrix.*` instance:
- `inst.security_matrix.mikrotik` — perimeter enforcement (rtr-mikrotik-chateau, RouterOS)
- `inst.security_matrix.proxmox` — internal enforcement (srv-gamayun, Proxmox VE)

**Trust Zone vs VLAN — Entity Separation:**
Trust Zone and VLAN are separate entities. Multiple VLANs can belong to one Trust Zone.
Security matrix operates on Zones; firewall rules are generated for all VLAN CIDRs
within each zone. See Section 1.5.

## Context

The current network zone and VLAN configuration is distributed across multiple locations:

| Location | Content | Problem |
|----------|---------|---------|
| `topology/class-modules/L2-network/` | Class definitions for trust_zone, vlan | Schema only |
| `topology/object-modules/network/` | Object definitions (6 zones, 7 VLANs) | Properties scattered |
| `projects/home-lab/topology/instances/network/` | Instance bindings | Manual synchronization |
| `rtr-mikrotik-chateau.yaml` | Router vlans, zone_policies sections | Duplication |

**Problems identified:**

| ID | Problem | Impact |
|----|---------|--------|
| P1 | Zone/VLAN definitions duplicated across 4+ locations | Drift risk |
| P2 | No central policy matrix | Incomplete security view |
| P3 | VLAN ID in object must manually match router config | Manual errors |
| P4 | Instances are hand-authored, not generated | Labor intensive |
| P5 | Validation happens at instance level only | Late error detection |
| P6 | No single file to review network security posture | Audit difficulty |
| P7 | Firewall policies manually written, not derived | Inconsistency risk |

**ADR-0109** established the zone-based architecture but did not address the configuration mechanism. This ADR provides the implementation mechanism with automatic security matrix derivation.

## Decision

### 1. Class → Object → Instance Hierarchy

The security matrix follows the standard topology pattern, enabling different projects
to have different matrices while sharing common templates.

```
CLASS LEVEL (schema)
├── class.network.trust_zone          ← EXISTS
├── class.network.vlan                ← EXISTS
└── class.network.security_matrix     ← NEW: Matrix schema

OBJECT LEVEL (reusable templates)
├── obj.network.trust_zone.*          ← EXISTS (6 zones)
├── obj.network.vlan.*                ← EXISTS
└── obj.network.security_matrix.soho  ← NEW: SOHO network template

INSTANCE LEVEL (per project)
├── projects/home-lab/topology/instances/network/
│   ├── inst.trust_zone.*             ← EXISTS
│   ├── inst.vlan.*                   ← EXISTS
│   └── inst.security_matrix.home_lab ← NEW: Project-specific matrix
│
├── projects/other-project/topology/instances/network/
│   └── inst.security_matrix.other    ← Different matrix for other project
```

#### 1.1 Class Definition: `class.network.security_matrix`

```yaml
# topology/class-modules/L2-network/network/class.network.security_matrix.yaml
@class: class.network.security_matrix
@title: Network Security Matrix
@description: Zone-to-zone security policy matrix with automatic rule derivation
@layer: L2
@version: 1.0.0

properties:
  required:
    - name
    - zone_refs
  optional:
    - description
    - defaults
    - policy_overrides
    - device_assignments
    - managed_by_ref

property_schemas:
  name:
    type: string
    description: Matrix identifier
  zone_refs:
    type: array
    items:
      type: string
      format: instance_ref
      target_class: class.network.trust_zone
    description: Trust zones participating in this matrix
  defaults:
    type: object
    properties:
      dns_servers:
        type: array
        items: { type: string, format: ipv4 }
      mtu:
        type: integer
        default: 1500
      dhcp_lease_time:
        type: string
        default: "30m"
  policy_overrides:
    type: array
    items:
      type: object
      properties:
        name: { type: string }
        from_zone_ref: { type: string, format: instance_ref }
        to_zone_ref: { type: string, format: instance_ref }
        action: { type: string, enum: [accept, drop] }
        ports: { type: object }
        log: { type: boolean, default: false }
    description: Exceptions to auto-derived matrix rules
  device_assignments:
    type: array
    items:
      type: object
      properties:
        device_ref: { type: string, format: instance_ref }
        vlan_ref: { type: string, format: instance_ref }
        static_ip: { type: string, format: ipv4 }
  managed_by_ref:
    type: string
    format: instance_ref
    target_class: class.router
```

#### 1.2 Object Template: `obj.network.security_matrix.soho`

```yaml
# topology/object-modules/network/obj.network.security_matrix.soho.yaml
@object: obj.network.security_matrix.soho
@class_ref: class.network.security_matrix
@title: SOHO Network Security Matrix
@description: Standard security matrix for Small Office/Home Office networks

name: soho-default

# References to standard SOHO zones (objects, resolved to instances per project)
zone_refs:
  - obj.network.trust_zone.untrusted
  - obj.network.trust_zone.guest
  - obj.network.trust_zone.iot
  - obj.network.trust_zone.user
  - obj.network.trust_zone.servers
  - obj.network.trust_zone.management

defaults:
  dns_servers: [1.1.1.1, 8.8.8.8]
  mtu: 1500
  dhcp_lease_time: "30m"

# Standard SOHO policy overrides
policy_overrides:
  - name: user-to-servers-http
    from_zone_ref: obj.network.trust_zone.user
    to_zone_ref: obj.network.trust_zone.servers
    action: accept
    ports:
      tcp: [80, 443]
    comment: User HTTP/HTTPS access to servers
```

#### 1.3 Instances: Two Matrices, One Per Enforcer (M1-B)

**Design decision (SPC Step 6):** One `inst.security_matrix.*` per enforcement plane.
`managed_by_ref` is a single reference. The two planes are independent.

```
inst.security_matrix.mikrotik   →  managed_by_ref: rtr-mikrotik-chateau
                                   enforcement_plane: perimeter
                                   scope: inter-VLAN / WAN

inst.security_matrix.proxmox    →  managed_by_ref: srv-gamayun
                                   enforcement_plane: internal
                                   scope: intra-servers-zone LXC/VM
```

**inst.security_matrix.mikrotik** (perimeter):
```yaml
# projects/home-lab/topology/instances/network/inst.security_matrix.mikrotik.yaml
@instance: inst.security_matrix.mikrotik
@extends: obj.network.security_matrix.soho
@group: network

managed_by_ref: rtr-mikrotik-chateau

zone_refs:
  - inst.trust_zone.untrusted
  - inst.trust_zone.guest
  - inst.trust_zone.iot
  - inst.trust_zone.vpn_tunnel
  - inst.trust_zone.user
  - inst.trust_zone.servers
  - inst.trust_zone.management

address_space:
  vlan_refs:
    - inst.vlan.lan
    - inst.vlan.user
    - inst.vlan.guest
    - inst.vlan.iot
    - inst.vlan.vpn_germany
    - inst.vlan.management
    - inst.vlan.servers   # perimeter sees servers as a zone, not its internal layout

policy_overrides:
  - name: user-to-servers-db
    from_zone_ref: inst.trust_zone.user
    to_zone_ref: inst.trust_zone.servers
    action: accept
    ports: { tcp: [5432, 6379] }
  - name: management-to-servers-full
    from_zone_ref: inst.trust_zone.management
    to_zone_ref: inst.trust_zone.servers
    action: accept
```

**inst.security_matrix.proxmox** (internal):
```yaml
# projects/home-lab/topology/instances/network/inst.security_matrix.proxmox.yaml
@instance: inst.security_matrix.proxmox
@extends: obj.network.security_matrix.proxmox_servers
@group: network

managed_by_ref: srv-gamayun

zone_refs:
  - inst.trust_zone.servers

address_space:
  vlan_refs:
    - inst.vlan.servers   # canonical: cidr 10.0.30.0/24, gateway 10.0.30.1

policy_overrides:
  - name: prometheus-scrape
    from_zone_ref: inst.trust_zone.servers
    to_zone_ref: inst.trust_zone.servers
    action: accept
    ports: { tcp: [9090, 9100, 9187, 9121] }
  - name: nginx-proxy-to-backends
    from_zone_ref: inst.trust_zone.servers
    to_zone_ref: inst.trust_zone.servers
    action: accept
    ports: { tcp: [80, 443, 3000, 8080, 8443] }
  - name: app-to-postgresql
    from_zone_ref: inst.trust_zone.servers
    to_zone_ref: inst.trust_zone.servers
    action: accept
    ports: { tcp: [5432] }
  - name: app-to-redis
    from_zone_ref: inst.trust_zone.servers
    to_zone_ref: inst.trust_zone.servers
    action: accept
    ports: { tcp: [6379] }
```

> **Multi-Project Support:** Each project can have its own `inst.security_matrix.*`
> instances with different zones, policies, and enforcers. The matrix calculation
> runs per-instance, not globally.

#### 1.5 Trust Zone vs VLAN: Entity Separation

**Key Principle:** Trust Zone and VLAN are separate entities with different concerns.

| Entity | Concern | Examples |
|--------|---------|----------|
| **Trust Zone** | Security policy, access control | security_level, isolated, capabilities |
| **VLAN** | Network segment, addressing | vlan_id, cidr, gateway, dhcp |

**Relationship: Many VLANs → One Trust Zone**

```
inst.trust_zone.servers (security_level: 4)
    │
    ├── inst.vlan.servers_db        (10.0.30.0/24, VLAN 30)
    ├── inst.vlan.servers_app       (10.0.31.0/24, VLAN 31)
    └── inst.vlan.servers_monitor   (10.0.32.0/24, VLAN 32)

inst.trust_zone.vpn_tunnel (security_level: 2, isolated: true)
    │
    ├── inst.vlan.vpn_germany       (192.168.55.0/24, VLAN 55)
    ├── inst.vlan.vpn_netherlands   (192.168.56.0/24, VLAN 56)  # future
    └── inst.vlan.vpn_usa           (192.168.57.0/24, VLAN 57)  # future
```

**VLAN references Trust Zone:**

```yaml
# inst.vlan.servers_db.yaml
@instance: inst.vlan.servers_db
@extends: obj.network.vlan.servers

vlan_id: 30
cidr: 10.0.30.0/24
gateway: 10.0.30.1
trust_zone_ref: inst.trust_zone.servers   # ← Zone assignment
```

**Security Matrix operates on Zones, not VLANs:**

The matrix calculates `M[from_zone][to_zone]`. When generating firewall rules:
1. Resolve all VLANs belonging to `from_zone` → get their CIDRs
2. Resolve all VLANs belonging to `to_zone` → get their CIDRs
3. Generate rules for all CIDR combinations

```
Matrix cell: servers → user = ALLOW (security_level 4 > 3)

VLANs in servers zone:
  - 10.0.30.0/24 (servers_db)
  - 10.0.31.0/24 (servers_app)

VLANs in user zone:
  - 192.168.10.0/24 (user)

Generated rules (Terraform):
  - ALLOW 10.0.30.0/24 → 192.168.10.0/24
  - ALLOW 10.0.31.0/24 → 192.168.10.0/24
```

**Compiler publishes zone-to-vlans mapping:**

```python
ctx.publish("zone_vlans", {
    "inst.trust_zone.servers": [
        "inst.vlan.servers_db",
        "inst.vlan.servers_app",
        "inst.vlan.servers_monitor"
    ],
    "inst.trust_zone.user": [
        "inst.vlan.user"
    ],
    # ...
})
```

#### 1.6 IP Address Derivation

> **See ADR-0111:** IP Address Derivation from VLAN Instances
>
> IP addresses in workload instances use `vlan_ref + host` pattern.
> The VLAN CIDR is the single source of truth. ADR-0111 defines:
> - Resolution algorithm (vlan_ref + host → full IP)
> - Validation rules (E7861-E7865)
> - Migration plan for existing hardcoded IPs

#### 1.4 Multi-Platform Target Devices

The security matrix is **platform-agnostic**. The `managed_by_ref` determines which
generator adapter produces the output. Different routers require different script formats.

```
inst.security_matrix.mikrotik (perimeter)
         │
         │ managed_by_ref
         ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Target Device Resolution                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  inst.device.rtr_mikrotik_chateau                               │
│  ├── class_ref: class.mikrotik.router                           │
│  └── Adapter: TerraformMikroTikGenerator                        │
│      └── Output: routeros_ip_firewall_filter resources          │
│                                                                  │
│  inst.device.rtr_slate_travel                                   │
│  ├── class_ref: class.openwrt.router                            │
│  └── Adapter: TerraformOpenWrtGenerator (future)                │
│      └── Output: uci firewall zone/forwarding resources         │
│                                                                  │
│  inst.device.pve_node_main                                      │
│  ├── class_ref: class.proxmox.node                              │
│  └── Adapter: TerraformProxmoxGenerator (future)                │
│      └── Output: proxmox_virtual_environment_firewall_rules     │
│                                                                  │
│  inst.device.rtr_pfsense_dc (hypothetical)                      │
│  ├── class_ref: class.pfsense.router                            │
│  └── Adapter: AnsiblePfSenseGenerator (future)                  │
│      └── Output: pfsense_rule Ansible modules                   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

**Adapter Selection Logic:**

| Device Class | OS/Platform | Generator Adapter | Output Format |
|--------------|-------------|-------------------|---------------|
| `class.mikrotik.*` | RouterOS | `terraform_mikrotik_generator` | HCL (routeros provider) |
| `class.openwrt.*` | OpenWrt | `terraform_openwrt_generator` | HCL (uci provider) |
| `class.proxmox.*` | Proxmox VE | `terraform_proxmox_generator` | HCL (bpg/proxmox provider) |
| `class.pfsense.*` | pfSense | `ansible_pfsense_generator` | YAML (pfsense modules) |
| `class.vyos.*` | VyOS | `terraform_vyos_generator` | HCL (vyos provider) |

**Proxmox Firewall Specifics:**

Proxmox VE has a built-in firewall at three levels:
- **Datacenter level** — rules applied to all nodes
- **Node level** — rules for specific hypervisor
- **VM/CT level** — rules for individual guests

The servers zone (`10.0.0.0/24`) is managed by Proxmox vmbr0 bridge. The security matrix
can generate Proxmox firewall rules for VM/CT isolation within this zone.

```hcl
# Example: Proxmox firewall rule from security matrix
resource "proxmox_virtual_environment_firewall_rules" "vm_isolation" {
  node_name = "pve"
  vm_id     = 100

  rule {
    type    = "in"
    action  = "DROP"
    source  = "10.0.0.0/24"
    dest    = "10.0.0.100"
    log     = "warning"
    comment = "ADR-0110: Deny intra-zone by default"
  }
}
```

**Current Scope:** This ADR focuses on MikroTik (RouterOS) as the primary target,
since `rtr-mikrotik-chateau` is the central network device. OpenWrt adapter for
`rtr-slate` can be implemented later using the same security matrix.

**Key Principle:** The security matrix (`inst.security_matrix.*`) is **declarative intent**.
The generator adapter translates intent to platform-specific implementation.

```yaml
# Same matrix, different targets
inst.security_matrix.home_lab:
  managed_by_ref: inst.device.rtr_mikrotik_chateau  # → RouterOS firewall

inst.security_matrix.travel_kit:
  managed_by_ref: inst.device.rtr_slate_travel      # → OpenWrt nftables
```

### 2. Security Matrix Design (Zone × Zone)

The core innovation is automatic derivation of firewall policies from zone security levels.

#### 2.1 Matrix Structure

```
              TO ZONE
           ┌─────────────────────────────────────────────────────────┐
           │ untrusted │ guest │ iot │ vpn │ user │ servers │ mgmt  │
           │   (0)     │  (0)  │ (1) │ (2) │  (3) │   (4)   │  (5)  │
    ┌──────┼───────────┼───────┼─────┼─────┼──────┼─────────┼───────┤
    │untr. │     -     │   -   │  -  │  -  │   -  │    -    │   -   │
F   │guest │   ALLOW   │   -   │ DENY│ DENY│ DENY │  DENY   │ DENY  │
R   │iot   │   ALLOW   │ DENY  │  -  │ DENY│ DENY │  DENY   │ DENY  │
O   │vpn   │   ALLOW   │ DENY  │ DENY│  -  │ DENY │  DENY   │ DENY  │
M   │user  │   ALLOW   │ ALLOW │ALLOW│ALLOW│   -  │ *POLICY*│ DENY  │
    │serv. │   ALLOW   │ ALLOW │ALLOW│ALLOW│ALLOW │    -    │ DENY  │
    │mgmt  │   ALLOW   │ ALLOW │ALLOW│ALLOW│ALLOW │  ALLOW  │   -   │
    └──────┴───────────┴───────┴─────┴─────┴──────┴─────────┴───────┘

Legend:
  ALLOW    = Implicit allow (higher→lower security level, "downhill")
  DENY     = Implicit deny (lower→higher security level, "uphill")
  *POLICY* = Explicit policy_override required (partial allow with ports)
  -        = Same zone or N/A
```

#### 2.2 Matrix Calculation Rules

The matrix cell value `M[from_zone][to_zone]` is calculated as:

| Rule | Condition | Result | Logging |
|------|-----------|--------|---------|
| R1 | `from_zone == to_zone` | ALLOW | No |
| R2 | `from_zone.isolated == true AND to_zone != untrusted` | DENY | Yes |
| R3 | `from_zone.security_level > to_zone.security_level` | ALLOW | No |
| R4 | `from_zone.security_level < to_zone.security_level` | DENY | Yes |
| R5 | `from_zone.security_level == to_zone.security_level` | DENY | Yes |
| R6 | Explicit `policy_override` exists | Override action | Per policy |

**Rule Evaluation Order (CRITICAL):**

```
R6 (explicit override) → checked FIRST, short-circuits all other rules
       ↓ (no match)
R1 (same zone) → ALLOW, stop
       ↓ (different zones)
R2 (isolated source) → if isolated AND dest != untrusted: DENY, stop
       ↓ (not isolated OR dest == untrusted)
R3/R4/R5 (security level comparison) → apply based on level delta
```

> **Implementation Note:** R2 MUST be evaluated before R3. An isolated zone with
> `security_level: 2` must NOT be allowed to reach `security_level: 1` zones despite
> R3 (downhill) logic. Isolation overrides security level hierarchy.

#### 2.3 Rule Rationale

- **R1 (Same zone):** Intra-zone traffic allowed by default — devices in same security domain can communicate freely.
- **R2 (Isolated):** Isolated zones (guest, IoT, VPN) can only reach internet — prevents lateral movement.
- **R3 (Downhill):** Higher security can initiate to lower — management can reach everything, users can reach IoT.
- **R4 (Uphill):** Lower security cannot initiate to higher — IoT cannot reach management.
- **R5 (Same level):** Zones at same level denied by default — requires explicit policy.
- **R6 (Override):** Explicit policies override calculated values — for partial access (specific ports).

#### 2.4 Intra-Zone Micro-Segmentation (R1 Exception)

For enforcement planes like Proxmox (srv-gamayun), intra-zone traffic may require
explicit policy_overrides even though R1 says "same zone = ALLOW".

**Use case:** `inst.security_matrix.proxmox` manages servers→servers traffic.
Default R1 would allow all, but we want explicit port-based rules.

**Solution:** When `enforcement_plane: internal`, R1 behavior changes:

```
R1a (perimeter): from_zone == to_zone → ALLOW (implicit, no rules generated)
R1b (internal):  from_zone == to_zone → DENY by default, require policy_overrides
```

This is controlled by the `enforcement_plane` property in the matrix instance:

```yaml
inst.security_matrix.proxmox:
  enforcement_plane: internal   # ← Triggers R1b behavior
  # ... policy_overrides required for intra-zone communication
```

### 3. Compilation Pipeline

```
┌─────────────────────────────────────────────────────────────────────┐
│                        COMPILE STAGE                                │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  inst.security_matrix.*                                             │
│  inst.trust_zone.*         (from normalized_rows)                   │
│  inst.vlan.*                                                        │
│         │                                                           │
│         ▼                                                           │
│  ┌──────────────────────────────────────────┐                       │
│  │ SecurityMatrixCompiler                   │                       │
│  │ ─────────────────────────────            │                       │
│  │ 1. Find inst.security_matrix.* rows     │                       │
│  │ 2. Resolve zone_refs to inst.trust_zone │                       │
│  │ 3. Build Zone×Zone matrix per instance  │                       │
│  │ 4. Merge policy_overrides (obj + inst)  │                       │
│  │ 5. Publish per-project matrices         │                       │
│  └──────────────────────────────────────────┘                       │
│         │                                                           │
│         ├── ctx.publish("security_matrices", {                      │
│         │       "inst.security_matrix.home_lab": {...}              │
│         │   })                                                      │
│         ├── ctx.publish("matrix_by_router", {                       │
│         │       "inst.device.rtr_mikrotik_chateau": "inst.security_matrix.home_lab"
│         │   })                                                      │
│         └── Per-matrix data:                                        │
│             - zones: resolved trust_zone instances                  │
│             - vlans: associated VLAN instances                      │
│             - matrix: Zone×Zone calculated policies                 │
│             - policy_overrides: merged from object + instance       │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                       VALIDATE STAGE                                │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌────────────────────────────────┐                                 │
│  │ SecurityMatrixValidator        │                                 │
│  │ ──────────────────────────     │                                 │
│  │ E7850: VLAN ID collision       │                                 │
│  │ E7851: CIDR overlap            │                                 │
│  │ E7852: Invalid zone reference  │                                 │
│  │ W7853: Unreachable zone pair   │                                 │
│  │ W7854: Missing policy_override │                                 │
│  └────────────────────────────────┘                                 │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                       GENERATE STAGE                                │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  security_matrix ────┬──► TerraformMikroTikGenerator                │
│                      │    ├── address_list per zone CIDR            │
│                      │    ├── firewall forward rules from matrix    │
│                      │    └── VLAN interface resources              │
│                      │                                              │
│                      ├──► DocsGenerator                             │
│                      │    └── security-matrix.md (audit view)       │
│                      │                                              │
│                      └──► AnsibleInventoryGenerator                 │
│                           └── zone-aware host grouping              │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### 4. Terraform Generation (Primary Target)

The security matrix is consumed by `terraform_mikrotik_generator` to produce:

#### 4.1 Address Lists

```hcl
# Generated from zones[*].cidr via vlans
resource "routeros_ip_firewall_addr_list" "zone_user" {
  list    = "zone-user"
  address = "192.168.10.0/24"
  comment = "Trust zone: user (security_level=3)"
}

resource "routeros_ip_firewall_addr_list" "zone_guest" {
  list    = "zone-guest"
  address = "192.168.20.0/24"
  comment = "Trust zone: guest (security_level=0, isolated)"
}
```

#### 4.2 Firewall Forward Rules

```hcl
# Generated from security_matrix[guest][user] = DENY
resource "routeros_ip_firewall_filter" "deny_guest_to_user" {
  chain            = "forward"
  action           = "drop"
  src_address_list = "zone-guest"
  dst_address_list = "zone-user"
  log              = true
  log_prefix       = "DENY:guest→user"
  comment          = "ADR-0110: isolated zone cannot reach user (R2)"
}

# Generated from security_matrix[user][servers] with policy_override
resource "routeros_ip_firewall_filter" "allow_user_to_servers_http" {
  chain            = "forward"
  action           = "accept"
  src_address_list = "zone-user"
  dst_address_list = "zone-servers"
  protocol         = "tcp"
  dst_port         = "80,443"
  comment          = "ADR-0110: user-to-servers-allowed (R6 override)"
}
```

#### 4.3 Rule Ordering (CRITICAL)

MikroTik has a **default-allow** policy — if no rule matches, traffic is permitted.
This differs from most enterprise firewalls. Explicit ordering is mandatory.

**Terraform Generation Order:**

| Order | Rule Type | Terraform `place_before` | Action |
|-------|-----------|--------------------------|--------|
| 1 | Established/related | (first) | accept |
| 2 | Explicit policy_override ACCEPT | after established | accept |
| 3 | Matrix-derived DENY (isolated zones) | after accepts | drop + log |
| 4 | Matrix-derived DENY (uphill traffic) | after isolated | drop + log |
| 5 | Matrix-derived ALLOW (downhill traffic) | after denies | accept |
| 6 | **Final drop-all** | (last) | drop + log |

**Implementation Requirement:**

```hcl
# Each rule must use place_before to maintain order
resource "routeros_ip_firewall_filter" "established_related" {
  chain       = "forward"
  action      = "accept"
  connection_state = "established,related"
  comment     = "ADR-0110: Stateful return traffic"
  # place_before = (implicit first)
}

resource "routeros_ip_firewall_filter" "deny_guest_to_user" {
  chain            = "forward"
  action           = "drop"
  src_address_list = "zone-guest"
  dst_address_list = "zone-user"
  log              = true
  comment          = "ADR-0110: R2 isolated zone deny"
  place_before     = routeros_ip_firewall_filter.drop_all_forward.id
}
```

#### 4.4 Final Drop Rule (MANDATORY)

**Rationale:** MikroTik RouterOS default-allow requires explicit drop-all at chain end.
Without this rule, any traffic not matching previous rules will be **permitted**.

```hcl
# MUST be generated LAST in forward chain
resource "routeros_ip_firewall_filter" "drop_all_forward" {
  chain   = "forward"
  action  = "drop"
  log     = true
  log_prefix = "DROP:final"
  comment = "ADR-0110: Final drop-all (implicit deny policy)"
}
```

> **Security Note:** This rule implements the "implicit deny" principle from
> [Cisco Zone-Based Firewall](https://www.cisco.com/c/en/us/support/docs/security/ios-firewall/98628-zone-design-guide.html)
> best practices. All matrix-derived rules must use `place_before` referencing this resource.

### 5. Validation Rules

**VLAN & Zone Validation:**

| Code | Severity | Rule |
|------|----------|------|
| E7850 | Error | VLAN ID must be unique across all VLANs |
| E7851 | Error | VLAN CIDRs must not overlap |
| E7852 | Error | VLAN must have trust_zone_ref pointing to existing zone |
| E7853 | Error | policy_override from/to must reference existing zones |
| W7860 | Warning | Zone referenced in matrix has no VLANs assigned (empty zone) |

**IP Address Derivation Validation:** See ADR-0111 (E7861-E7865)

**Firewall Generation Validation:**

| Code | Severity | Rule |
|------|----------|------|
| E7854 | Error | Final drop-all rule missing in generated Terraform |
| W7855 | Warning | Zone pair at same security_level has no policy_override |
| W7856 | Warning | Isolated zone has policy_override to non-untrusted (likely redundant) |
| W7857 | Warning | DENY rule without logging enabled (audit gap) |
| W7858 | Warning | Rule ordering violation detected (place_before missing) |

**Statistics:**

| Code | Severity | Rule |
|------|----------|------|
| I7859 | Info | Matrix statistics: X allow, Y deny, Z override across N zones |
| I7865 | Info | Zone-VLAN mapping: zone X has Y VLANs |

### 6. Backward Compatibility

- Existing object modules (obj.network.trust_zone.*, obj.network.vlan.*) remain unchanged
- Existing instances (inst.trust_zone.*, inst.vlan.*) continue to work
- inst.security_matrix.* is optional; projects without it use existing workflow
- Migration is gradual: create instance when ready
- Router instance vlans/zone_policies sections deprecated once matrix is active
- Zone_refs in matrix reference existing trust_zone instances

### 7. Input/Output Artifacts

**Source (Class → Object → Instance):**

| Artifact | Location | Purpose |
|----------|----------|---------|
| `class.network.security_matrix.yaml` | `topology/class-modules/L2-network/network/` | Schema definition |
| `obj.network.security_matrix.soho.yaml` | `topology/object-modules/network/` | Reusable template |
| `inst.security_matrix.home_lab.yaml` | `projects/home-lab/topology/instances/network/` | Project-specific config |

**Generated Output:**

| Artifact | Location | Purpose |
|----------|----------|---------|
| `firewall.tf` | `generated/home-lab/terraform/mikrotik/` | MikroTik firewall rules |
| `addresses.tf` | `generated/home-lab/terraform/mikrotik/` | Address list resources |
| `security-matrix.md` | `generated/home-lab/docs/` | Human-readable matrix |
| `security-matrix.json` | `generated/home-lab/` | Machine-readable matrix |

### 8. Security Matrix JSON Schema

```json
{
  "schema_version": 1,
  "generated_at": "2026-06-22T12:00:00Z",
  "zones": {
    "guest": { "security_level": 0, "isolated": true, "cidr": "192.168.20.0/24" }
  },
  "matrix": {
    "guest": {
      "user": {
        "action": "deny",
        "reason": "R2: isolated zone cannot reach user",
        "rule": "R2",
        "log": true,
        "terraform_resource": "routeros_ip_firewall_filter.deny_guest_to_user"
      }
    }
  },
  "policy_overrides": [
    {
      "name": "user-to-servers-allowed",
      "from": "user",
      "to": "servers",
      "action": "accept",
      "ports": { "tcp": [80, 443] }
    }
  ],
  "statistics": {
    "total_pairs": 42,
    "allow": 21,
    "deny": 15,
    "override": 6
  }
}
```

## Consequences

### Benefits

- **Class → Object → Instance pattern** — consistent with entire topology model
- **Multi-project support** — each project can have different security matrices
- **Reusable templates** — obj.network.security_matrix.soho can be shared
- **Automatic policy derivation** from security levels — no manual rule writing
- **Audit-friendly** matrix visualization for security review
- **Early validation** at compile time before deployment
- **Consistent generation** of Terraform resources
- **Declarative** configuration replaces imperative scripting
- **Terraform-first** deployment (preferred over Ansible)

### Trade-offs

- **New class/object to maintain** (class.network.security_matrix, obj.*.soho)
- **Learning curve** for matrix calculation rules
- **Less flexibility** than hand-written rules (by design — security by convention)
- **Instance per project** — each project needs its own inst.security_matrix.*

### Migration Path

| Phase | Action | Risk | Rollback |
|-------|--------|------|----------|
| 1 | Create class.network.security_matrix | Low | Delete class file |
| 2 | Create obj.network.security_matrix.soho | Low | Delete object file |
| 3 | Create inst.security_matrix.home_lab | Low | Delete instance file |
| 4 | Implement compiler plugin with matrix calculation | Low | Unregister plugin |
| 5 | Implement validation plugins | Low | Disable validators |
| 6 | Enhance terraform_mikrotik_generator to consume matrix | Medium | Revert generator |
| 7 | **BACKUP** + Generate Terraform + validate with `terraform plan` | Medium | Restore backup |
| 8 | `terraform apply` to MikroTik | **High** | Restore backup |
| 9 | Remove duplicated vlans/zone_policies from router instance | Low | Re-add sections |
| 10 | Delete legacy network-zones.yaml if exists | Low | Restore from git |

#### Phase 5-6: Backup Requirement (MANDATORY)

**RouterOS does not support commit-confirmed.** Mistakes in firewall rules are immediate
and can lock you out. Before any `terraform apply`:

```bash
# 1. Create backup on MikroTik
ssh admin@192.168.88.1 '/system backup save name=pre-adr0110'

# 2. Export configuration (human-readable)
ssh admin@192.168.88.1 '/export file=pre-adr0110-export'

# 3. Verify backup exists
ssh admin@192.168.88.1 '/file print where name~"pre-adr0110"'

# 4. Only then apply
terraform apply
```

**Rollback procedure:**
```bash
# If locked out, access via MAC-Telnet or serial console
/system backup load name=pre-adr0110
/system reboot
```

> **Reference:** [MikroTik Terraform Getting Started](https://mirceanton.com/posts/mikrotik-terraform-getting-started/)
> — "RouterOS mistakes are immediate; backup before apply."

## Implementation Plan

### Phase 0: Prerequisites
**Goal:** Ensure environment is ready for implementation.
**Exit Criteria:** All checks pass, no blockers.

| Task | Owner | Depends | Risk |
|------|-------|---------|------|
| Verify topology compiles without errors | — | — | Low |
| Verify MikroTik REST API accessible | — | — | Low |
| Ensure Terraform provider installed | — | — | Low |
| Create feature branch `feat/adr-0110-security-matrix` | — | — | Low |

### Phase 1: Topology Structure (Class/Object/Instance)
**Goal:** Define schema and create instances.
**Exit Criteria:** `task build` passes, model.lock updated.

| Task | Status | Depends | Files |
|------|--------|---------|-------|
| Create `class.network.security_matrix` | ☐ | — | `topology/class-modules/L2-network/network/` |
| Create `obj.network.security_matrix.soho` | ☐ | class | `topology/object-modules/network/` |
| Create `obj.network.security_matrix.proxmox_servers` | ☐ | class | `topology/object-modules/network/` |
| Create `inst.security_matrix.mikrotik` | ☐ | obj.soho | `projects/home-lab/topology/instances/network/` |
| Create `inst.security_matrix.proxmox` | ☐ | obj.proxmox | `projects/home-lab/topology/instances/network/` |
| Fix `obj.network.vlan.servers` CIDR | ☐ | — | `topology/object-modules/network/` |
| Run `task framework:lock-refresh` | ☐ | all above | — |

**Acceptance Test:**
```bash
task build && task validate  # Must pass
```

### Phase 2: IP Address Derivation Migration

> **See ADR-0111** for IP derivation implementation plan.
> This phase migrates 9 LXC + 2 server instances to `vlan_ref + host` pattern.

### Phase 3: Compiler Plugin
**Goal:** Build security matrix at compile time.
**Exit Criteria:** `security_matrices` published to context.

| Task | Status | Depends | Location |
|------|--------|---------|----------|
| Create `security_matrix_compiler.py` | ☐ | Phase 1 | `topology-tools/plugins/compilers/` |
| Implement zone_vlans resolution | ☐ | — | (in compiler) |
| Implement matrix calculation (R1-R6) | ☐ | — | (in compiler) |
| Implement R1a/R1b enforcement_plane | ☐ | — | (in compiler) |
| Implement policy_overrides merge | ☐ | — | (in compiler) |
| Register in `plugins.yaml` (order: 55) | ☐ | compiler | `topology-tools/plugins/` |
| Add unit tests | ☐ | compiler | `tests/plugins/compilers/` |

**Published Data:**
```python
ctx.publish("security_matrices", {...})
ctx.publish("zone_vlans", {...})
ctx.publish("matrix_by_enforcer", {...})
```

**Acceptance Test:**
```bash
task build && python -c "import json; print(json.load(open('generated/home-lab/compiled.json'))['security_matrices'])"
```

### Phase 4: Validators
**Goal:** Catch errors early.
**Exit Criteria:** All E-codes block build, W-codes warn.

| Validator | Codes | Priority |
|-----------|-------|----------|
| `vlan_zone_validator` | E7850, E7851, E7852 | High |
| `security_matrix_validator` | E7853, E7854 | High |
| `ip_derivation_validator` | E7861, E7862, E7863, W7864 | High |
| `policy_completeness_validator` | W7855, W7856, W7860 | Medium |
| `firewall_audit_validator` | W7857, W7858 | Medium |

**Acceptance Test:**
```bash
# Introduce intentional error, verify it's caught
task validate 2>&1 | grep E7850  # Must appear for duplicate VLAN ID
```

### Phase 5: Generator Enhancement
**Goal:** Generate Terraform firewall rules from matrix.
**Exit Criteria:** `terraform plan` shows expected rules.

| Task | Status | Depends |
|------|--------|---------|
| Extend `projections.py` to consume matrix | ☐ | Phase 3 |
| Create `zone_firewall.tf.j2` template | ☐ | projection |
| Generate address lists per zone | ☐ | template |
| Generate established/related rule | ☐ | template |
| Generate policy_override ACCEPT rules | ☐ | template |
| Generate matrix DENY rules with `place_before` | ☐ | template |
| Generate matrix ALLOW rules | ☐ | template |
| Generate **final drop-all** rule | ☐ | template |
| Update artifact contract | ☐ | all above |

**Rule Ordering (CRITICAL):**
```
1. established/related
2. policy_override ACCEPTs
3. matrix DENY (isolated)
4. matrix DENY (uphill)
5. matrix ALLOW (downhill)
6. FINAL DROP-ALL
```

**Acceptance Test:**
```bash
task build
cd generated/home-lab/terraform/mikrotik
terraform init && terraform plan  # Review rule count and order
```

### Phase 6: Staging Deployment
**Goal:** Deploy to MikroTik with safety.
**Exit Criteria:** All zones have connectivity, logs confirm deny rules work.

| Step | Command | Rollback |
|------|---------|----------|
| 1. Backup | `ssh admin@192.168.88.1 '/system backup save name=pre-adr0110'` | — |
| 2. Export | `ssh admin@192.168.88.1 '/export file=pre-adr0110'` | — |
| 3. Plan | `terraform plan -out=adr0110.plan` | — |
| 4. Review | Manual inspection of plan output | Don't apply |
| 5. Apply | `terraform apply adr0110.plan` | See step 7 |
| 6. Test | Ping/curl from each zone | — |
| 7. Rollback (if needed) | `/system backup load name=pre-adr0110` | — |

**Connectivity Test Matrix:**
```
guest → internet    ✓ (R2 allows untrusted)
guest → user        ✗ (R2 denies)
user → servers:443  ✓ (policy_override)
user → servers:22   ✗ (no override)
user → management   ✗ (R4 uphill)
management → all    ✓ (R3 downhill)
```

### Phase 7: Cleanup & Documentation
**Goal:** Remove legacy code, update docs.
**Exit Criteria:** ADR status = Implemented.

| Task | Status |
|------|--------|
| Remove `vlans` section from rtr-mikrotik-chateau.yaml | ☐ |
| Remove `zone_policies` section from rtr-mikrotik-chateau.yaml | ☐ |
| Update model.lock | ☐ |
| Generate security-matrix.md | ☐ |
| Update ADR-0110 status to Implemented | ☐ |
| Create PR, merge to main | ☐ |

### Future Phases (Backlog)

| Phase | Scope | Priority |
|-------|-------|----------|
| F1 | `terraform_proxmox_generator` for srv-gamayun | High |
| F2 | `terraform_openwrt_generator` for rtr-slate | Medium |
| F3 | CI integration (`lane.py validate-security-matrix`) | High |
| F4 | Network diagram generator (Mermaid) | Low |
| F5 | Policy simulation (`--dry-run --what-if`) | Medium |
| F6 | Abstract adapter interface | Low |

---

## Risk Mitigation Summary

| Risk | Mitigation | Owner |
|------|------------|-------|
| Lock-out from MikroTik | Physical access, MAC-Telnet, backup restore | Operator |
| Terraform state drift | Weekly `terraform plan` in CI | CI |
| Rule ordering bugs | E2E test with connectivity matrix | QA |
| Compiler regression | Unit tests, golden file comparison | Dev |
| CIDR overlap | E7851 validator | Compiler |

## References

### Internal
- Schema: `topology/class-modules/L2-network/network/class.network.trust_zone.yaml`
- Schema: `topology/class-modules/L2-network/network/class.network.vlan.yaml`
- Existing validator: `topology-tools/plugins/validators/network_vlan_zone_consistency_validator.py`
- Related: ADR-0109 (Network Segmentation with Zone-Based Architecture)
- Related: ADR-0063 (Plugin Microkernel for Compiler, Validators, and Generators)
- Related: ADR-0074 (V5 Generator Architecture)

### External Best Practices (SPC Analysis 2026-06-22)
- [Cisco Zone-Based Policy Firewall Design Guide](https://www.cisco.com/c/en/us/support/docs/security/ios-firewall/98628-zone-design-guide.html)
- [Huawei Firewall Security Policy Best Practices](https://support.huawei.com/enterprise/en/doc/EDOC1100170992)
- [Tufin: Zone-Based Firewall Explained](https://www.tufin.com/blog/zone-based-firewall)
- [UpGuard: Network Segmentation Best Practices 2026](https://www.upguard.com/blog/network-segmentation-best-practices)
- [Palo Alto Networks: What Is Network Segmentation](https://www.paloaltonetworks.com/cyberpedia/what-is-network-segmentation)

### MikroTik Terraform References
- [Schwitzd/IaC-HomeRouter](https://github.com/Schwitzd/IaC-HomeRouter) — Address lists + firewall rules pattern
- [mirceanton/mikrotik-terraform](https://github.com/mirceanton/mikrotik-terraform) — Terragrunt structure
- [MikroTik Terraform Getting Started](https://mirceanton.com/posts/mikrotik-terraform-getting-started/) — Backup requirement

---

## Appendix: SPC Analysis Summary

**Date:** 2026-06-22
**Method:** 7-Step Strict Process Compliance

### SWOT Summary (Revised)

**Strengths (10):**

| ID | Strength |
|----|----------|
| S1 | Class→Object→Instance pattern — consistent with topology |
| S2 | Automatic policy derivation (R1-R6) — no manual firewall writing |
| S3 | M1-B multi-enforcer — perimeter (MikroTik) + internal (Proxmox) |
| S4 | Trust Zone vs VLAN separation — many VLANs per zone |
| S5 | IP derivation (vlan_ref + host) — see ADR-0111 |
| S6 | Multi-platform adapters — RouterOS, OpenWrt, Proxmox |
| S7 | Cisco-aligned implicit deny — final drop-all rule |
| S8 | Intra-zone micro-segmentation — R1a/R1b enforcement_plane |
| S9 | 15 validation rules — early error detection |
| S10 | Terraform-first — IaC, state tracking, plan before apply |

**Weaknesses (8):**

| ID | Weakness | Mitigation |
|----|----------|------------|
| W1 | Complexity (12 findings) | Phased implementation |
| W2 | No rollback automation | Add rollback playbook |
| W3 | Two compilers needed | Could combine |
| W4 | No CI integration | Add to lane.py |
| W5 | Migration burden (9 files) | See ADR-0111 |
| W6 | No unit tests yet | Add pytest fixtures |
| W7 | Documentation spread | Single entry point |
| W8 | No dry-run mode | Add --dry-run flag |

**Opportunities (8):**

| ID | Opportunity | Value |
|----|-------------|-------|
| O1 | GitOps workflow — PR review for security | High |
| O2 | Compliance reports — auto-generate | Medium |
| O3 | Network diagrams — Mermaid/PlantUML | Medium |
| O4 | Ansible fallback | Medium |
| O5 | Multi-site support | Built-in |
| O6 | Audit trail — git history | Low |
| O7 | Policy simulation | High |
| O8 | Monitoring integration | Medium |

**Threats (8):**

| ID | Threat | Probability | Mitigation |
|----|--------|-------------|------------|
| T1 | Terraform state drift | Medium | Weekly CI plan |
| T2 | No commit-confirmed | High | Backup before apply |
| T3 | Rule ordering bugs | Medium | E2E tests |
| T4 | CIDR overlap | Low | E7851 validator |
| T5 | Wrong zone assignment | Medium | E7852 + W7860 |
| T6 | Compiler regression | Medium | Unit tests |
| T7 | Generator breaks existing | Medium | Artifact contract |
| T8 | Lock-out scenario | Low | Physical access |

### Critical Findings Addressed

| Finding | Status |
|---------|--------|
| F1: R2 vs R3 priority | ✅ Added Rule Evaluation Order section |
| F2: Missing final drop rule | ✅ Added Section 4.4 |
| F3: No backup strategy | ✅ Added Phase 5-6 backup requirement |
| F4: Terraform ordering | ✅ Added Section 4.3 with place_before |
| F5: Terminology | ✅ Unified to policy_overrides |
| F6: Class→Object→Instance pattern | ✅ Restructured Section 1 (revision 2) |
| F7: Multi-platform support | ✅ Added Section 1.4 (adapter architecture) |
| F8: Two matrices per project | ✅ Added Section 1.3 M1-B (perimeter + internal) |
| F9: Trust Zone vs VLAN separation | ✅ Added Section 1.5 (many VLANs → one zone) |
| F10: Intra-zone micro-segmentation | ✅ Added Section 2.4 R1a/R1b (enforcement_plane) |
| F11: IP address derivation | ✅ Moved to ADR-0111 (vlan_ref + host pattern) |
| F12: Host uniqueness validation | ✅ Moved to ADR-0111 (E7861-E7865 validation rules) |
