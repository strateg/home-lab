# Topology Fixtures

Compatibility fixtures used for ADR-0026 migration hardening.

## Fixture classes

- `legacy-only/`:
  snapshot exported from commit `271762c` (pre-runtime/pre-endpoint model).
- `mixed/`:
  snapshot exported from commit `e072616` (dual model, legacy + new fields).
- `new-only/`:
  snapshot exported from `HEAD` (strict new-model topology).

Each fixture contains:

- `topology.yaml`
- `topology/` layered source tree required by `!include` loading.

## Validation contract

- `legacy-only` and `mixed` are validated in `compat` mode.
- `new-only` is validated in `strict` mode and must have zero migration items.

Use:

```bash
python topology-tools/run-fixture-matrix.py
```

This runs validation, migration-report checks, and generator smoke tests for all fixture classes.
