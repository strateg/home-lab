# ADR 0009: Robust Mermaid Icon Pack Discovery and Render Validation

- Status: Accepted
- Date: 2026-02-20

## Context

After moving to Mermaid icon-node as default (`ADR 0008`), rendering quality depends on runtime icon pack availability.
Initial icon-pack loading in the generator relied on the current working directory, which is fragile when scripts are run from different paths or CI jobs.

At the same time, the project lacked a single automated check that validates Mermaid rendering across all generated documents in both icon-node and compat modes.

## Decision

1. Implement robust icon-pack discovery in `generate-docs.py` by searching multiple roots:
   - current working directory;
   - topology file directory;
   - tool script directory and its repository root.
2. Introduce explicit icon-mode metadata and runtime hints in generation context:
   - `none`, `icon-nodes`, `compat`;
   - mode-specific `mermaid_icon_runtime_hint`.
3. Update all diagram templates to consume the dynamic runtime hint instead of hardcoded icon-node text.
4. Add a dedicated render validation tool:
   - `topology-tools/validate-mermaid-render.py`;
   - validates all Mermaid blocks from generated docs through Mermaid CLI for selected mode.

## Consequences

Benefits:

- Icon pack discovery is resilient to launch directory differences.
- Generated docs show accurate runtime guidance per selected icon mode.
- Rendering regressions are caught quickly with one validation command.

Trade-offs:

- Tooling complexity increases with additional mode metadata and validator script.
- Validation requires Mermaid CLI and icon pack dependencies in local/CI environment.

## References

- Files:
  - `topology-tools/generate-docs.py`
  - `topology-tools/docs_diagrams.py`
  - `topology-tools/validate-mermaid-render.py`
  - `topology-tools/templates/docs/network-diagram.md.j2`
  - `topology-tools/templates/docs/physical-topology.md.j2`
  - `topology-tools/templates/docs/vlan-topology.md.j2`
  - `topology-tools/templates/docs/service-dependencies.md.j2`
  - `topology-tools/templates/docs/storage-topology.md.j2`
  - `topology-tools/templates/docs/monitoring-topology.md.j2`
  - `topology-tools/templates/docs/vpn-topology.md.j2`
  - `topology-tools/templates/docs/qos-topology.md.j2`
  - `topology-tools/templates/docs/certificates-topology.md.j2`
  - `topology-tools/templates/docs/ups-topology.md.j2`
  - `topology-tools/templates/docs/data-links-topology.md.j2`
  - `topology-tools/templates/docs/power-links-topology.md.j2`
  - `topology-tools/templates/docs/trust-zones.md.j2`
  - `topology-tools/README.md`
  - `topology-tools/GENERATORS-README.md`
