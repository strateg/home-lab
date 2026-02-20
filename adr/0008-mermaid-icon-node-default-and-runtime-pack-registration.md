# ADR 0008: Make Mermaid Icon-Node the Default and Require Runtime Icon Pack Registration

- Status: Accepted
- Date: 2026-02-20
- Supersedes: [0006](0006-mermaid-icon-mode-with-fallback.md)

## Context

The project adopted specialized Mermaid icons for professional topology diagrams.
`ADR 0006` introduced icon mode as optional with compatibility-first defaults.
Current usage goals prioritize icon-rich output by default and align with Mermaid's native icon-node flow via `registerIconPacks(...)`.

## Decision

1. Enable icon generation by default in `generate-docs.py`.
2. Make Mermaid icon-node syntax (`@{ icon: "...", ... }`) the default output mode.
3. Keep a compatibility fallback mode for older renderers:
   - `--mermaid-icon-compat` converts icon-nodes to standard Mermaid nodes with inline icon labels.
4. Keep explicit disable switch:
   - `--no-mermaid-icons` for plain, icon-free diagrams.
5. Standardize runtime guidance for icon pack registration:
   - pack aliases used in diagrams: `si`, `mdi`;
   - documented for CDN and bundler flows in tooling READMEs.

## Consequences

Benefits:

- Professional diagrams are produced by default without extra flags.
- Mermaid-native icon nodes are first-class for environments that support them.
- Compatibility fallback still exists for strict or older renderers.

Trade-offs:

- Default output now assumes renderer support for icon nodes and registered packs.
- Consumers without Mermaid icon-node support must opt into compatibility mode.

## References

- Files:
  - `topology-tools/generate-docs.py`
  - `topology-tools/docs_diagrams.py`
  - `topology-tools/README.md`
  - `topology-tools/GENERATORS-README.md`
  - `adr/REGISTER.md`
- External:
  - https://docs.mermaidchart.com/mermaid-oss/config/icons.html
  - https://iconify.design/docs/icons/icon-sets/
