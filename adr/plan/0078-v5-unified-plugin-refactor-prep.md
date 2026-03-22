# ADR0078: v5 Unified Plugin Refactor Preparation

**Date:** 2026-03-22
**Status:** Ready for execution
**Amended:** 2026-03-22 (WP6-WP10 added for boundary enforcement)
**Related:** `adr/0078-object-module-local-template-layout.md`, `adr/plan/0078-plugin-layering-and-v4-v5-migration-plan.md`

---

## 1. Purpose

Подготовить v5 рефакторинг под единые правила для всех типов плагинов:

1. compilers;
2. validators;
3. generators.

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
   - family (`compiler|validator|generator`);
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

### 3.1 Known Violations (2026-03-22 Audit)

| Violation Type | Location | Details |
|----------------|----------|---------|
| Instance literal | `mikrotik/plugins/terraform_mikrotik_generator.py:64` | Hardcoded IP `192.168.88.1` |
| Instance literal | `proxmox/plugins/terraform_proxmox_generator.py:65` | Hardcoded hostname `proxmox.local` |
| Hardcoded paths | `object_projection_loader.py:14-18` | Static dict `OBJECT_PROJECTION_PATHS` |
| Capability coupling | `terraform_mikrotik_generator.py:106-111` | Hardcoded `if has_qos/wireguard/containers` |
| Missing test | `test_plugin_level_boundaries.py` | No cross-object import scan |

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

**Scope:**
- Сканировать все `object-modules/*/plugins/*.py` на IP-адреса и hostnames;
- Рефакторить генераторы на получение данных из projection/config;
- Добавить CI enforcement.

**Tasks:**

1. Создать `v5/tests/plugin_contract/test_instance_literal_isolation.py`:
   ```python
   IP_PATTERN = re.compile(r'\b(?:192\.168|10\.0|172\.(?:1[6-9]|2\d|3[01]))\.\d{1,3}\.\d{1,3}\b')
   HOSTNAME_PATTERN = re.compile(r'\b[a-z][\w-]*\.(local|home|lan|internal)\b', re.I)
   ```

2. Рефакторить `terraform_mikrotik_generator.py`:
   - Удалить `mikrotik_host = "https://192.168.88.1:8443"`
   - Добавить `_resolve_api_url(projection, ctx)` method

3. Рефакторить `terraform_proxmox_generator.py`:
   - Удалить `proxmox_api_url = "https://proxmox.local:8006/api2/json"`
   - Добавить `_resolve_api_url(projection, ctx)` method

4. Добавить `api_host`, `api_port` в config schema генераторов.

**Exit criteria:**
- `test_instance_literal_isolation.py` проходит;
- Нет hardcoded IPs/hostnames в object plugins.

---

### WP7: Cross-Object Import Prohibition

**Цель:** Запретить импорты между object modules.

**Tasks:**

1. Добавить тест `test_object_modules_do_not_cross_import()` в `test_plugin_level_boundaries.py`:
   ```python
   # Scan for patterns like:
   # from topology.object_modules.proxmox import ...
   # inside mikrotik module
   ```

2. Проверить текущее состояние и зафиксировать violations.

3. Документировать allowed vs prohibited import patterns в `PLUGIN_AUTHORING.md`.

**Exit criteria:**
- Тест добавлен и проходит;
- Документация обновлена.

---

### WP8: Dynamic Object Module Discovery

**Цель:** Убрать hardcoded object paths из framework кода.

**Tasks:**

1. Рефакторить `v5/topology-tools/plugins/generators/object_projection_loader.py`:
   - Заменить `OBJECT_PROJECTION_PATHS` dict на `discover_object_projection_modules()`;
   - Добавить `@lru_cache` для performance.

2. Создать `v5/tests/plugin_contract/test_dynamic_object_discovery.py`:
   - Проверить что discovery находит все ожидаемые modules;
   - Проверить отсутствие hardcoded paths.

**Exit criteria:**
- Нет статических object ID mappings;
- Discovery test проходит;
- Добавление нового object module не требует изменения framework.

---

### WP9: Capability-Template Externalization

**Цель:** Вынести capability→template mappings в config.

**Tasks:**

1. Добавить `capability_templates` секцию в `plugins.yaml` для mikrotik/proxmox.

2. Рефакторить генераторы:
   - Убрать `if has_qos: templates["qos.tf"] = ...` patterns;
   - Добавить `_get_capability_templates(projection, ctx)` method.

3. Создать `v5/tests/plugin_contract/test_capability_template_config.py`:
   - Проверить отсутствие hardcoded capability checks в генераторах.

**Exit criteria:**
- Capability mappings в config;
- Генераторы читают из config;
- Test проходит.

---

### WP10: Projection Architecture Consolidation

**Цель:** Чёткие ownership boundaries для projections.

**Tasks:**

1. Документировать projection ownership:
   - Core: `ansible_projection`, `docs_projection`, `effective_model_projection`;
   - Object: `mikrotik_projection`, `proxmox_projection`;
   - Shared: `bootstrap_projections`.

2. Проверить нет ли object-specific логики в core projections.

3. Добавить `v5/tests/plugin_contract/test_projection_ownership_boundaries.py`.

4. Консолидировать shared utilities в `_shared/plugins/projection_helpers.py`.

**Exit criteria:**
- Ownership задокументирован;
- Test проходит;
- Shared helpers в одном месте.

---

## 8. Updated Batch Order

Рекомендуемый порядок выполнения:

1. **Batch A**: Core Import Hygiene (WP1-WP5 completed)
2. **Batch B**: Instance Isolation (WP6)
3. **Batch C**: Cross-Object Boundaries (WP7)
4. **Batch D**: Dynamic Discovery (WP8)
5. **Batch E**: Capability Externalization (WP9)
6. **Batch F**: Projection Consolidation (WP10)

После каждого batch:
- Regenerate framework lock;
- Run full test suite;
- Capture cutover evidence.

---

## 9. Extended Mandatory Gates

Для WP6-WP10 добавляются gates:

1. `python -m pytest v5/tests/plugin_contract/test_instance_literal_isolation.py -q`
2. `python -m pytest v5/tests/plugin_contract/test_plugin_level_boundaries.py::test_object_modules_do_not_cross_import -q`
3. `python -m pytest v5/tests/plugin_contract/test_dynamic_object_discovery.py -q`
4. `python -m pytest v5/tests/plugin_contract/test_capability_template_config.py -q`
5. `python -m pytest v5/tests/plugin_contract/test_projection_ownership_boundaries.py -q`

Все gates должны быть green перед release.

---

## 10. Extended Done Criteria

К существующим критериям добавляются:

6. WP6: No instance literals in object plugins.
7. WP7: No cross-object imports.
8. WP8: Object discovery is dynamic.
9. WP9: Capability templates in config.
10. WP10: Projection ownership boundaries documented and tested.
