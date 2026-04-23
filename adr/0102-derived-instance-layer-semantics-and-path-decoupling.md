# ADR 0102: Derived Instance Layer Semantics and Path-Decoupled Instance Layout

**Status:** Accepted (Implementation Ready)
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

## SWOT Analysis

### Strengths

- Устраняет дублирование `@layer` на уровне instance.
- Делает `class -> object -> instance` единственным семантическим источником слоя.
- Упрощает дальнейшую эволюцию структуры `instances/` без перепривязки к `Lx-*` директориям.

### Weaknesses

- Повышается чувствительность к качеству object-модулей (`@layer` в object теперь критичен).
- Появляется дополнительная логика вывода (derivation), которую нужно поддерживать в нескольких валидаторах.

### Opportunities

- Перейти к ownership/domain-ориентированной структуре instance-файлов.
- Централизовать проверки слоёв в семантическом контракте вместо path-правил.
- Снизить когнитивную нагрузку при добавлении новых instance.

### Threats

- Расхождение поведения между runtime loader и независимыми validation-скриптами.
- Частичная миграция может создать «серую зону» смешанных правил.
- Ошибки в object-layer mapping могут привести к массовым ложным диагностическим ошибкам.

---

## Migration Scope (Phase A)

- `topology-tools/compiler_runtime.py`
- `scripts/validation/validate_v5_layer_contract.py`
- `topology-tools/plugins/validators/foundation_file_placement_validator.py`
- `topology-tools/plugins/compilers/instance_rows_compiler.py` (shape expectations)
- related plugin contract/integration tests

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
   - Все layer-checks используют derived layer как canonical.
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
