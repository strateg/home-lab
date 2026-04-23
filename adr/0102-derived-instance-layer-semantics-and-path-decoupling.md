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

5. **Layer-oriented source-tree placement only for class modules**
   - `topology/class-modules/` may be reorganized to top-level layer buckets: `L0`…`L7`.
   - This is optional but recommended because class is the canonical layer source.

6. **Object modules stay domain/plugin-oriented**
   - `topology/object-modules/` keeps domain/plugin-centric layout (no mandatory `L0`…`L7` path contract).
   - Layer for objects is enforced semantically via `object.@extends -> class.@layer`, not by directory path.

7. **Instances are path-decoupled**
   - `projects/*/topology/instances/` may be organized by operational/domain ownership (host/stack/team/etc).
   - Instance placement no longer обязано mirror `Lx-*` buckets.

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
- Возможно потребуется частичное перемещение class-файлов по layer-директориям.

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
- (Optional) Reorganize `topology/class-modules/**` into `L0..L7` tree.
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
