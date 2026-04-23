# ADR 0102: Derived Instance Layer Semantics and Path-Decoupled Instance Layout

**Status:** Proposed
**Date:** 2026-04-23
**Depends on:** ADR 0062, ADR 0071, ADR 0088, ADR 0101

---

## Context

Current instance authoring keeps `@layer` in every instance file and enforces layer-bucket directory contracts (`L1-*`, `L2-*`, ...).

In the active topology model, layer semantics already exist in class/object inheritance:

- class contracts define allowed layers;
- object contracts define concrete layer placement;
- instance files already reference object contracts via `@extends`.

For current project data, `instance.@layer` is fully redundant with `object.@layer`, while path-based layer checks add duplication and migration friction.

---

## Decision

Adopt derived layer semantics for instances:

1. **Instance layer is derived from object**
   - Canonical instance layer is resolved via `instance.@extends -> object.@layer`.
   - `instance.@layer` becomes optional authoring metadata (not a required source-of-truth field).

2. **Consistency rule when `@layer` is present**
   - If instance includes `@layer`, it must equal derived object layer.
   - Mismatch is validation error.

3. **Validation shifts from path-layer to semantic-layer**
   - Layer correctness checks must use derived layer and class/object contracts.
   - Path layout is no longer the primary authority for layer identity.

4. **Path decoupling for instances**
   - Instance files may be organized by operational/domain ownership (e.g., host, stack, team), not only by `Lx-*` buckets.
   - Placement validators should enforce deterministic structure rules without requiring layer-bucket path semantics.

---

## Consequences

### Positive

- Removes authoring duplication for layer metadata.
- Strengthens `class -> object -> instance` as the semantic source-of-truth.
- Improves flexibility for project-specific instance tree organization.

### Trade-offs / Risks

- Requires coordinated updates in loaders, validators, and tests.
- Transitional period may require compatibility handling for mixed old/new instance files.

---

## Migration Scope (Phase A)

- `topology-tools/compiler_runtime.py`
- `scripts/validation/validate_v5_layer_contract.py`
- `topology-tools/plugins/validators/foundation_file_placement_validator.py`
- `topology-tools/plugins/compilers/instance_rows_compiler.py` (shape expectations)
- related plugin contract/integration tests

---

## Validation

- `.venv/bin/python -m pytest -q -o addopts= <targeted test set>`
- `task framework:lock-refresh`
- `task framework:strict`
- `task validate:default`
- `task validate:adr-consistency`

---

## References

- `topology/layer-contract.yaml`
- `topology/class-modules/**`
- `topology/object-modules/**`
- `projects/home-lab/topology/instances/**`
- `scripts/validation/validate_v5_layer_contract.py`
- `topology-tools/compiler_runtime.py`
