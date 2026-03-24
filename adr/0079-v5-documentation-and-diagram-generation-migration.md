# ADR 0079: V5 Documentation and Diagram Generation Migration

**Date:** 2026-03-24
**Status:** Proposed
**Depends on:** ADR 0027 (Mermaid Rendering Strategy), ADR 0074 (V5 Generator Architecture)
**Migrates:** ADR 0005, ADR 0027 implementations from v4

---

## Context

V4 documentation generator implements a comprehensive set of topology visualizations per ADR 0005-0010 (consolidated in ADR 0027):

- 19 documentation templates covering network, physical, security, application, and operations layers
- Mermaid icon-node rendering with si/mdi icon packs
- Deterministic diagram generation with sorted collections
- Mermaid render validation quality gate

V5 currently has a minimal docs generator plugin (`docs_generator.py`) with only 3 templates:
- overview.md
- devices.md
- services.md

This represents 16% coverage of v4 documentation capabilities.

### Gap Summary

| Category | V4 Templates | V5 Templates | Gap |
|----------|--------------|--------------|-----|
| Core docs | 5 | 3 | 2 missing |
| Phase 1 diagrams | 7 | 0 | 7 missing |
| Phase 2 diagrams | 3 | 0 | 3 missing |
| Phase 3 diagrams | 3 | 0 | 3 missing |
| Navigation | 1 | 0 | 1 missing |
| **Total** | **19** | **3** | **16 missing** |

### Missing Tooling

| Component | V4 | V5 |
|-----------|----|----|
| validate-mermaid-render.py | Yes | No |
| Icon Manager (si, mdi) | Yes | No |
| Mermaid icon-node rendering | Yes | No |
| Extended data projections | Yes | Minimal |

## Decision

Migrate v4 documentation generation capabilities to v5 in a phased approach, adapting to v5's plugin architecture and class/object/instance model.

### Migration Principles

1. **Plugin-first architecture**: All generators are v5 plugins per ADR 0063/0074.
2. **Projection-based data flow**: Templates consume projections built from compiled model, not raw topology.
3. **Deterministic output**: Maintain ADR 0005 determinism guarantees (sorted collections, stable ordering).
4. **Mermaid compatibility**: Preserve ADR 0027 icon-node rendering with fallback modes.
5. **Incremental rollout**: Templates can be enabled progressively without breaking existing generation.

### Target Architecture

```
v5/topology-tools/
├── plugins/generators/
│   └── docs_generator.py          # Extended with phased template sets
├── plugins/projections/
│   ├── docs_projection.py         # Core projection (existing)
│   ├── network_projection.py      # Network diagrams data
│   ├── physical_projection.py     # Physical topology data
│   ├── security_projection.py     # Trust zones, firewall data
│   ├── storage_projection.py      # Storage pools, data assets
│   └── operations_projection.py   # Monitoring, VPN, certs, QoS, UPS
├── icons/
│   ├── icon_manager.py            # Icon pack discovery and mapping
│   └── packs/                     # Icon pack definitions
├── templates/docs/
│   ├── overview.md.j2             # (existing)
│   ├── devices.md.j2              # (existing)
│   ├── services.md.j2             # (existing)
│   ├── network-diagram.md.j2      # Phase A
│   ├── ip-allocation.md.j2        # Phase A
│   ├── physical-topology.md.j2    # Phase B
│   ├── data-links-topology.md.j2  # Phase B
│   ├── power-links-topology.md.j2 # Phase B
│   ├── vlan-topology.md.j2        # Phase C
│   ├── trust-zones.md.j2          # Phase C
│   ├── service-dependencies.md.j2 # Phase D
│   ├── storage-topology.md.j2     # Phase D
│   ├── monitoring-topology.md.j2  # Phase E
│   ├── vpn-topology.md.j2         # Phase E
│   ├── certificates-topology.md.j2# Phase E
│   ├── qos-topology.md.j2         # Phase E
│   ├── ups-topology.md.j2         # Phase E
│   ├── icon-legend.md.j2          # Phase F
│   └── diagrams-index.md.j2       # Phase F
└── validate-mermaid-render.py     # Phase F
```

### Migration Phases

#### Phase A: Core Network Documentation

**Scope:**
- network-diagram.md.j2
- ip-allocation.md.j2
- network_projection.py

**Data requirements:**
- Networks with CIDR, VLAN tags, trust zones
- IP allocations per network
- Device-to-network bindings
- Bridge and interface mappings

**Acceptance criteria:**
- Network diagram renders with Mermaid flowchart
- IP allocation table shows all assigned addresses
- Deterministic output (sorted by network, then IP)

#### Phase B: Physical Topology

**Scope:**
- physical-topology.md.j2
- data-links-topology.md.j2
- power-links-topology.md.j2
- physical_projection.py

**Data requirements:**
- L1 devices with types, locations, interfaces
- Data links (physical connections)
- Power links (power feed paths)
- Device coordinates for layout hints

**Acceptance criteria:**
- Physical topology shows all L1 devices
- Data links diagram shows physical connectivity
- Power links diagram shows power distribution

#### Phase C: Security Topology

**Scope:**
- vlan-topology.md.j2
- trust-zones.md.j2
- security_projection.py

**Data requirements:**
- VLANs with tags, networks, trunk ports
- Trust zones with member networks
- Firewall policies per zone pair
- Security policy references

**Acceptance criteria:**
- VLAN diagram shows segmentation
- Trust zones show security boundaries
- Firewall matrix shows allowed flows

#### Phase D: Application Layer

**Scope:**
- service-dependencies.md.j2
- storage-topology.md.j2
- Extend existing projections

**Data requirements:**
- Service dependency graph (service_ref chains)
- Storage pools with capacity, media type
- Data assets with locations, backup status

**Acceptance criteria:**
- Service dependency graph renders correctly
- Storage topology shows pool hierarchy
- Data assets linked to storage locations

#### Phase E: Operations Layer

**Scope:**
- monitoring-topology.md.j2
- vpn-topology.md.j2
- certificates-topology.md.j2
- qos-topology.md.j2
- ups-topology.md.j2
- operations_projection.py

**Data requirements:**
- Healthchecks, alerts, dashboards
- VPN tunnels and remote access
- Certificates with validity, issuers
- QoS policies and queues
- UPS devices and protected loads

**Acceptance criteria:**
- Each diagram renders without errors
- Data accurately reflects compiled model

#### Phase F: Meta and Tooling

**Scope:**
- icon-legend.md.j2
- diagrams-index.md.j2
- icon_manager.py
- validate-mermaid-render.py

**Data requirements:**
- Icon mappings by device type, zone, service type
- Generated files manifest for index

**Acceptance criteria:**
- Icon legend documents all used icons
- Diagrams index links to all generated docs
- Mermaid validation passes for all diagrams

### Icon Mode Configuration

```yaml
# plugins.yaml
- id: base.generator.docs
  config:
    mermaid_icons: true
    mermaid_icon_nodes: true  # false = compat mode
    icon_packs:
      - si   # Simple Icons
      - mdi  # Material Design Icons
```

### Projection Contract

Each projection module exports a `build_*_projection(compiled_json: dict) -> dict` function:

```python
def build_network_projection(compiled_json: dict) -> dict:
    """Build network diagram projection from compiled model."""
    return {
        "networks": [...],      # Sorted by id
        "allocations": [...],   # Sorted by network, then IP
        "devices": [...],       # Devices with network bindings
        "bridges": [...],       # Bridge definitions
    }
```

### Compatibility Notes

1. **V4 templates** can be ported with minimal changes; main adaptation is data source (projection vs raw topology).
2. **Icon mappings** from v4 `DiagramDocumentationGenerator` are preserved.
3. **Mermaid syntax** remains compatible (flowchart, icon-nodes).
4. **Output paths** follow v5 convention: `v5-generated/<project>/docs/`.

## Consequences

### Benefits

1. Full documentation parity with v4.
2. Plugin-based architecture enables selective generation.
3. Projection layer decouples templates from model structure.
4. Mermaid quality gate catches rendering regressions.

### Trade-offs

1. Significant implementation effort (6 phases).
2. Projection modules add maintenance surface.
3. Icon pack dependencies for full rendering.

### Risks

1. **Model mapping complexity**: V5 class/object/instance model differs from v4 flat topology. Projections must handle this translation.
2. **Icon pack availability**: Mermaid icon-node support depends on renderer configuration.
3. **Template drift**: Parallel v4/v5 templates during migration may diverge.

## Migration Milestones

| Milestone | Deliverable | Definition of Done |
|-----------|-------------|-------------------|
| M1 | Phase A complete | network-diagram + ip-allocation render correctly |
| M2 | Phase B complete | Physical topology diagrams render correctly |
| M3 | Phase C complete | Security diagrams render correctly |
| M4 | Phase D complete | Application layer diagrams render correctly |
| M5 | Phase E complete | Operations layer diagrams render correctly |
| M6 | Phase F complete | Icon legend, index, Mermaid validation operational |
| M7 | V4 deprecation | V4 docs generator marked deprecated |

## References

- ADR 0005: Diagram Generation Determinism
- ADR 0027: Mermaid Rendering Strategy Consolidation
- ADR 0063: Plugin Microkernel Architecture
- ADR 0074: V5 Generator Architecture
- V4 implementation: `v4/topology-tools/scripts/generators/docs/`
- V5 docs generator: `v5/topology-tools/plugins/generators/docs_generator.py`
