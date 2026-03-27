# ADR 0079: V5 Documentation and Diagram Generation Migration

**Date:** 2026-03-24
**Status:** Accepted
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

### V4 Implementation Analysis

V4 docs generator consists of:

| Component | Lines | Responsibility |
|-----------|-------|----------------|
| `generator.py` | ~500 | Main orchestrator, CLI integration, template rendering |
| `diagrams/__init__.py` | ~1087 | All diagram generation methods, icon mappings |
| `data/__init__.py` | ~700 | Data resolution from L0-L7 topology layers |
| `templates/__init__.py` | ~200 | Jinja2 environment wrapper |
| `icons/__init__.py` | ~250 | Icon pack discovery, SVG extraction, HTML generation |

Key architectural characteristics:
1. **Direct layer access**: Reads from `topology["L1_foundation"]`, `topology["L2_network"]`, etc.
2. **Monolithic diagram class**: `DiagramDocumentationGenerator` contains all icon mappings and diagram methods
3. **Complex data resolution**: `DataResolver` handles storage chains, service runtime enrichment, network profile merging
4. **Icon pack system**: Discovers `@iconify-json` packages, caches SVG data URIs

### V4 Architectural Issues

The v4 implementation has several architectural limitations that must be addressed in the v5 migration:

1. **Tight coupling to layer structure**: `DataResolver` assumes fixed layer paths (`L1_foundation`, `L2_network`, etc.). Any topology schema evolution requires code changes in multiple locations.

2. **Scattered data resolution**: Storage chain resolution (`resolve_storage_pools_for_docs`, `resolve_data_assets_for_docs`) duplicates logic that the v5 compiler already performs during instance compilation.

3. **Mixed concerns in DiagramDocumentationGenerator**:
   - Icon mappings (should be constants module)
   - Data extraction (should be projection layer)
   - Template rendering (should be generator layer)
   - File I/O (should be base generator)

4. **Imperative service enrichment**: `apply_service_runtime_compat_fields()` mutates topology in-place to inject backward-compatible fields. This pattern is fragile and violates v5's immutable projection model.

5. **Non-typed data structures**: All data flows through untyped `Dict[str, Any]`, making it impossible to enforce contracts or enable IDE assistance.

### V5 Model Mapping Considerations

The v5 class/object/instance model differs fundamentally from v4's flat layer structure:

| V4 Pattern | V5 Pattern | Projection Strategy |
|------------|------------|---------------------|
| `topology["L1_foundation"]["devices"]` | `compiled_json["instances"]["devices"]` | Use `_instance_groups()` from projection_core |
| `topology["L2_network"]["networks"]` | `compiled_json["instances"]["network"]` | Group name is `network` (singular) |
| `topology["L4_platform"]["lxc"]` | `compiled_json["instances"]["lxc"]` | Direct mapping |
| `topology["L5_application"]["services"]` | `compiled_json["instances"]["services"]` | Direct mapping |
| Layer reference (`device_ref`) | Instance reference with `object_ref` | Resolve via instance_id lookup |
| Profile merging (`profile_ref`) | Pre-resolved in instance_data | Compiler handles merging |

Key differences requiring projection adaptation:

1. **Instance data location**: V4 reads directly from topology keys; v5 reads from `row.get("instance_data", {})` or top-level row keys.

2. **Reference resolution**: V4 resolves references at render time; v5 should rely on compiler-resolved references where possible.

3. **Canonical group names**: V5 uses `GROUP_DEVICES`, `GROUP_LXC`, etc. constants from `projection_core.py` for consistent group access.

4. **Status filtering**: V5 instances have explicit `status` field that should be used to filter inactive/draft instances from documentation.

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

---

## Architectural Alternatives

### Alternative A: Direct V4 Port (Rejected)

Port v4 code directly to v5 with minimal changes.

**Approach:**
- Copy `DocumentationGenerator`, `DiagramDocumentationGenerator`, `DataResolver` classes
- Adapt to read from `ctx.compiled_json` instead of loaded topology
- Maintain monolithic structure

**Pros:**
- Fastest initial implementation
- Known working code
- Minimal risk of new bugs

**Cons:**
- Violates ADR 0074 projection-first contract
- Does not leverage v5 class/object/instance model
- Creates tight coupling between generator and compiled model schema
- Monolithic class not aligned with plugin architecture
- Data resolution logic duplicates what compiler already handles
- Violates ADR 0063 four-level plugin boundary contract

**Verdict:** Rejected. Creates technical debt and violates established v5 contracts.

### Alternative B: Projection-First Rewrite (Selected)

Build new projections that extract documentation-relevant data from compiled model, then port templates to consume projections.

**Approach:**
- Create domain-specific projection builders per ADR 0074 D1
- Port templates with minimal changes (projection access instead of layer access)
- Extract icon system to reusable module
- Keep diagram generation logic as helper functions, not monolithic class

**Pros:**
- Aligned with ADR 0074 projection-first mandate
- Templates decoupled from compiled model schema drift
- Enables projection snapshot testing
- Follows plugin architecture principles
- Icon system becomes reusable across generators

**Cons:**
- More initial implementation effort
- Need to design projection contracts carefully
- V4 data resolution logic must be reimplemented in projection layer

**Verdict:** Selected. Aligns with v5 architecture and provides better maintainability.

### Alternative C: Hybrid Adapter Pattern (Considered)

Create adapter layer that transforms compiled model to v4-compatible structure.

**Approach:**
- Build adapter: `compiled_json -> v4_topology_format`
- Reuse v4 `DataResolver` with adapter output
- Gradually migrate to projections

**Pros:**
- Faster initial implementation than full rewrite
- Can reuse v4 resolution logic

**Cons:**
- Creates intermediate abstraction layer
- Adapter becomes maintenance burden
- Does not solve projection-first requirement
- Still violates ADR 0074 spirit

**Verdict:** Not selected. Adds complexity without solving architectural alignment.

---

## Decision

Adopt **Alternative B: Projection-First Rewrite** with the following architecture:

### Plugin Architecture

The docs generator follows ADR 0063/0074 contracts with a single generator plugin that orchestrates multiple projection modules and template sets.

```
Generator Plugin Layer
├── base.generator.docs (order: 240)
│   ├── consumes: compiled_json via ctx
│   ├── builds: domain projections
│   ├── renders: templates from projection data
│   └── publishes: docs_files, docs_projection

Projection Module Layer (ADR 0074 D1)
├── projection_core.py         # Shared utilities (existing)
├── projections.py             # build_docs_projection (existing, extended)
├── docs/
│   ├── network_projection.py  # Networks, IPs, bridges
│   ├── physical_projection.py # Devices, links, storage slots
│   ├── security_projection.py # Trust zones, firewall, VLANs
│   ├── storage_projection.py  # Pools, assets, mount chains
│   └── operations_projection.py # Monitoring, VPN, certs, QoS, UPS

Icon System Layer
├── icons/
│   ├── icon_manager.py        # Pack discovery, caching
│   ├── mappings.py            # Type-to-icon constants
│   └── mermaid_helpers.py     # Icon-node syntax helpers

Template Layer
├── templates/docs/
│   ├── core/                  # overview, devices, services
│   ├── network/               # network-diagram, ip-allocation
│   ├── physical/              # physical, data-links, power-links
│   ├── security/              # vlan, trust-zones
│   ├── application/           # service-deps, storage
│   ├── operations/            # monitoring, vpn, certs, qos, ups
│   └── navigation/            # icon-legend, diagrams-index
```

### Generator Plugin Specification

```yaml
# plugins.yaml entry
- id: base.generator.docs
  kind: generator
  entry: plugins.generators.docs_generator:DocsGenerator
  api_version: "1.x"
  stages: [generate]
  order: 240  # After infrastructure generators (210-230)
  depends_on: []
  config:
    template_sets:
      - core
      - network
      - physical
      - security
      - application
      - operations
      - navigation
    mermaid_icons: true
    mermaid_icon_nodes: true
    icon_packs:
      - si
      - mdi
  config_schema:
    type: object
    properties:
      template_sets:
        type: array
        items:
          type: string
          enum: [core, network, physical, security, application, operations, navigation, all]
        default: [all]
      mermaid_icons:
        type: boolean
        default: true
      mermaid_icon_nodes:
        type: boolean
        default: true
      icon_packs:
        type: array
        items:
          type: string
        default: [si, mdi]
```

### Projection Contracts

Each projection module follows ADR 0074 D1 contract:

```python
# Network projection contract
def build_network_projection(compiled_json: dict) -> NetworkProjection:
    """Build network diagram projection from compiled model.

    Returns:
        NetworkProjection with:
        - networks: List[NetworkRow] sorted by instance_id
        - allocations: List[AllocationRow] sorted by (network_id, ip)
        - bridges: List[BridgeRow] sorted by id
        - device_bindings: List[BindingRow] sorted by (device_ref, network_ref)
    """

# Physical projection contract
def build_physical_projection(compiled_json: dict) -> PhysicalProjection:
    """Build physical topology projection from compiled model.

    Returns:
        PhysicalProjection with:
        - devices: List[DeviceRow] sorted by instance_id
        - data_links: List[LinkRow] sorted by (endpoint_a, endpoint_b)
        - power_links: List[LinkRow] sorted by (endpoint_a, endpoint_b)
        - storage_slots: Dict[device_id, List[SlotRow]]
        - locations: List[LocationRow] sorted by id
    """

# Security projection contract
def build_security_projection(compiled_json: dict) -> SecurityProjection:
    """Build security topology projection from compiled model.

    Returns:
        SecurityProjection with:
        - trust_zones: List[ZoneRow] sorted by id
        - vlans: List[VlanRow] sorted by tag
        - firewall_policies: List[PolicyRow] sorted by (priority, id)
        - zone_network_bindings: Dict[zone_id, List[network_id]]
    """

# Storage projection contract
def build_storage_projection(compiled_json: dict) -> StorageProjection:
    """Build storage topology projection from compiled model.

    Returns:
        StorageProjection with:
        - storage_pools: List[PoolRow] sorted by id
        - data_assets: List[AssetRow] sorted by id
        - mount_chains: List[ChainRow] with resolved device->pool->asset links
    """

# Operations projection contract
def build_operations_projection(compiled_json: dict) -> OperationsProjection:
    """Build operations topology projection from compiled model.

    Returns:
        OperationsProjection with:
        - healthchecks: List[HealthcheckRow] sorted by id
        - alerts: List[AlertRow] sorted by id
        - dashboards: List[DashboardRow] sorted by id
        - vpn_tunnels: List[VpnRow] sorted by id
        - certificates: List[CertRow] sorted by id
        - qos_policies: List[QosRow] sorted by id
        - ups_policies: List[UpsRow] sorted by id
```

### Icon System Design

Icon management extracted to reusable module with clear contracts:

```python
# icons/icon_manager.py
class IconManager:
    """Stateless icon lookup with caching."""

    def __init__(self, packs: List[str], search_roots: List[Path]):
        self._cache: Dict[str, str] = {}
        self._packs = self._load_packs(packs, search_roots)

    def icon_for_device(self, device: dict) -> str:
        """Get icon ID for device based on type/class/model."""

    def icon_for_zone(self, zone_id: str) -> str:
        """Get icon ID for trust zone."""

    def icon_for_service(self, service: dict) -> str:
        """Get icon ID for service based on type."""

    def icon_html(self, icon_id: str, height: int = 16) -> str:
        """Generate HTML img tag with data URI or remote fallback."""

# icons/mappings.py - Constants extracted from v4 DiagramDocumentationGenerator
DEVICE_ICON_BY_TYPE: Dict[str, str] = {
    "hypervisor": "si:proxmox",
    "router": "mdi:router-network",
    # ... full mapping from v4
}

ZONE_ICON_MAP: Dict[str, str] = {
    "untrusted": "mdi:earth",
    "management": "mdi:shield-crown",
    # ... full mapping from v4
}
```

### Template Organization

Templates organized by category with shared partials:

```
templates/docs/
├── _partials/
│   ├── mermaid_header.j2      # Icon registration runtime hint
│   ├── icon_node.j2           # Icon-node macro
│   └── footer.j2              # Generation metadata
├── core/
│   ├── overview.md.j2
│   ├── devices.md.j2
│   └── services.md.j2
├── network/
│   ├── network-diagram.md.j2
│   └── ip-allocation.md.j2
├── physical/
│   ├── physical-topology.md.j2
│   ├── data-links-topology.md.j2
│   └── power-links-topology.md.j2
├── security/
│   ├── vlan-topology.md.j2
│   └── trust-zones.md.j2
├── application/
│   ├── service-dependencies.md.j2
│   └── storage-topology.md.j2
├── operations/
│   ├── monitoring-topology.md.j2
│   ├── vpn-topology.md.j2
│   ├── certificates-topology.md.j2
│   ├── qos-topology.md.j2
│   └── ups-topology.md.j2
└── navigation/
    ├── icon-legend.md.j2
    └── diagrams-index.md.j2
```

### Mermaid Validation Integration

Mermaid validation becomes a separate validator plugin per ADR 0063:

```yaml
- id: base.validator_generated.mermaid
  kind: validator_generated
  entry: plugins.validators.mermaid_validator:MermaidValidator
  api_version: "1.x"
  stages: [validate]
  order: 500  # Post-generation validation
  depends_on: [base.generator.docs]
  config:
    icon_mode: auto  # auto | icon-nodes | compat | none
    fail_on_error: true
```

### Diagnostic Code Ranges (ADR 0074 D8 Compliance)

The docs generator reserves code range `E97xx` per ADR 0074:

| Code | Severity | Description |
|------|----------|-------------|
| E3001 | error | compiled_json empty (shared precondition) |
| E9701 | error | Projection build failure |
| E9702 | error | Template rendering failure |
| E9703 | error | Icon pack discovery failure (non-fatal if fallback enabled) |
| I9701 | info | Generation summary (counts) |
| W9701 | warning | Missing optional projection data |

Mermaid validator uses `E98xx` range:

| Code | Severity | Description |
|------|----------|-------------|
| E9801 | error | Mermaid syntax validation failed |
| E9802 | error | Mermaid CLI execution failed |
| W9801 | warning | No docs files to validate |
| I9801 | info | Validation summary |

---

## Migration Principles

1. **Plugin-first architecture**: All generators are v5 plugins per ADR 0063/0074.
2. **Projection-based data flow**: Templates consume projections built from compiled model, not raw topology.
3. **Deterministic output**: Maintain ADR 0005 determinism guarantees (sorted collections, stable ordering).
4. **Mermaid compatibility**: Preserve ADR 0027 icon-node rendering with fallback modes.
5. **Incremental rollout**: Template sets can be enabled progressively without breaking existing generation.
6. **Reusable components**: Icon system and projection helpers are available to other generators.

---

## Migration Phases

### Phase A: Core Network Documentation

**Scope:**
- network-diagram.md.j2
- ip-allocation.md.j2
- network_projection.py

**Data requirements:**
- Networks with CIDR, VLAN tags, trust zones (from `instances.network`)
- IP allocations per network (from network instance data)
- Device-to-network bindings (from device/lxc/vm instance data)
- Bridge and interface mappings

**Acceptance criteria:**
- Network diagram renders with Mermaid flowchart
- IP allocation table shows all assigned addresses
- Deterministic output (sorted by network, then IP)

### Phase B: Physical Topology

**Scope:**
- physical-topology.md.j2
- data-links-topology.md.j2
- power-links-topology.md.j2
- physical_projection.py

**Data requirements:**
- Devices with types, locations, interfaces (from `instances.devices`)
- Data links (from device instance `data_links`)
- Power links (from device instance `power_links`)
- Storage slot views

**Acceptance criteria:**
- Physical topology shows all devices
- Data links diagram shows physical connectivity
- Power links diagram shows power distribution

### Phase C: Security Topology

**Scope:**
- vlan-topology.md.j2
- trust-zones.md.j2
- security_projection.py

**Data requirements:**
- VLANs with tags, networks
- Trust zones with member networks
- Firewall policies per zone pair
- Security policy references

**Acceptance criteria:**
- VLAN diagram shows segmentation
- Trust zones show security boundaries
- Firewall matrix shows allowed flows

### Phase D: Application Layer

**Scope:**
- service-dependencies.md.j2
- storage-topology.md.j2
- storage_projection.py (extended)

**Data requirements:**
- Service dependency graph (from service instance `dependencies`)
- Storage pools with capacity, media type
- Data assets with locations, backup status
- Mount chain resolution

**Acceptance criteria:**
- Service dependency graph renders correctly
- Storage topology shows pool hierarchy
- Data assets linked to storage locations

### Phase E: Operations Layer

**Scope:**
- monitoring-topology.md.j2
- vpn-topology.md.j2
- certificates-topology.md.j2
- qos-topology.md.j2
- ups-topology.md.j2
- operations_projection.py

**Data requirements:**
- Healthchecks, alerts, dashboards (from `instances.healthchecks`, etc.)
- VPN tunnels and remote access
- Certificates with validity, issuers
- QoS policies and queues
- UPS devices and protected loads

**Acceptance criteria:**
- Each diagram renders without errors
- Data accurately reflects compiled model

### Phase F: Meta and Tooling

**Scope:**
- icon-legend.md.j2
- diagrams-index.md.j2
- icon_manager.py
- mermaid_validator.py

**Data requirements:**
- Icon mappings by device type, zone, service type
- Generated files manifest for index

**Acceptance criteria:**
- Icon legend documents all used icons
- Diagrams index links to all generated docs
- Mermaid validation passes for all diagrams

---

## Improvements Over V4

The v5 implementation introduces several improvements:

### Architectural Improvements

1. **Projection contracts**: Typed dataclasses with validation instead of ad-hoc dict access. Each projection defines explicit input/output contracts.

2. **Snapshot testing**: Projection outputs can be golden-tested for stability. Changes to projections are caught before template rendering.

3. **Template hot-reload**: Jinja2 StrictUndefined catches missing variables early, preventing runtime template errors.

4. **Selective generation**: `template_sets` config enables partial generation. Operators can generate only network docs without triggering full regeneration.

5. **Mermaid validation as plugin**: Decoupled from generator, can be skipped in CI or enabled only for release validation.

6. **Icon system reuse**: Available to other generators (e.g., bootstrap docs). IconManager is injected rather than instantiated inline.

7. **Clear boundary**: Generator code is context assembly only, templates do rendering. No inline string construction in generator code.

### Quality Improvements

8. **Compiler-resolved references**: V5 leverages compiler-stage reference resolution instead of duplicating resolution logic in the docs generator.

9. **Status-aware filtering**: Documentation automatically excludes draft/inactive instances based on compiled status field.

10. **Determinism enforcement**: All collections sorted through `_sorted_rows()` helper; no undeterministic iteration.

11. **Diagnostic code governance**: Generator uses reserved code range `E97xx` per ADR 0074 D8.

### Extensibility Improvements

12. **Template set extension**: New template sets can be added without modifying generator code - just add templates and update config.

13. **Projection module extension**: New projections can be added as separate modules with clear contracts.

14. **Icon mapping extension**: New device types or service categories can add icon mappings without generator code changes.

### Performance Improvements

15. **Lazy projection building**: Projections are built only when needed by template sets.

16. **Icon cache reuse**: IconManager maintains SVG data URI cache across all templates.

17. **Single-pass instance extraction**: Uses `_instance_groups()` once per generation instead of per-template layer access.

---

## Consequences

### Benefits

1. Full documentation parity with v4.
2. Plugin-based architecture enables selective generation.
3. Projection layer decouples templates from model structure.
4. Mermaid quality gate catches rendering regressions.
5. Typed projection contracts improve maintainability.
6. Icon system becomes reusable across generators.

### Trade-offs

1. Significant implementation effort (6 phases, estimated 13-18 days).
2. Projection modules add maintenance surface.
3. Icon pack dependencies for full rendering.
4. V4 data resolution logic must be reimplemented in projection layer.

### Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Model mapping complexity | V5 class/object/instance model differs from v4 flat topology | Use projection_core helpers; add comprehensive contract tests |
| Icon pack availability | Mermaid icon-node support depends on renderer configuration | Maintain remote fallback; support compat mode |
| Template drift | Parallel v4/v5 templates during migration may diverge | Semantic comparison tests, not byte-exact |
| Instance group naming | V5 group names may differ from v4 layer names | Use GROUP_* constants from projection_core |
| Reference resolution timing | Some references may not be resolved by compiler | Add explicit resolution in projection layer with fallback |
| Healthcheck/data-asset instances | May be in nested directories (L6-observability/healthchecks) | Support hierarchical instance group discovery |

---

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

---

## References

- ADR 0005: Diagram Generation Determinism
- ADR 0027: Mermaid Rendering Strategy Consolidation
- ADR 0063: Plugin Microkernel Architecture
- ADR 0074: V5 Generator Architecture
- V4 implementation: `v4/topology-tools/scripts/generators/docs/`
- V5 docs generator: `v5/topology-tools/plugins/generators/docs_generator.py`
- Analysis directory: `adr/0079-analysis/`
