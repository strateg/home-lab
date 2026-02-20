# ADR 0007: Add Icon Legend Page and Complete Device Icon Coverage

- Status: Accepted
- Date: 2026-02-20
- Supersedes: -

## Context

ADR 0006 introduced optional Mermaid icon mode with fallback.
After first rollout, icon mapping still needed two improvements:

1. Explicit documentation of icon semantics directly in generated docs.
2. Stable and complete icon coverage for all modeled device types, including cloud-provider specific visual identity.

Without this, teams may interpret icons inconsistently and output could vary depending on which concrete devices are encountered first.

## Decision

1. Add a dedicated generated page `icon-legend.md` with:
   - device type icons;
   - trust zone icons;
   - cloud provider icons;
   - external endpoint icon patterns.
2. Include `Icon Legend` in documentation navigation/index.
3. Expand icon mapping to cover all current `DeviceType` values with stable defaults.
4. Keep provider-specific icons in a separate cloud-provider mapping, while preserving generic `cloud-vm` icon for device type legend stability.

## Consequences

Benefits:

- Icon language is explicit, auditable, and discoverable in generated docs.
- Visual consistency across all topology diagrams.
- Reduced ambiguity for future contributors when extending templates.

Trade-offs:

- Additional generated page to maintain in navigation.
- Slightly more complex generator logic for icon selection.

## References

- Files:
  - `topology-tools/docs_diagrams.py`
  - `topology-tools/templates/docs/icon-legend.md.j2`
  - `topology-tools/templates/docs/diagrams-index.md.j2`
  - `topology-tools/templates/docs/overview.md.j2`
