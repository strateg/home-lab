# ADR 0017: Modular Refactor of topology-tools into Validation and Generation Domains

- Status: Accepted
- Date: 2026-02-21

## Context

`topology-tools/validate-topology.py` has grown into a large monolithic script (~1500 lines),
combining schema validation, semantic checks, cross-layer checks, and reporting.

This increases cognitive load for humans and AI agents:

- difficult local reasoning about one domain (for example storage);
- higher regression risk when editing unrelated checks;
- weak reuse of checker logic across future tooling.

At the same time, operational pipelines (`regenerate-all.py`, CLI usage) depend on stable script entry points.

## Decision

1. Refactor `topology-tools` by domain, introducing:
   - `topology-tools/validation/`
   - `topology-tools/generation/`
2. Keep existing top-level CLI scripts as compatibility entry points during migration.
3. Apply incremental migration by bounded context, not big-bang rewrite.
4. First migration slice: extract storage validation (slots, media registry, attachments, L3 disk refs)
   from `validate-topology.py` into `validation/checks/storage.py`.

## Consequences

Benefits:

- Lower cognitive complexity per file and per change.
- Better maintainability and simpler future extension of validation checks.
- Reduced merge conflicts by domain ownership.

Trade-offs:

- Transitional architecture: some logic remains in legacy script while new modules are introduced.
- Requires strict compatibility tests after each migration slice.

Compatibility:

- No immediate CLI breaking changes.
- `validate-topology.py` remains executable and delegates to extracted modules.

## References

- Primary files:
  - `topology-tools/validate-topology.py`
  - `topology-tools/validation/checks/storage.py`
- Orchestration/compatibility:
  - `topology-tools/regenerate-all.py`
