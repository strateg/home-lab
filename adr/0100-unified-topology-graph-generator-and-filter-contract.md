# ADR 0100: Unified Topology Graph Generator and Filter Contract

- Status: Implemented
- Date: 2026-04-22
- Depends on: ADR 0005, ADR 0027, ADR 0079, ADR 0086

## Context

The repository had multiple Mermaid diagram outputs (physical/network/service-focused), but no single configurable graph for cross-domain dependency analysis.

Operator and architecture review workflows needed:

- one unified graph view across physical/network/services/storage/operations;
- deterministic rendering and stable diffs;
- configurable filtering/verbosity controls without template forking;
- plugin-manifest level contract for these controls.

Without a canonical generator contract, diagram behavior was fragmented across templates and ad-hoc rendering decisions.

## Decision

Introduce a dedicated framework generator plugin:

- `base.generator.topology_graph`
- stage: `generate`
- execution mode: `subinterpreter`
- output: `generated/<project>/docs/diagrams/unified-topology.md`

Use `build_topology_projection()` as the canonical projection for unified graph rendering.

Define and enforce a configuration contract for the generator:

- filtering:
  - `domain_filter`
  - `layer_filter`
  - `edge_type_filter`
  - `node_type_filter`
- rendering controls:
  - `graph_direction` (`TB|TD|BT|LR|RL`)
  - `include_external_refs`
  - `show_edge_labels`
  - `show_domain_styling`
  - `show_node_metadata`
  - `cross_domain_edges_dashed`
  - `include_isolated_nodes`
  - `group_nodes_by_domain`
  - `group_nodes_by_layer`
- bounded output controls:
  - `max_nodes` (`0` = unlimited)
  - `max_edges` (`0` = unlimited)

Additional runtime behavior:

- external references are materialized as synthetic `external_ref` nodes;
- cross-domain edges can be rendered as dashed links;
- filtered output statistics and truncation state are emitted in the rendered document.

## Consequences

### Positive

- Canonical, deterministic, cross-domain topology graph is available.
- Graph behavior is now controlled by manifest-backed contract rather than template duplication.
- Operator workflows can switch between detailed and compact views without code changes.
- Integration tests and manifest validation cover the contract surface.

### Trade-offs / Risks

- Increased configuration surface area raises misuse risk if options are combined without intent.
- Mermaid output complexity grows with grouping/styling options.
- Large topologies still require careful limits (`max_nodes`, `max_edges`) for readability.

### Compatibility / Migration

- Default settings preserve backward-compatible rendering style for previously generated unified graph artifacts.
- Existing physical/network/service-specific diagrams remain unchanged.

## References

- Plugin manifest: `topology-tools/plugins/plugins.yaml`
- Generator: `topology-tools/plugins/generators/topology_graph_generator.py`
- Projection: `topology-tools/plugins/generators/projections.py`
- Template: `topology-tools/templates/docs/diagrams/unified-topology.md.j2`
