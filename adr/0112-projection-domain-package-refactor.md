# ADR 0112: Projection Domain Package Refactor

- Status: Proposed
- Date: 2026-07-03
- Related: ADR-0074 (Generator Architecture), ADR-0078 (Object Module Layout), ADR-0079 (Docs/Diagram Migration), ADR-0104 (Ansible Role Generation), ADR-0106 (Capability-Driven Plugins)

## Context

`topology-tools/plugins/generators/projections.py` has grown to ~1,289 LOC and mixes
builders from at least six distinct concerns in a single module:

- Ansible inventory projection (`build_ansible_projection`)
- Ansible role projection and role host_vars builders (ADR 0104/0106:
  `CAPABILITY_ROLE_MAP`, `build_ansible_role_projection`, `build_host_vars_for_role`, ...)
- Docs projection orchestrator (`build_docs_projection`) delegating to five domain
  sub-projections that already live in `plugins/generators/docs/`
- Diagram projection (`build_diagram_projection`) with Mermaid helpers
  (`_safe_id`, `_icon_for_class`, zone colour palette, `IconManager` instance)
- Topology graph projection (`build_topology_projection`) with node/edge collectors
  and six `_extract_*_dependencies` helpers

ADR 0079 already established the five documentation domains (network, physical,
security, storage, operations) as separate modules, but they are filed under a
`docs/` package name that describes a consumer, not the domain layer. The main
orchestration file remains a cross-domain monolith, which raises review cost and
invites hidden coupling between unrelated builders.

Constraints:

- Zero functional change: golden projection snapshots
  (`tests/plugin_integration/test_projection_snapshots.py`) and manifest `produces`
  keys (`docs_projection`, `topology_graph_projection`, ...) must remain identical.
- `plugins.generators.projection_core` is imported by object-modules
  (proxmox/mikrotik/oracle `plugins/projections.py`) and must keep its import path
  (ADR 0078 object-module compatibility).
- `object_projection_loader.py` loads `bootstrap_projections.py` by file name from
  the framework generators root; that file must not move.
- Subinterpreter execution (ADR 0097) imports plugin modules via `sys.path`
  entries for both `topology-tools` and `topology-tools/plugins`; the canonical
  import prefix is `plugins.generators.*`.

## Decision

Dissolve `plugins/generators/projections.py` and the `plugins/generators/docs/`
package into a single domain-oriented package:

```
topology-tools/plugins/generators/projections/
├── __init__.py        # docstring only, no re-exports
├── mermaid.py         # Mermaid helpers: _safe_id, _icon_for_class, _zone_label,
│                      # zone colour palette, single IconManager instance
├── ansible.py         # build_ansible_projection, CAPABILITY_ROLE_MAP,
│                      # build_ansible_role_projection, role host_vars builders
├── ansible_roles.py   # moved verbatim from generators/ansible_role_projections.py
├── docs.py            # build_docs_projection (domain orchestrator)
├── diagram.py         # build_diagram_projection
├── topology_graph.py  # build_topology_projection + node/edge collectors
├── network.py         # moved from docs/network_projection.py   (ADR 0079 Phase A)
├── physical.py        # moved from docs/physical_projection.py  (ADR 0079 Phase B)
├── security.py        # moved from docs/security_projection.py  (ADR 0079 Phase C)
├── storage.py         # moved from docs/storage_projection.py   (ADR 0079 Phase D)
└── operations.py      # moved from docs/operations_projection.py (ADR 0079 Phase E)
```

Rules:

1. Full import migration, no compatibility shims: `projections.py`,
   `ansible_role_projections.py`, and the `docs/` package are deleted in the same
   change; all consumers (5 generator plugins, projection tests) import directly
   from the new domain modules.
2. `ProjectionError` is imported from its defining module
   `plugins.generators.projection_core` (no re-export through the package).
3. `projection_core.py`, `bootstrap_projections.py`, and
   `object_projection_loader.py` stay in place (object-module import stability and
   loader file-name coupling).
4. New modules use only the `plugins.generators.projections.*` import prefix to
   avoid duplicate module objects under the dual `sys.path` roots (ADR 0097).
5. Code moves are verbatim; only intra-package imports change. Behavioural
   equivalence is proven by unchanged golden snapshots.

## Consequences

What improves:

- Cross-domain monolith (1,289 LOC) becomes ~11 focused domain modules aligned
  with ADR 0079 domains and the ADR 0106 capability-driven layout.
- Domain builders can be reviewed and tested in isolation; the `docs/` misnomer
  is removed.

Trade-offs / risks:

- One-time import churn across 5 generators and 4 test modules.
- `framework.lock` integrity changes and must be refreshed (CORE-005).
- Historical documents (ADR 0079/0104/0106 analysis plans) reference old import
  paths; they are records and are intentionally not rewritten. This ADR
  supersedes the file-layout description in ADR 0079 (projection module
  locations only, not the domain contracts).

Migration impact:

- No topology, template, or generated-artifact change; recompile only revalidates.
- Object-modules are unaffected.

## References

- Commit: (filled on implementation)
- Schema: -
- Docs: `adr/0079-analysis/`, `docs/ai/rules/generator-artifacts.md`
