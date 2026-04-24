# ADR 0102: Derived Instance Layer Semantics and Path-Decoupled Instance Layout

**Status:** Implemented
**Date:** 2026-04-23
**Depends on:** ADR 0062, ADR 0071, ADR 0088, ADR 0101

---

## Context

Current instance authoring keeps `@layer` in every instance file and enforces layer-bucket directory contracts (`L1-*`, `L2-*`, ...).

In the active topology model, layer semantics already exist in class/object inheritance:

- class contracts define canonical layer placement;
- object contracts bind to class contracts;
- instance files already reference object contracts via `@extends`.

Repository analysis for current state:

- all class modules already declare `@layer`;
- all object modules currently duplicate class layer (`object.@layer == class.@layer` for 116/116 objects);
- therefore both `instance.@layer` and `object.@layer` are redundant in current topology semantics.

Path-based layer checks still add duplication and migration friction.

---

## Decision

Adopt **fully derived layer semantics** from `class -> object -> instance`:

1. **Class is the canonical layer source**
   - Canonical entity layer is defined by `class.@layer`.
   - `layer-contract.class_layers.allowed_layers` remains governance policy, but effective runtime layer is `class.@layer`.

2. **Object layer is derived from class**
   - Canonical object layer is resolved via `object.@extends -> class.@layer`.
   - `object.@layer` is removed from object modules (non-canonical and prohibited after migration).

3. **Instance layer is derived via object -> class chain**
   - Canonical instance layer is resolved via `instance.@extends -> object.@extends -> class.@layer`.
   - `instance.@layer` is non-canonical and prohibited (same anti-duplication policy as objects).
   - Instance shard grouping key is canonical `@group` (plain `group` is deprecated/non-canonical).

4. **Validation shifts from path-layer to semantic-layer**
   - Layer correctness checks must use derived layer and class/object contracts.
   - Path layout is not the primary authority for layer identity.

5. **Layer-oriented source-tree placement for class modules (required)**
   - `topology/class-modules/` must be reorganized by layer buckets using the same names as instance layer directories:
     - `L0-meta`, `L1-foundation`, `L2-network`, `L3-data`,
     - `L4-platform`, `L5-application`, `L6-observability`, `L7-operations`.
   - Class files must be placed under the directory that matches canonical `class.@layer`.

6. **Object modules stay domain/plugin-oriented**
   - `topology/object-modules/` keeps domain/plugin-centric layout (no mandatory `L0`…`L7` path contract).
   - Layer for objects is enforced semantically via `object.@extends -> class.@layer`, not by directory path.

7. **Instances are path-decoupled**
   - `projects/*/topology/instances/` may be organized by operational/domain ownership (host/stack/team/etc).
   - Instance placement no longer обязано mirror `Lx-*` buckets.

8. **Path non-authority rule**
   - Directory path must not be used as canonical source for layer resolution.
   - Path-based checks are policy/hygiene checks only and cannot override semantic derivation.

---

## Transition and Cutover Policy

### Transitional compatibility window (Phase A/B)

- `object.@layer`: deprecated compatibility field.
  - Runtime/validators may read it only as fallback while migration is in progress.
  - Any mismatch between `object.@layer` and derived class layer is a validation violation.

### Cutover (Phase C)

- `object.@layer` becomes prohibited (error-level contract violation).
- `instance.@layer` becomes prohibited (error-level contract violation).
- `group` in instance shards is replaced by canonical `@group`.
- Effective layer resolution is strictly:
  - object: `object.@extends -> class.@layer`
  - instance: `instance.@extends -> object.@extends -> class.@layer`
- Legacy instance layer-bucket paths (`L0-*`…`L7-*`) are no longer accepted by compiler runtime.
  Canonical shard path contract is only:
  - `<group>/<instance>.yaml`
  - `<group>/<host-shard>/<instance>.yaml`
- Path-based layer assumptions remain non-authoritative.

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

## SWOT Analysis

### Strengths

- Устраняет дублирование `@layer` на уровне instance.
- Устраняет дублирование `@layer` на уровне object.
- Делает `class -> object -> instance` единственным семантическим источником слоя.
- Упрощает дальнейшую эволюцию структуры `instances/` без перепривязки к `Lx-*` директориям.

### Weaknesses

- Повышается чувствительность к корректности `class.@layer` (единственная точка истины).
- Появляется дополнительная логика вывода (derivation), которую нужно поддерживать в нескольких валидаторах.
- Требуется массовое перемещение class-файлов по layer-директориям.

### Opportunities

- Перейти к ownership/domain-ориентированной структуре instance-файлов.
- Централизовать проверки слоёв в семантическом контракте вместо path-правил.
- Снизить когнитивную нагрузку при добавлении новых instance.

### Threats

- Расхождение поведения между runtime loader и независимыми validation-скриптами.
- Частичная миграция может создать «серую зону» смешанных правил.
- Ошибки в class-layer mapping могут привести к массовым ложным диагностическим ошибкам.
- Риск регрессий в toolchain из-за path-aware логики при переезде class-модулей.

---

## Implementation Plan (Phase A/B/C)

### Phase A — Runtime/Validator semantic alignment (compatibility mode)

**Scope**
- `topology-tools/compiler_runtime.py`
- `topology-tools/plugins/validators/foundation_file_placement_validator.py`
- `scripts/validation/validate_v5_layer_contract.py`
- `topology-tools/plugins/compilers/instance_rows_compiler.py` (row-shape compatibility)
- shared derivation helper(s) and related tests

**Required behavior**
- Single derivation chain in all execution paths:
  `instance.@extends -> object.@extends -> class.@layer`.
- `instance.@layer` is optional; if present, strict-match with derived layer.
- `object.@layer` allowed only as transitional fallback; mismatch with class-derived layer is violation.
- Path is non-authoritative for layer identity.

**Gate criteria (must pass)**
1. Runtime and validators produce consistent layer decisions for identical fixtures.
2. No mandatory dependency on instance path bucket for layer resolution.
3. Contract + integration tests cover:
   - missing `instance.@layer` + valid class chain (PASS),
   - explicit `instance.@layer` mismatch (FAIL),
   - `object.@layer` mismatch vs class-derived layer (FAIL).

**Test evidence (attach in PR)**
- Targeted pytest output for affected suites.
- `task validate:default` output.
- `task framework:strict` output.

---

### Phase B — Canonicalization and structure migration

**Scope**
- Move class files into required layer directories:
  `L0-meta`, `L1-foundation`, `L2-network`, `L3-data`,
  `L4-platform`, `L5-application`, `L6-observability`, `L7-operations`.
- Keep `topology/object-modules/**` domain/plugin-oriented.
- Remove redundant `instance.@layer` where safely derivable.
- Prepare/execute removal of `object.@layer` from object modules.
- Refresh module index / framework lock / path-sensitive tests.

**Gate criteria (must pass)**
1. All class modules reside in the directory matching canonical `class.@layer`.
2. Module loading/compilation remains deterministic after moves.
3. No functional regression in generators/validators caused by path migration.

**Test evidence (attach in PR)**
- File-move map (old path -> new path) in PR description.
- `task framework:lock-refresh` output.
- `task validate:default` output.
- `task framework:strict` output.

---

### Phase C — Strict cutover enforcement

**Scope**
- Enforce error-level prohibition of `object.@layer`.
- Enforce error-level prohibition of `instance.@layer`.
- Remove fallback reads of `object.@layer` from runtime/validators.
- Keep rollback playbook and temporary compatibility branch/tag.

**Gate criteria (must pass)**
1. `object.@layer` in any object module fails validation with deterministic error code.
2. `instance.@layer` in any instance shard fails validation with deterministic error code.
3. Effective layer resolution uses only class-derived chain.
4. All quality gates green on full topology.

**Test evidence (attach in PR)**
- Negative test evidence showing `object.@layer` rejection.
- Full validation evidence:
  - `task validate:default`
  - `task framework:strict`
  - `task validate:adr-consistency`

---

## Rollback boundary

- Emergency rollback may temporarily re-enable `object.@layer` fallback without reverting class-directory migration.
- Rollback does not change canonical policy in this ADR (class remains source-of-truth); it only restores compatibility behavior in tooling.

---

## Implementation Status

- Phase A: completed
- Phase B: completed
- Phase C: completed

Evidence:
- targeted contract/integration tests for derivation and strict cutover
- `task framework:layer-derivation-report`
- `task framework:lock-refresh`
- `task validate:default`
- `task framework:strict`
- `task validate:adr-consistency`

---

## References

- `topology/layer-contract.yaml`
- `topology/class-modules/**`
- `topology/object-modules/**`
- `projects/home-lab/topology/instances/**`
- `scripts/validation/validate_v5_layer_contract.py`
- `topology-tools/compiler_runtime.py`
