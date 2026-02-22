# ADR 0027: Consolidate Mermaid Rendering Strategy and Quality Gates

- Status: Accepted
- Date: 2026-02-22
- Supersedes:
  - [0007](0007-icon-legend-and-complete-device-icon-coverage.md)
  - [0008](0008-mermaid-icon-node-default-and-runtime-pack-registration.md)
  - [0009](0009-robust-icon-pack-discovery-and-render-validation.md)
  - [0010](0010-regeneration-pipeline-mermaid-quality-gate.md)

## Context

Mermaid-related decisions were split across multiple narrowly scoped ADRs during rapid iteration.
That sequence was useful during active change, but now creates fragmentation in day-to-day governance:

1. Operator guidance is spread across several ADR files.
2. The ADR register looks noisier than the real decision surface.
3. Contributors must chase historical links to understand the current contract.

The implementation is now stable and can be represented as one canonical policy ADR.

## Decision

1. Keep Mermaid icon-node output as default for generated docs.
2. Keep compatibility paths explicit:
   - plain mode (`--no-mermaid-icons`);
   - icon-compat mode where renderer support is limited.
3. Keep runtime icon-pack contract explicit:
   - icon aliases `si` and `mdi` are canonical;
   - docs output must include runtime hints for icon registration.
4. Keep icon semantics documented in generated documentation via an icon legend page and diagrams index linkage.
5. Keep Mermaid render validation as a regeneration quality gate by default, with explicit opt-out (`--skip-mermaid-validate`) for constrained environments.
6. Consolidate governance by treating ADR-0007..0010 as superseded historical steps.

## Consequences

Benefits:

- One source of truth for Mermaid generation behavior.
- Lower cognitive overhead in ADR review and onboarding.
- Clear distinction between canonical policy and historical migration steps.

Trade-offs:

- Fine-grained historical rationale is now split between this summary ADR and superseded details.
- Future Mermaid changes should prefer updating this ADR unless a new decision boundary appears.

## References

- Replaced ADRs:
  - [0007](0007-icon-legend-and-complete-device-icon-coverage.md)
  - [0008](0008-mermaid-icon-node-default-and-runtime-pack-registration.md)
  - [0009](0009-robust-icon-pack-discovery-and-render-validation.md)
  - [0010](0010-regeneration-pipeline-mermaid-quality-gate.md)
- Tooling:
  - `topology-tools/regenerate-all.py`
  - `topology-tools/validate-mermaid-render.py`
  - `topology-tools/scripts/generators/docs/`
  - `topology-tools/templates/docs/`
