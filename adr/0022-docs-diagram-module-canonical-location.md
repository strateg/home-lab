# ADR 0022: Use scripts/generation/docs/docs_diagram.py as Canonical Diagram Module

- Status: Accepted
- Date: 2026-02-21

## Context

After moving documentation generation into `scripts/generation/docs`, diagram logic still had transitional naming
and compatibility shims. The requirement is to keep diagram code physically inside the documentation generation domain.

## Decision

1. Set canonical module path for documentation diagrams to:
   - `topology-tools/scripts/generation/docs/docs_diagram.py`
2. Update documentation generator imports to use this module directly.
3. Remove root-level compatibility shim file for diagram module.

## Consequences

Benefits:

- Diagram code is unambiguously part of docs generation domain.
- Reduced indirection and fewer transitional modules.
- Cleaner module ownership inside `scripts/generation/docs`.

Trade-offs:

- Any external imports from old shim path must be updated.

Compatibility:

- CLI behavior and generated documentation outputs are unchanged.

## References

- `topology-tools/scripts/generation/docs/docs_diagram.py`
- `topology-tools/scripts/generation/docs/generator.py`
