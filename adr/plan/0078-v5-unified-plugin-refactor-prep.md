# ADR0078: v5 Unified Plugin Refactor Preparation

**Date:** 2026-03-22
**Status:** Completed (WP6-WP10 all completed)
**Amended:** 2026-03-22 (WP6-WP10 added for boundary enforcement)
**Amended:** 2026-03-22 (WP9-WP10 executed)
**Related:** `adr/0078-object-module-local-template-layout.md`, `adr/plan/0078-plugin-layering-and-v4-v5-migration-plan.md`

---

## ADR0080 Alignment Note (2026-03-27)

1. Этот документ закрывает historical prep/refactor scope WP6-WP10 и остается reference-only.
2. Scope этого документа ограничен эпохой `compiler/validator/generator` перед расширением ADR0080.
3. Текущий runtime baseline использует 6 plugin families и 6-stage lifecycle (`discover -> compile -> validate -> generate -> assemble -> build`).
4. Для активного cutover-контроля использовать `adr/plan/0078-cutover-checklist.md`.

---

## 1. Purpose

Подготовить v5 рефакторинг под единые правила для всех типов плагинов:

1. discoverers;
2. compilers;
3. validators;
4. generators.

---

## 2. Unified Rules Baseline

1. Архитектура строго 4-уровневая:
   - global/core;
   - class;
   - object;
   - instance.
2. Уровень class не содержит object/instance-specific зависимостей.
3. Уровень object не содержит instance-specific зависимостей.
4. Плагин уровня `N` использует только интерфейсы, которые реализует уровень `N+1`.
5. Глобальные плагины без class/object-specific имен переносятся в core/global уровень.
6. Глобальные плагины оркестрируют специализированные плагины через интерфейсы или проектные паттерны.
7. Весь код следует SOLID.

---

## 3. Refactor Inventory Deliverables

Обязательные артефакты перед стартом рефакторинга:

1. Полный реестр плагинов по семействам и уровням:
   - plugin id;
   - family (`discoverer|compiler|validator|generator`);
   - level (`core|class|object|instance`);
   - owner manifest/path.
2. Карта нарушений:
   - cross-level direct imports/calls;
   - leakage высоких уровней;
   - global plugins с конкретной class/object логикой;
   - **instance-specific literals in object-level code** (NEW);
   - **cross-object imports** (NEW);
   - **hardcoded module paths** (NEW).
3. Карта целевых интерфейсов:
   - какой глобальный плагин оркестрирует какие specialized плагины;
   - какой контракт заменяет прямую зависимость.

### 3.1 Violation Status (2026-03-22)

| Violation Type | Location | Details | State |
|----------------|----------|---------|-------|
| Instance literal | `mikrotik/plugins/terraform_mikrotik_generator.py` | Hardcoded IP removed; config/projection resolution added | Resolved |
| Instance literal | `proxmox/plugins/terraform_proxmox_generator.py` | Hardcoded hostname removed; config/projection resolution added | Resolved |
| Hardcoded paths | `object_projection_loader.py` | Static mapping replaced with dynamic discovery | Resolved |
| Missing test | `test_plugin_level_boundaries.py` | Cross-object import scan added | Resolved |
| Capability coupling | `terraform_mikrotik_generator.py` | Mapping externalized to manifest `capability_templates`; hardcoded selection removed from code | Resolved |

---

## 4. Execution Batches

1. Batch A: core/global cleanup
   - отделить global orchestration от domain-specific logic;
   - подготовить shared interfaces.
2. Batch B: class-level normalization
   - убрать object/instance leakage;
   - унифицировать class-level contracts.
3. Batch C: object-level normalization
   - убрать instance leakage;
   - выровнять object manifest ownership.
4. Batch D: instance-level strictness
   - закрепить instance-only semantics;
   - убрать дублирующую оркестрацию из higher levels.

---

## 5. Mandatory Gates Per Batch

1. `python -m pytest -o addopts= v5/tests/plugin_contract/test_plugin_level_boundaries.py -q`
2. `task test:parity-v4-v5` (для затронутых parity-доменов)
3. `python -m pytest -o addopts= v5/tests/plugin_integration -q`
4. `python v5/topology-tools/compile-topology.py --topology v5/topology/topology.yaml --strict-model-lock --secrets-mode passthrough`
5. `python v5/topology-tools/verify-framework-lock.py --strict`

---

## 6. Done Criteria for Preparation Phase

1. Inventory готов и покрывает все active plugins.
2. Violation map подтвержден и приоритизирован.
3. Batch order согласован (A -> B -> C -> D).
4. Для каждого batch есть ожидаемые touchpoints (paths/tests/gates).
5. Реализационная команда может начинать refactor без дополнительных ADR-уточнений.

---

## 7. Extended Work Packages (Boundary Enforcement)

Добавлены для адресации выявленных проблем при аудите (2026-03-22).

### WP6: Instance Literal Isolation

**Цель:** Убрать все instance-specific литералы из object-level кода.

**Execution result (done):**

1. Hardcoded endpoints removed from object terraform generators.
2. API endpoint resolution moved to config/projection-first flow.
3. CI enforcement added in:
   - `v5/tests/plugin_contract/test_plugin_level_boundaries.py::test_object_plugin_python_files_do_not_hardcode_private_or_local_url_hosts`

**Exit criteria:** completed.

---

### WP7: Cross-Object Import Prohibition

**Цель:** Запретить импорты между object modules.

**Execution result (done):**

1. AST-based cross-object import guard added in:
   - `v5/tests/plugin_contract/test_plugin_level_boundaries.py::test_object_modules_do_not_cross_import_other_object_modules`
2. Current object plugin tree passes contract checks.

**Exit criteria:** completed.

---

### WP8: Dynamic Object Module Discovery

**Цель:** Убрать hardcoded object paths из framework кода.

**Execution result (done):**

1. `object_projection_loader.py` switched to filesystem discovery + `@lru_cache`.
2. Discovery behavior covered by:
   - `v5/tests/plugin_integration/test_object_projection_loader.py`.

**Exit criteria:** completed.

---

### WP9: Capability-Template Externalization

**Цель:** Вынести capability→template mappings в config.

**Execution result (done):**

1. Added `capability_templates` config section to `mikrotik/plugins.yaml`.
2. Refactored `terraform_mikrotik_generator.py`:
   - Added `_get_capability_templates(capabilities, ctx)` method;
   - Added `_DEFAULT_CAPABILITY_TEMPLATES` fallback for backwards compatibility;
   - Removed hardcoded `if has_qos/wireguard/containers` patterns.
3. Created `v5/tests/plugin_contract/test_capability_template_config.py` with 3 tests:
   - `test_generators_do_not_hardcode_capability_template_mappings`
   - `test_generators_have_capability_templates_in_config_or_fallback`
   - `test_capability_templates_schema_in_manifests`

**Exit criteria:** completed.

---

### WP10: Projection Architecture Consolidation

**Цель:** Чёткие ownership boundaries для projections.

**Execution result (done):**

1. Created `v5/tests/plugin_contract/test_projection_ownership_boundaries.py` with 6 tests:
   - `test_core_projections_are_cross_object`
   - `test_object_projections_only_reference_own_object`
   - `test_shared_projections_are_in_shared_module`
   - `test_projection_modules_import_only_from_allowed_sources`
   - `test_projection_ownership_inventory`
   - `test_no_projection_duplication_across_levels`

2. Projection ownership verified:
   - Core: `build_ansible_projection`, `build_docs_projection` (in tools/generators/projections.py)
   - Object: `build_mikrotik_projection`, `build_proxmox_projection` (in object-modules/*/plugins/projections.py)
   - Shared: `build_bootstrap_projection`, `build_bootstrap_typed` (in _shared/plugins/bootstrap_projections.py)
   - Core helpers: `projection_core.py` (low-level utilities)

3. All projection modules pass ownership boundary tests.

**Exit criteria:** completed.

---

## 8. Updated Batch Order

Рекомендуемый порядок выполнения:

1. **Batch A**: Core Import Hygiene (WP1-WP5 completed)
2. **Batch B**: Instance Isolation (WP6 completed)
3. **Batch C**: Cross-Object Boundaries (WP7 completed)
4. **Batch D**: Dynamic Discovery (WP8 completed)
5. **Batch E**: Capability Externalization (WP9 completed)
6. **Batch F**: Projection Consolidation (WP10 completed)

После каждого batch:
- Regenerate framework lock;
- Run full test suite;
- Capture cutover evidence.

**All batches completed (2026-03-22).**

---

## 9. Extended Mandatory Gates

Финальные release gates:

1. `python -m pytest -o addopts= v5/tests/plugin_contract/test_plugin_level_boundaries.py -q`
2. `python -m pytest -o addopts= v5/tests/plugin_integration/test_object_projection_loader.py -q`
3. `python -m pytest -o addopts= v5/tests/plugin_integration -q`
4. `python -m pytest -o addopts= v5/tests/plugin_contract/test_capability_template_config.py -q` (new)
5. `python -m pytest -o addopts= v5/tests/plugin_contract/test_projection_ownership_boundaries.py -q` (new)

Все gates должны быть green перед release.

---

## 10. Extended Done Criteria

К существующим критериям добавляются:

6. WP6: No instance literals in object plugins. (done)
7. WP7: No cross-object imports. (done)
8. WP8: Object discovery is dynamic. (done)
9. WP9: Capability templates in config. (done)
10. WP10: Projection ownership boundaries documented and tested. (done)

**All criteria satisfied (2026-03-22).**
