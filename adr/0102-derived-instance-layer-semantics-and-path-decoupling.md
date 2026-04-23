# ADR 0102: Derived Instance Layer Semantics and Path-Decoupled Instance Layout

**Status:** Accepted (Implementation Ready)
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
   - `instance.@layer` is optional transition metadata and must match derived layer when present.

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

- `instance.@layer`: optional.
  - If present, it must equal derived layer (`instance -> object -> class`).
- `object.@layer`: deprecated compatibility field.
  - Runtime/validators may read it only as fallback while migration is in progress.
  - Any mismatch between `object.@layer` and derived class layer is a validation violation.

### Cutover (Phase C)

- `object.@layer` becomes prohibited (error-level contract violation).
- Effective layer resolution is strictly:
  - object: `object.@extends -> class.@layer`
  - instance: `instance.@extends -> object.@extends -> class.@layer`
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

## Migration Scope (Phase A)

- `topology-tools/compiler_runtime.py`
- `scripts/validation/validate_v5_layer_contract.py`
- `topology-tools/plugins/validators/foundation_file_placement_validator.py`
- `topology-tools/plugins/compilers/instance_rows_compiler.py` (shape expectations)
- related plugin contract/integration tests

## Migration Scope (Phase B — class/object canonicalization)

- Remove `@layer` from object modules and enforce derivation from `@extends` class.
- Update validators/loaders to prohibit `object.@layer` after cutover window.
- Reorganize `topology/class-modules/**` into layer tree aligned with instance directory naming:
  `L0-meta`, `L1-foundation`, `L2-network`, `L3-data`, `L4-platform`,
  `L5-application`, `L6-observability`, `L7-operations`.
- Keep `topology/object-modules/**` domain/plugin-oriented; generate derived layer index/report for audit views.
- Refresh module index / lock / path-sensitive tests.

---

## Implementation Readiness Contract

1. **Гейт совместимости**
   - На переходный период `instance.@layer` допускается как optional.
   - При наличии `instance.@layer` обязателен strict match с `object.@layer`.

2. **Единое правило вывода**
   - Во всех каналах проверки слой instance вычисляется одинаково:
     `instance.@extends -> object.@layer`.

3. **Критерии завершения реализации**
   - Нет обязательности `@layer` в instance при наличии валидного `@extends`.
   - `object.@layer` полностью удалён из object-модулей и запрещён контрактом.
   - Все layer-checks используют derived layer from class как canonical.
   - Валидации/тесты/strict-пайплайн зелёные.

4. **Rollback boundary**
   - Возможен возврат к mandatory `instance.@layer` без изменения class/object контрактов.
   - Path-ориентированные проверки остаются совместимыми как warning-only fallback на период миграции.

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
