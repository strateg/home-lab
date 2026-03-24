# ADR 0079 Implementation Plan

**ADR:** `adr/0079-v5-documentation-and-diagram-generation-migration.md`
**Date:** 2026-03-24
**Status:** Planning

---

## Overview

Migrate v4 documentation generator (19 templates) to v5 plugin architecture.

### Current State

| Metric | V4 | V5 | Gap |
|--------|----|----|-----|
| Templates | 19 | 3 | 16 |
| Projections | 8+ | 1 | 7+ |
| Icon support | Full | None | Full |
| Mermaid validation | Yes | No | Yes |

---

## Phase A: Core Network Documentation

### A.1 Network Projection Module

**File:** `v5/topology-tools/plugins/projections/network_projection.py`

**Tasks:**
1. Extract networks from compiled model (group: networks)
2. Build IP allocation table from `ip_allocations` in network instances
3. Resolve device-to-network bindings via `network_binding_ref`
4. Sort all collections deterministically

**Data structure:**
```python
{
    "networks": [
        {
            "id": "inst.vlan.servers",
            "name": "Servers VLAN",
            "cidr": "10.0.30.0/24",
            "vlan_tag": 30,
            "trust_zone_ref": "inst.trust_zone.servers",
            "gateway": "10.0.30.1",
            "ip_allocations": [...]
        }
    ],
    "allocations": [
        {
            "network_id": "inst.vlan.servers",
            "ip": "10.0.30.5",
            "device_ref": "srv-orangepi5",
            "purpose": "docker host"
        }
    ],
    "device_bindings": [
        {
            "device_ref": "lxc-docker",
            "network_ref": "inst.vlan.servers",
            "ip": "10.0.30.90/24"
        }
    ]
}
```

### A.2 Network Diagram Template

**File:** `v5/topology-tools/templates/docs/network-diagram.md.j2`

**Port from:** `v4/topology-tools/templates/docs/network-diagram.md.j2`

**Adaptations:**
- Change data source from `topology.L2_network.networks` to `projection.networks`
- Use v5 instance refs instead of v4 IDs

### A.3 IP Allocation Template

**File:** `v5/topology-tools/templates/docs/ip-allocation.md.j2`

**Port from:** `v4/topology-tools/templates/docs/ip-allocation.md.j2`

**Adaptations:**
- Change data source to `projection.allocations`
- Sort by network, then IP address

### A.4 Generator Integration

**Update:** `v5/topology-tools/plugins/generators/docs_generator.py`

**Tasks:**
1. Import `build_network_projection`
2. Add templates to generation list:
   - `("docs/network-diagram.md.j2", "network-diagram.md")`
   - `("docs/ip-allocation.md.j2", "ip-allocation.md")`
3. Pass network projection to template context

### A.5 Tests

**File:** `v5/tests/plugin_integration/test_docs_network_projection.py`

**Test cases:**
1. Network projection builds correctly from compiled model
2. IP allocations sorted deterministically
3. Device bindings resolved correctly
4. Empty networks handled gracefully

---

## Phase B: Physical Topology

### B.1 Physical Projection Module

**File:** `v5/topology-tools/plugins/projections/physical_projection.py`

**Data sources:**
- Devices (group: devices)
- Data links (from device instances)
- Power links (from device instances)
- Interfaces (from device instances)

### B.2 Templates

| Template | Source | Output |
|----------|--------|--------|
| physical-topology.md.j2 | v4 | physical-topology.md |
| data-links-topology.md.j2 | v4 | data-links-topology.md |
| power-links-topology.md.j2 | v4 | power-links-topology.md |

### B.3 Link Resolution

V5 uses instance refs for links:
```yaml
# Device instance
data_links:
  - port: eth0
    peer_device_ref: rtr-mikrotik-chateau
    peer_port: ether2
    media: cat6
```

Projection must resolve refs to device names for diagram labels.

---

## Phase C: Security Topology

### C.1 Security Projection Module

**File:** `v5/topology-tools/plugins/projections/security_projection.py`

**Data sources:**
- Trust zones (group: trust_zones)
- Networks with trust_zone_ref
- Firewall policies (if modeled)

### C.2 Templates

| Template | Source | Output |
|----------|--------|--------|
| vlan-topology.md.j2 | v4 | vlan-topology.md |
| trust-zones.md.j2 | v4 | trust-zones.md |

### C.3 Firewall Matrix

Build zone-to-zone allowed flows matrix from:
- Trust zone definitions
- Network firewall_policy_refs
- Service allowed_from rules

---

## Phase D: Application Layer

### D.1 Extended Service Projection

**Update:** `v5/topology-tools/plugins/projections/docs_projection.py`

**Add:**
- Service dependency graph (from `dependencies[].service_ref`)
- Service-to-runtime bindings

### D.2 Storage Projection

**File:** `v5/topology-tools/plugins/projections/storage_projection.py`

**Data sources:**
- Storage pools (group: storage_pools)
- Data assets (group: data_assets)
- Storage bindings in LXC/VM instances

### D.3 Templates

| Template | Source | Output |
|----------|--------|--------|
| service-dependencies.md.j2 | v4 | service-dependencies.md |
| storage-topology.md.j2 | v4 | storage-topology.md |

---

## Phase E: Operations Layer

### E.1 Operations Projection Module

**File:** `v5/topology-tools/plugins/projections/operations_projection.py`

**Data sources:**
- Healthchecks (group: healthchecks)
- Alerts (group: alerts)
- Dashboards (group: dashboards)
- VPN tunnels (from network instances)
- Certificates (group: certificates)
- QoS policies (from network instances)
- UPS devices (group: devices, type: ups)

### E.2 Templates

| Template | Source | Output |
|----------|--------|--------|
| monitoring-topology.md.j2 | v4 | monitoring-topology.md |
| vpn-topology.md.j2 | v4 | vpn-topology.md |
| certificates-topology.md.j2 | v4 | certificates-topology.md |
| qos-topology.md.j2 | v4 | qos-topology.md |
| ups-topology.md.j2 | v4 | ups-topology.md |

---

## Phase F: Meta and Tooling

### F.1 Icon Manager

**File:** `v5/topology-tools/icons/icon_manager.py`

**Port from:** `v4/topology-tools/scripts/generators/docs/icons.py`

**Features:**
- Icon pack discovery (si, mdi)
- Device type to icon mapping
- Zone to icon mapping
- Service type to icon mapping
- Icon HTML generation for compat mode

### F.2 Icon Mappings

**File:** `v5/topology-tools/icons/mappings.yaml`

```yaml
device_types:
  hypervisor: si:proxmox
  router: mdi:router-network
  sbc: mdi:chip
  # ...

trust_zones:
  management: mdi:shield-crown
  servers: mdi:server
  # ...

service_types:
  database: mdi:database
  web-application: mdi:web
  # ...
```

### F.3 Templates

| Template | Source | Output |
|----------|--------|--------|
| icon-legend.md.j2 | v4 | icon-legend.md |
| diagrams-index.md.j2 | v4 | diagrams-index.md |

### F.4 Mermaid Validation

**File:** `v5/topology-tools/validate-mermaid-render.py`

**Port from:** `v4/topology-tools/validate-mermaid-render.py`

**Features:**
- Extract Mermaid blocks from generated docs
- Validate via Mermaid CLI (mmdc)
- Support icon-node and compat modes
- Exit non-zero on validation failure

---

## Generator Configuration

### plugins.yaml Entry

```yaml
- id: base.generator.docs
  kind: generator
  entry: plugins.generators.docs_generator
  config:
    enabled: true
    mermaid_icons: true
    mermaid_icon_nodes: true
    template_sets:
      - core        # overview, devices, services
      - network     # network-diagram, ip-allocation
      - physical    # physical-topology, data-links, power-links
      - security    # vlan-topology, trust-zones
      - application # service-dependencies, storage-topology
      - operations  # monitoring, vpn, certs, qos, ups
      - meta        # icon-legend, diagrams-index
```

### Selective Generation

```bash
# Generate only core docs
python compile-topology.py --generator-config docs.template_sets=core

# Generate all docs
python compile-topology.py --generator-config docs.template_sets=all
```

---

## Testing Strategy

### Unit Tests

| Test File | Scope |
|-----------|-------|
| test_network_projection.py | Network projection logic |
| test_physical_projection.py | Physical topology projection |
| test_security_projection.py | Security projection |
| test_storage_projection.py | Storage projection |
| test_operations_projection.py | Operations projection |
| test_icon_manager.py | Icon mapping and rendering |

### Integration Tests

| Test File | Scope |
|-----------|-------|
| test_docs_generator_full.py | Full docs generation |
| test_mermaid_render.py | Mermaid validation |

### Golden Tests

Compare generated docs against baseline snapshots for:
- Deterministic output
- Template correctness
- Data accuracy

---

## Migration Checklist

### Phase A
- [ ] Create network_projection.py
- [ ] Port network-diagram.md.j2
- [ ] Port ip-allocation.md.j2
- [ ] Update docs_generator.py
- [ ] Add tests
- [ ] Validate output matches v4

### Phase B
- [ ] Create physical_projection.py
- [ ] Port physical-topology.md.j2
- [ ] Port data-links-topology.md.j2
- [ ] Port power-links-topology.md.j2
- [ ] Add tests

### Phase C
- [ ] Create security_projection.py
- [ ] Port vlan-topology.md.j2
- [ ] Port trust-zones.md.j2
- [ ] Add tests

### Phase D
- [ ] Extend docs_projection.py for dependencies
- [ ] Create storage_projection.py
- [ ] Port service-dependencies.md.j2
- [ ] Port storage-topology.md.j2
- [ ] Add tests

### Phase E
- [ ] Create operations_projection.py
- [ ] Port monitoring-topology.md.j2
- [ ] Port vpn-topology.md.j2
- [ ] Port certificates-topology.md.j2
- [ ] Port qos-topology.md.j2
- [ ] Port ups-topology.md.j2
- [ ] Add tests

### Phase F
- [ ] Create icon_manager.py
- [ ] Create mappings.yaml
- [ ] Port icon-legend.md.j2
- [ ] Port diagrams-index.md.j2
- [ ] Port validate-mermaid-render.py
- [ ] Add mermaid validation to CI
- [ ] Add tests

---

## Effort Estimates

| Phase | Templates | Projections | Effort |
|-------|-----------|-------------|--------|
| A | 2 | 1 | 2-3 days |
| B | 3 | 1 | 2-3 days |
| C | 2 | 1 | 2 days |
| D | 2 | 1 | 2 days |
| E | 5 | 1 | 3-4 days |
| F | 2 + tooling | - | 2-3 days |
| **Total** | **16** | **5** | **13-18 days** |

---

## Dependencies

### External
- Mermaid CLI (`@mermaid-js/mermaid-cli`) for validation
- Node.js for Mermaid CLI

### Internal
- ADR 0074 generator plugin interface
- Compiled model with all instance groups populated
- Instance refs resolution in projections
