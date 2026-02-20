# ADR 0006: Add Mermaid Icon Mode with Template Fallback

- Status: Accepted
- Date: 2026-02-20
- Supersedes: -

## Context

Generated topology diagrams were readable but visually generic.
The project needs more professional-looking diagrams with specialized infrastructure/vendor icons while preserving compatibility for Mermaid renderers that do not preload icon packs.

## Decision

1. Add optional CLI flag `--mermaid-icons` to `generate-docs.py`.
2. Keep default output icon-free for maximum compatibility.
3. When icon mode is enabled:
   - render icon nodes in selected docs templates;
   - use Iconify-based IDs with two packs:
     - `si` (Simple Icons)
     - `mdi` (Material Design Icons)
4. Keep fallback behavior in templates via conditional rendering:
   - icon mode: `@{ icon: "...", ... }` nodes;
   - compatibility mode: plain labeled nodes.
5. Document renderer prerequisites in tool READMEs.

## Consequences

Benefits:

- More professional diagram aesthetics when icon packs are available.
- Backward compatibility retained by default.
- No schema/topology model changes required for visual improvements.

Trade-offs:

- Icon mode depends on renderer-side pack registration.
- Additional template complexity due to dual rendering paths.

## References

- Files:
  - `topology-tools/generate-docs.py`
  - `topology-tools/docs_diagrams.py`
  - `topology-tools/templates/docs/data-links-topology.md.j2`
  - `topology-tools/templates/docs/power-links-topology.md.j2`
  - `topology-tools/templates/docs/trust-zones.md.j2`
  - `topology-tools/README.md`
  - `topology-tools/GENERATORS-README.md`
- External:
  - https://docs.mermaidchart.com/mermaid-oss/config/icons.html
  - https://iconify.design/docs/icons/icon-sets/
