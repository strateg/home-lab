# ADR 0005: Improve Diagram Generation Determinism and Firewall Binding Visibility

- Status: Accepted
- Date: 2026-02-20
- Supersedes: -

## Context

Diagram generation logic had significant duplication and unstable ordering across pages.
This complicated maintenance and could produce noisy diffs between runs.
After introducing `firewall_policy_refs` in L2 networks, trust-zone documentation also needed an explicit network-to-policy binding view.

## Decision

1. Introduce shared rendering helpers in `topology-tools/docs_diagrams.py`:
   - centralized page render/write flow;
   - shared data extraction for link-based diagrams.
2. Make diagram inputs deterministic by sorting collections before rendering.
3. Use one in-memory diagrams catalog as a single source for:
   - diagrams index generation;
   - summary output item list.
4. Extend trust-zones documentation with explicit `network -> firewall_policy_refs` bindings.

## Consequences

Benefits:

- Lower maintenance cost in diagram generator code.
- Stable output ordering and cleaner diffs in generated docs.
- Better auditability of firewall intent per network.

Trade-offs:

- Larger refactor in one module may complicate future cherry-picks.
- Additional template section increases page length for trust-zones.

## References

- Files:
  - `topology-tools/docs_diagrams.py`
  - `topology-tools/templates/docs/trust-zones.md.j2`
  - `topology-tools/generate-docs.py`
