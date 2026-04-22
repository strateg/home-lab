# SPC STEP 1: DOCUMENT MAP

**Analysis Task:** Mermaid diagram generation — dependency graph visualization, unification, algorithm improvements, fixes

**Created:** 2026-04-22

---

## Sources of Truth Table

| Category | Type | Path | Role | Authority | Notes |
|----------|------|------|------|-----------|-------|
| **ADR (Architecture)** |
| ADR | Decision | `adr/0005-diagram-generation-determinism-and-binding-visibility.md` | Sorting/determinism policy | ✅ Canonical | Sorted collections, centralized helpers |
| ADR | Decision | `adr/0027-mermaid-rendering-strategy-consolidation.md` | Icon mode contract | ✅ Canonical | icon-nodes (default), compat, none modes |
| ADR | Migration | `adr/0079-v5-documentation-and-diagram-generation-migration.md` | V4→V5 migration context | ✅ Canonical | Projection pattern, architectural issues |
| **Core Implementation** |
| Plugin | Generator | `topology-tools/plugins/generators/diagram_generator.py` | Diagram generation plugin | ✅ Primary | Renders 4 templates (physical, network, legend, index) |
| Plugin | Generator | `topology-tools/plugins/generators/docs_generator.py` | Base docs generator | ✅ Primary | Renders 19 doc templates |
| Module | Projection | `topology-tools/plugins/generators/projections.py` | Projection builders | ✅ Primary | 385 lines: build_diagram_projection, build_docs_projection |
| Module | Icon mgmt | `topology-tools/plugins/icons/icon_manager.py` | Icon resolution + SVG cache | ✅ Primary | IconManager with si/mdi packs |
| Module | Icon data | `topology-tools/plugins/icons/mappings.py` | Icon registry | ✅ Primary | CLASS_ICON_BY_PREFIX, SERVICE_ICON_BY_PREFIX, ZONE_ICON_BY_NAME |
| **Domain Projections** |
| Module | Projection | `topology-tools/plugins/generators/docs/physical_projection.py` | Physical topology view | ✅ Primary | Devices, data_links, physical_links, power |
| Module | Projection | `topology-tools/plugins/generators/docs/network_projection.py` | Network topology view | ✅ Primary | Networks, bridges, IP allocations |
| Module | Projection | `topology-tools/plugins/generators/docs/security_projection.py` | Security view | ✅ Primary | Trust zones, VLANs, firewall policies |
| Module | Projection | `topology-tools/plugins/generators/docs/storage_projection.py` | Storage view | ✅ Primary | Pools, volumes, data assets |
| Module | Projection | `topology-tools/plugins/generators/docs/operations_projection.py` | Operations view | ✅ Primary | Backups, healthchecks, alerts |
| Module | Helper | `topology-tools/plugins/generators/projection_core.py` | Projection utilities | ✅ Primary | _instance_groups, _sorted_rows, _safe_id |
| **Templates (Jinja2)** |
| Template | Diagram | `topology-tools/templates/docs/diagrams/physical-topology.md.j2` | Physical topology Mermaid | ✅ Primary | graph TB with icon-nodes, data links |
| Template | Diagram | `topology-tools/templates/docs/diagrams/network-topology.md.j2` | Network topology Mermaid | ✅ Primary | Trust zone subgraphs with VLANs |
| Template | Diagram | `topology-tools/templates/docs/diagrams/icon-legend.md.j2` | Icon legend | ✅ Primary | Icon semantics documentation |
| Template | Diagram | `topology-tools/templates/docs/diagrams/diagrams-index.md.j2` | Diagrams index | ✅ Primary | Links to all diagram pages |
| Template | Diagram | `topology-tools/templates/docs/service-dependencies.md.j2` | Service dependency graph | ✅ Primary | graph LR with service→service edges |
| Template | Docs | `topology-tools/templates/docs/monitoring-topology.md.j2` | Monitoring diagram | ✅ Secondary | Healthchecks, alerts |
| Template | Docs | `topology-tools/templates/docs/data-flow-topology.md.j2` | Data flow diagram | ✅ Secondary | Logs/metrics/backups flows |
| Template | Docs | `topology-tools/templates/docs/vlan-topology.md.j2` | VLAN table | ✅ Secondary | VLAN inventory (no diagram) |
| Template | Docs | `topology-tools/templates/docs/*.md.j2` | Other docs (16 files) | ✅ Secondary | overview, devices, services, storage, etc. |
| **Generated Outputs (Examples)** |
| Output | Diagram | `generated/home-lab/docs/service-dependencies.md` | Service dependency graph example | 📊 Reference | Shows current output quality |
| Output | Diagram | `generated/home-lab/docs/diagrams/physical-topology.md` | Physical topology example | 📊 Reference | Shows icon-nodes mode |
| Output | Diagram | `generated/home-lab/docs/diagrams/network-topology.md` | Network topology example | 📊 Reference | Shows trust zone subgraphs |
| **Tests** |
| Test | Contract | `tests/plugin_integration/test_projection_helpers.py` | Projection contract tests | ✅ Validation | Tests projection builder stability |
| Test | Contract | `tests/plugin_integration/test_generator_projection_contract.py` | Generator isolation tests | ✅ Validation | Ensures generators use projections only |
| Test | Integration | `tests/plugin_integration/test_docs_generator.py` | Docs generator tests | ✅ Validation | End-to-end rendering tests |
| Test | Plugin | `tests/plugin_integration/test_icon_manager.py` | Icon manager tests | ✅ Validation | Icon resolution tests |
| **Configuration** |
| Manifest | Plugin | `topology-tools/plugins/plugins.yaml` | Framework plugin manifest | ✅ Config | Plugin registration |
| Manifest | Object | `topology/object-modules/*/plugins.yaml` | Object plugin manifests | ✅ Config | Object-specific plugins |

---

## Document Classification Summary

| Category | Count | Authority Level |
|----------|-------|----------------|
| ADR (Architecture Decisions) | 3 | ✅ Canonical |
| Core Implementation (plugins/modules) | 11 | ✅ Primary |
| Templates (Jinja2) | 22 | ✅ Primary |
| Generated Examples | 3 | 📊 Reference |
| Tests | 4 | ✅ Validation |
| Configuration | 2 | ✅ Config |
| **Total** | **45** | - |

---

## Key Authorities

1. **ADR 0027** — Icon mode contract (icon-nodes, compat, none)
2. **ADR 0005** — Determinism via sorting
3. **ADR 0079** — V4→V5 migration context
4. **`projections.py`** — Projection transformation logic
5. **`diagram_generator.py`** — Diagram rendering plugin
6. **`icon_manager.py`** — Icon resolution runtime

---

## Scope Boundaries

**In Scope:**
- Service dependency graph visualization
- Mermaid diagram generation algorithms
- Projection-to-template data flow
- Icon resolution and rendering
- ID sanitization consistency
- Diagram determinism and quality

**Out of Scope:**
- Topology model compilation (compiler plugins)
- Terraform/Ansible generation
- Bootstrap package generation
- Deployment workflows
- Secret management
- V4 archive parity

---

**DOCUMENT MAP COMPLETE** ✅

Ready for **STEP 2: CONSTRAINTS REGISTER**

**GO STEP 2?**
