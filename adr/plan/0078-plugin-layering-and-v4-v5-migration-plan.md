# Plugin Layering + v4->v5 Migration Plan

**Date:** 2026-03-22  
**Status:** Active  
**Related ADRs:** 0063, 0069, 0074, 0078

---

## 1. Objective

Привести runtime и плагины к новым правилам 4 уровней:

1. global/core
2. class
3. object
4. instance

и завершить перенос оставшихся v4 validator/generator потоков в v5 plugin-first архитектуру без архитектурных утечек между уровнями.

---

## 2. Current State (Audit Snapshot)

### 2.1 v5

1. Базовый контракт уровней уже формализован и покрыт тестами (`v5/tests/plugin_contract/test_plugin_level_boundaries.py`).
2. В core plugins есть остаточные `sys.path.insert(...)` (compilers/validators/generators).
3. `v5/topology/object-modules/network/plugins/port_occupancy_validator.py` не зарегистрирован и использует legacy API.
4. В `object_network.validator_json.ethernet_cable_endpoints` есть жёсткие object-to-object зависимости:
   - `object_mikrotik.validator_json.router_ports`
   - `object_glinet.validator_json.router_ports`

### 2.2 v4 -> v5 Gap

Только часть top-level toolchain уже имеет v5 аналоги (`compile-topology.py`, `assemble-ansible-runtime.py`, `check-capability-contract.py`).  
Основные legacy зоны миграции:

1. `v4/topology-tools/scripts/validators/checks/*.py` (foundation/governance/network/references/storage)
2. `v4/topology-tools/scripts/generators/docs/generator.py`
3. v4 orchestration wrappers (`regenerate-all.py`, `validate-topology.py`, `generate-*`, `assemble-*`)

---

## 3. Scope

### In Scope

1. Приведение v5 plugin runtime к kernel-owned import policy.
2. Устранение кросс-уровневых утечек и жёсткой vendor/object сцепки в плагинах.
3. Поэтапный перенос v4 validator/generator логики в v5 plugins.
4. Обновление orchestration/task-цепочек после parity.

### Out of Scope

1. Изменение доменной модели topology.
2. Изменение output-форматов Terraform/Ansible без отдельного ADR.
3. Изменение секретной модели ADR0072.

---

## 4. Work Plan

## Wave A - Core Import Hygiene

**Goal:** убрать `sys.path.insert` из core plugins, импортами управляет только kernel.

Tasks:

- [x] Удалить `sys.path.insert(...)` из `v5/topology-tools/plugins/compilers/*.py`.
- [x] Удалить `sys.path.insert(...)` из `v5/topology-tools/plugins/validators/*.py`.
- [x] Удалить `sys.path.insert(...)` из `v5/topology-tools/plugins/generators/*.py`.
- [x] Убедиться, что загрузка через `PluginRegistry` покрывает все импорты.

Verification:

1. `rg "sys.path.insert\\(" v5/topology-tools/plugins v5/topology/class-modules v5/topology/object-modules`
2. `python -m pytest -o addopts= v5/tests/test_plugin_registry.py v5/tests/plugin_contract/test_manifest.py -q`

Exit:

1. Нет `sys.path.insert(...)` в plugin code.
2. Plugin registry и manifest tests green.

---

## Wave B - Network Validator Boundary Refactor

**Goal:** убрать жёсткие зависимости object->object для network валидатора.

Tasks:

- [x] Вынести абстрактный контракт ethernet-port inventory в class/global plugin (например class.router contract или base validator contract).
- [x] Переподключить `object_network.validator_json.ethernet_cable_endpoints` на контракт верхнего уровня вместо конкретных object plugins.
- [x] Сохранить текущую диагностическую семантику (`E7304-E7308`).

Target files:

1. `v5/topology/object-modules/network/plugins.yaml`
2. `v5/topology/object-modules/network/plugins/ethernet_cable_endpoint_validator.py`
3. `v5/topology/class-modules/router/plugins.yaml` и/или `v5/topology-tools/plugins/plugins.yaml`

Verification:

1. `python -m pytest -o addopts= v5/tests/plugin_integration/test_tuc0001_router_data_link.py -q`
2. `python -m pytest -o addopts= v5/tests/plugin_contract/test_plugin_level_boundaries.py -q`

Exit:

1. Network validator не зависит от object-vendor plugin IDs.
2. TUC0001 regression tests green (за исключением внешних lock integrity факторов).

---

## Wave C - Legacy Orphan Plugin Cleanup

**Goal:** закрыть судьбу `port_occupancy_validator.py`.

Tasks:

- [x] Выбрать один вариант:
- [x] Вариант 1: удалить файл как неиспользуемый.
- [ ] Вариант 2: мигрировать на `ValidatorJsonPlugin`, зарегистрировать в `v5/topology/object-modules/network/plugins.yaml`, покрыть тестами.

Verification:

1. `rg "PortOccupancyValidator|port_occupancy" v5/topology v5/tests`
2. `python -m pytest -o addopts= v5/tests/plugin_integration/test_tuc0001_router_data_link.py -q`

Exit:

1. Нет legacy plugin API в v5 active path.

---

## Wave D - v4 Validators -> v5 Plugins

**Goal:** перенести semantic checks из `v4/scripts/validators/checks` в v5 staged plugins.

Migration batches:

1. Foundation/governance checks
2. Network checks
3. References checks
4. Storage checks

Tasks:

- [x] Создать mapping: `v4 check_*` -> `v5 plugin id + stage`.
- [ ] Портировать логику с минимальным поведением drift.
- [ ] Добавить contract/integration tests в `v5/tests/plugin_integration`.
- [ ] Зафиксировать deprecation legacy v4 checks.

Verification:

1. `python -m pytest -o addopts= v5/tests/plugin_integration/test_reference_validator.py -q`
2. `python -m pytest -o addopts= v5/tests/plugin_integration/test_l1_power_source_refs.py -q`
3. `python -m pytest -o addopts= v5/tests/plugin_integration/test_module_manifest_discovery.py -q`

Exit:

1. Эквивалентный coverage для ключевых v4 check domains в v5 plugins.
2. Нет новых cross-level violations.

---

## Wave E - v4 Generators -> v5 Plugins

**Goal:** закрыть legacy generator wrappers и довести генерацию до полного plugin-first.

Priority order:

1. Docs generator (`v4/scripts/generators/docs/generator.py`) -> `base.generator.docs` (core)
2. Legacy orchestration wrappers (`generate-*`, `regenerate-all.py`) -> task/lane на базе plugin pipeline

Tasks:

- [ ] Спроектировать projection contract для docs generation.
- [ ] Реализовать v5 docs generator plugin + templates.
- [ ] Добавить integration tests для docs artifacts.
- [ ] Обновить build/release pipelines под новый plugin.

Verification:

1. `python -m pytest -o addopts= v5/tests/plugin_integration -q`
2. `python v5/topology-tools/compile-topology.py --topology v5/topology/topology.yaml --strict-model-lock --secrets-mode passthrough`

Exit:

1. Docs generation доступна в v5 plugin pipeline.
2. Legacy generator wrappers не требуются для v5 lane.

---

## Wave F - Orchestration and Task Cleanup

**Goal:** удалить operational зависимость от v4 после parity closure.

Tasks:

- [ ] Обновить `taskfiles/validate.yml` (убрать v4-only quality hooks из v5 пути).
- [ ] Обновить `taskfiles/test.yml` (v4 fixture matrix отдельно, не блокирует v5 release lane).
- [ ] Обновить `v5/scripts/orchestration/lane.py` текст и цепочки под фактический generator-enabled runtime.

Verification:

1. `task validate:v5`
2. `task framework:release-preflight`

Exit:

1. v5 lane выполняется без обязательного вызова v4 tooling.

---

## 5. Acceptance Criteria

Все пункты обязательны:

1. v5 plugin code не содержит `sys.path.insert(...)`.
2. Нет object-to-object hard dependency там, где должен быть class/core контракт.
3. Нет активных legacy plugin API модулей в v5 runtime path.
4. Ключевые v4 semantic checks покрыты v5 plugins + tests.
5. v5 orchestration не зависит от v4 для стандартного validate/build/release пути.
6. `test_plugin_level_boundaries.py` остаётся green и расширяется по мере миграции.

---

## 6. Risks and Mitigations

1. **Риск:** функциональный drift при переносе v4 проверок.  
   **Контроль:** перенос батчами + parity tests на фикстурах.
2. **Риск:** регрессия в генераторах/шаблонах.  
   **Контроль:** snapshot tests + release preflight.
3. **Риск:** lock/integrity noise маскирует реальные регрессии.  
   **Контроль:** разделять pipeline failures на архитектурные и environment/lock категории.

---

## 7. Tracking

Рекомендуемый execution order:

1. Wave A
2. Wave C
3. Wave B
4. Wave D
5. Wave E
6. Wave F

После закрытия Wave F обновить статус плана на `Completed` и синхронизировать связанные ADR implementation status sections.

### Progress Snapshot (2026-03-22)

Completed:

1. **Wave A**: removed `sys.path.insert(...)` from v5 plugin code (compilers/validators/generators), registry/manifest tests green.
2. **Wave C**: removed legacy orphan `port_occupancy_validator.py` from active path.
3. **Wave B**: introduced `base.validator.ethernet_port_inventory`; rewired `object_network.validator_json.ethernet_cable_endpoints` from object-vendor hard deps to upper-level contract.

Wave D in progress:

1. Added mapping document: `adr/plan/0078-wave-d-v4-validator-mapping.md`.
2. Added D1 validators:
   - `base.validator.governance_contract`
   - `base.validator.foundation_layout`
   - `base.validator.foundation_include_contract`
   - `base.validator.foundation_device_taxonomy`
3. Added D2 validators (partial v4 parity):
   - `base.validator.network_ip_overlap`
   - `base.validator.single_active_os`
   - `base.validator.network_reserved_ranges`
   - `base.validator.network_trust_zone_firewall_refs`
   - `base.validator.network_firewall_addressability`
   - `base.validator.runtime_target_os_binding`
   - `base.validator.storage_l3_refs`
   - `base.validator.network_ip_allocation_host_os_refs`
   - `base.validator.network_vlan_zone_consistency`
   - `base.validator.network_core_refs`
   - `base.validator.network_vlan_tags`
   - `base.validator.network_mtu_consistency`
   - `base.validator.service_runtime_refs`
   - `base.validator.network_runtime_reachability`
   - `base.validator.service_dependency_refs`
4. Started D4 storage parity validators:
   - `base.validator.storage_device_taxonomy`
   - `base.validator.storage_media_inventory`
   - expanded `base.validator.storage_l3_refs` (partition/vg/lv/filesystem/mount/storage_endpoint refs)
   - added `storage_l3_refs` parity checks for `infer_from.*` consistency and data-asset backup policy linkage
   - added targeted warning-parity fixtures for `infer_from`/backup-policy edge semantics
5. Added D3 references thin-wrappers:
   - `base.validator.dns_refs`
   - `base.validator.certificate_refs`
   - `base.validator.backup_refs`
   - `base.validator.security_policy_refs`
6. Added draft deprecation matrix:
   - `adr/plan/0078-v4-validator-deprecation-matrix.md`
7. Added v4/v5 side-by-side parity fixture:
   - `v5/tests/plugin_integration/test_storage_l3_v4_v5_warning_parity.py`
   - `v5/tests/plugin_integration/test_service_refs_v4_v5_parity.py`
