# Plugin Layering + v4->v5 Migration Plan

**Date:** 2026-03-22
**Status:** Completed (Waves A-F + WP6-WP10 completed)
**Related ADRs:** 0063, 0069, 0074, 0078, 0080
**See also:** `adr/plan/0078-v5-unified-plugin-refactor-prep.md` (WP6-WP10)
**Cutover checklist:** `adr/plan/0078-cutover-checklist.md`

---

## Layout Note (2026-03-27)

После завершения миграции репозиторный layout зафиксирован так:

1. Legacy `v4` хранится в `archive/v4` и используется как эталон для сверок/parity.
2. Историческое содержимое `v5` перенесено в корень репозитория (`topology`, `topology-tools`, `tests`, `scripts`, `taskfiles` и т.д.).
3. Проверки v4/v5 выполняются с опорой на `archive/v4`; сборка v4 должна оставаться рабочей.
4. Перенос `v5` в корень был выполнен преждевременно, но принят как целевой layout: дальнейшая разработка продолжается в корневой структуре.

---

## ADR0080 Alignment (2026-03-27)

Этот план закрывает миграцию слоёв/плагинов (ADR0078 scope). Дальнейшее развитие runtime/pipeline выполняется по ADR0080.

Правила синхронизации с ADR0080:

1. Все исторические ссылки вида `v5/...` в этом документе трактуются как корневые пути репозитория.
2. Эталон legacy-сверок: только `archive/v4`; для регрессионной сверки допускается запуск v4 сборки из `archive/v4`.
3. Активная разработка и новые изменения выполняются только в root layout (без возврата к корневым папкам `v4/` и `v5/`).
4. Контрольные гейты должны включать:
   - `task validate:workspace-layout` (запрет legacy root директорий),
   - `task framework:audit-entrypoints` (strict runtime audit),
   - `task acceptance:tests-all` / `task acceptance:test` для TUC acceptance-checks.
5. Для lifecycle/stage-phase/data-bus изменений использовать планы и чеклисты ADR0080:
   - `adr/0080-analysis/IMPLEMENTATION-PLAN.md`
   - `adr/0080-analysis/CUTOVER-PLAN.md`
   - `adr/0080-analysis/CUTOVER-CHECKLIST.md`
6. Нормативный набор семейств плагинов для post-cutover runtime:
   - `discoverers`, `compilers`, `validators`, `generators`, `assemblers`, `builders`.
   - Runtime lifecycle включает 6 stage: `discover -> compile -> validate -> generate -> assemble -> build`.
   - `discover` stage выполняется discovery plugins (`base.discover.*`) внутри семейства `discoverers`.
   - Stage affinity:
   - `discover -> discoverers (discoverer kind)`
   - `compile -> compilers`
   - `validate -> validators`
   - `generate -> generators`
   - `assemble -> assemblers`
   - `build -> builders`
7. Для каждого legacy v4 plugin/check обязателен миграционный анализ перед переносом:
   - определить целевую стадию (`discover|compile|validate|generate|assemble|build`),
   - зафиксировать решение в mapping/плане,
   - переносить в v5 только после явного stage assignment.
8. Этот документ зафиксирован как completed migration baseline; выполнение оставшихся cutover шагов ведется по `adr/plan/0078-cutover-checklist.md`.

---

## 1. Objective

Привести runtime и плагины к новым правилам 4 уровней для всех семейств плагинов:

- discoverers;
- compilers;
- validators;
- generators;
- assemblers;
- builders;

и закрепить единые правила архитектуры:

1. global/core
2. class
3. object
4. instance

и завершить перенос оставшихся v4 validator/generator потоков в v5 plugin-first архитектуру без архитектурных утечек между уровнями.
Post-cutover расширение lifecycle-доменов (`assemble`, `build`) закрепляется через типы `assembler` и `builder` по ADR0080.

Единый норматив:

1. Плагин уровня `N` вызывает только интерфейсы, имплементируемые уровнем `N+1`.
2. На class-level запрещены object/instance-specific зависимости.
3. На object-level запрещены instance-specific зависимости.
4. Глобальные плагины без class/object-специфики переносятся в core/global уровень.
5. Глобальные плагины управляют специфичными через интерфейсы/паттерны.
6. Дизайн всех плагинов соответствует SOLID.

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
5. Синхронизация migration-plan с расширением типов плагинов `assembler`/`builder` для assemble/build стадий.

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
- [x] Вариант 2 (not selected): мигрировать на `ValidatorJsonPlugin`, зарегистрировать в `topology/object-modules/network/plugins.yaml`, покрыть тестами.

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
- [x] Портировать логику с минимальным поведением drift.
- [x] Добавить contract/integration tests в `v5/tests/plugin_integration`.
- [x] Зафиксировать deprecation legacy v4 checks.
- [x] Для каждого перенесённого v4 check/plugin выполнить явный stage-анализ и закрепить stage assignment в mapping.

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

- [x] Спроектировать projection contract для docs generation.
- [x] Реализовать v5 docs generator plugin + templates.
- [x] Добавить integration tests для docs artifacts.
- [x] Обновить build/release pipelines под новый plugin.

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

- [x] Обновить `taskfiles/validate.yml` (убрать v4-only quality hooks из v5 пути).
- [x] Обновить `taskfiles/test.yml` (v4 fixture matrix отдельно, не блокирует v5 release lane).
- [x] Обновить `v5/scripts/orchestration/lane.py` текст и цепочки под фактический generator-enabled runtime.

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
7. Для post-cutover структуры отсутствуют корневые каталоги `v4/` и `v5/` (legacy хранится в `archive/v4`).
8. v4 baseline-сборка из `archive/v4` остаётся воспроизводимой для parity/регрессионной сверки.
9. Все новые pipeline/lifecycle изменения после закрытия этого плана ведутся через ADR0080 артефакты.
10. Runtime/migrations учитывают полный набор из 6 семейств плагинов (`discoverers`, `compilers`, `validators`, `generators`, `assemblers`, `builders`) и полный 6-stage lifecycle (`discover -> compile -> validate -> generate -> assemble -> build`), где `discover` реализуется discovery plugins (`base.discover.*`) в `discoverers`.

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

Wave D completed:

1. Added mapping document: `adr/plan/0078-wave-d-v4-validator-mapping.md`.
2. Added D1 validators:
   - `base.validator.governance_contract`
   - `base.validator.foundation_layout`
   - `base.validator.foundation_include_contract`
   - `base.validator.foundation_device_taxonomy`
   - extended `base.validator.governance_contract` with defaults refs parity checks (`meta.defaults.refs.security_policy_ref`, `meta.defaults.refs.network_manager_device_ref`)
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
   - extended `base.validator.network_ip_overlap` with network-scoped duplicate allocation errors (`ip_allocations`) plus global overlap warnings parity
   - extended `base.validator.network_reserved_ranges` with object/extension/top-level payload parity and `cidr=dhcp` skip semantics
   - extended `base.validator.network_ip_allocation_host_os_refs` with required-ref parity (`host_os_ref|device_ref`), deprecation warning suggestion parity, and object/extension/top-level payload support
   - extended `base.validator.network_runtime_reachability` with top-level payload parity and active-only host_os reachability alignment
   - extended `base.validator.network_firewall_addressability` with top-level payload parity for network/policy refs
   - extended `base.validator.network_core_refs` with object/extension/top-level payload parity for core VLAN/bridge refs
   - extended `base.validator.service_runtime_refs` with v4-aligned legacy/runtime contracts parity:
     - legacy service fields deprecation warnings (`container`, `native`, `container_image`, `config.docker.host_ip`, `ip`)
     - https certificate intent warning (`security.ssl_certificate`)
     - runtime + legacy refs warning parity
     - legacy refs existence checks (`device_ref`, `vm_ref`, `lxc_ref`, `network_ref`, `trust_zone_ref`)
     - runtime target device host OS inventory parity (active/mapped/modeled statuses)
     - docker/baremetal host metadata checks when `capabilities` / `host_type` are declared
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
   - `base.validator.host_os_refs`
   - extended `base.validator.host_os_refs` with host_os architecture/device parity and installation/root-storage mount-device consistency checks
   - extended `base.validator.host_os_refs` with host_type/capabilities compatibility and canonical architecture checks (extension-level parity)
   - extended `base.validator.host_os_refs` with legacy top-level field parity (architecture/host_type/capabilities/installation paths without `extensions`)
   - extended `base.validator.vm_refs` / `base.validator.lxc_refs` with host_os-device binding parity (`os_refs` membership, host_os_ref requirement for multi-active bindings)
   - extended `base.validator.vm_refs` / `base.validator.lxc_refs` with resolved-host capability parity, bridge refs parity, storage endpoint platform parity, and guest/template/host architecture parity checks
   - extended `base.validator.vm_refs` / `base.validator.lxc_refs` with legacy top-level field parity (resolved host capabilities, storage endpoint platform, architecture/deprecation paths without `extensions`)
   - extended `base.validator.lxc_refs` with legacy field deprecation warnings parity (`type`, `role`, `resources`, `ansible.vars` app keys)
   - added legacy top-level field parity fallback for host_os/vm/lxc refs validators (non-extension paths for `architecture`, `host_type`, `capabilities`, `installation`, `platform`, and legacy LXC deprecation fields)
6. Added deprecation matrix:
   - `adr/plan/0078-v4-validator-deprecation-matrix.md`
7. Added v4/v5 side-by-side parity fixture:
   - `v5/tests/plugin_integration/test_storage_l3_v4_v5_warning_parity.py`
   - `v5/tests/plugin_integration/test_service_refs_v4_v5_parity.py`
   - `v5/tests/plugin_integration/test_network_refs_v4_v5_parity.py`
   - `v5/tests/plugin_integration/test_network_ip_overlap_v4_v5_parity.py`
   - `v5/tests/plugin_integration/test_network_reserved_ranges_v4_v5_parity.py`
   - `v5/tests/plugin_integration/test_network_ip_allocation_host_os_refs_v4_v5_parity.py`
   - `v5/tests/plugin_integration/test_governance_v4_v5_parity.py`
   - `v5/tests/plugin_integration/test_host_os_refs_v4_v5_parity.py`
   - `v5/tests/plugin_integration/test_vm_lxc_host_os_v4_v5_parity.py`
8. Added dedicated parity gate tasking for staged cutover:
   - `task test:parity-v4-v5`
   - `task ci:topology-parity-v4-v5`
   - wired into `task ci:local-with-legacy`
9. Updated cutover readiness reporting:
   - `v5/topology-tools/cutover-readiness-report.py` non-quick mode now includes `pytest_v4_v5_parity` gate
10. Executed cutover readiness gates after parity integration:
   - quick mode: PASS
   - non-quick mode: PASS (`verify_framework_lock`, `rehearse_rollback`, `validate_compatibility_matrix`, `audit_strict_entrypoints`, `pytest_v4_v5_parity`, `pytest_v5`, `lane_validate_v5`)

Wave E completed:

1. Added docs projection contract + core generator:
   - `base.generator.docs`
   - `v5/topology-tools/plugins/generators/projections.py:build_docs_projection`
2. Added docs templates (projection-first baseline):
   - `v5/topology-tools/templates/docs/overview.md.j2`
   - `v5/topology-tools/templates/docs/devices.md.j2`
   - `v5/topology-tools/templates/docs/services.md.j2`
3. Added integration coverage for docs generator:
   - `v5/tests/plugin_integration/test_docs_generator.py`
4. Updated `build-v5` orchestration message/contract to reflect generator-enabled runtime.

Wave F completed:

1. Updated `taskfiles/validate.yml`:
   - default `quality` path is now v5-focused (`quality-v5`)
   - legacy v4 static hooks moved to `quality-legacy-v4`
2. Updated `taskfiles/test.yml`:
   - default `test:all` runs v5 tests
   - legacy-inclusive matrix moved to `test:all-with-legacy`
3. Updated `taskfiles/ci.yml`:
   - `ci:local` no longer blocks on v4 fixture/test lanes
   - `ci:local-with-legacy` preserves full legacy regression path
4. Updated `v5/scripts/orchestration/lane.py` and `taskfiles/build.yml` labels:
   - v5 lane marked default
   - v4 lanes explicitly marked legacy compatibility.

Closure evidence (2026-03-22):

1. `python -m pytest -o addopts= v5/tests/plugin_integration -q` -> PASS (`449 passed`).
2. `task test:parity-v4-v5` -> PASS (`37 passed`).
3. `python topology-tools/cutover-readiness-report.py --output build/diagnostics/cutover-readiness-full-latest.json` -> PASS (all non-quick gates green).

Post-cutover hardening (2026-03-27):

1. Added manifest contract guard:
   - `tests/plugin_contract/test_manifest.py::test_plugin_kind_stage_affinity_across_discovered_manifests`
   - Enforces stage affinity by kind across all discovered manifests:
     - `discoverer -> discover`
     - `compiler -> compile`
     - `validator_yaml|validator_json -> validate`
     - `generator -> generate`
     - `assembler -> assemble`
     - `builder -> build`
2. Framework release-focused lane remains green with the new guard:
   - `task framework:release-tests` -> PASS (`157 passed`).
3. Runtime now hard-rejects kind/stage affinity violations at manifest load:
   - `topology-tools/kernel/plugin_registry.py::_validate_spec` enforces `KIND_STAGE_AFFINITY`.
   - Contract test: `tests/plugin_contract/test_manifest.py::test_manifest_rejects_kind_stage_affinity_violation`.
   - Updated framework release-focused lane snapshot: `task framework:release-tests` -> PASS (`158 passed`).
4. Agent-instruction contract sync hardened for root-layout/post-cutover policy:
   - Updated and synchronized `CLAUDE.md` and `.github/copilot-instructions.md` with current root structure
     (`class-modules`, `object-modules`, `kernel`) and current build lane command.
   - Added guard test: `tests/test_agent_instruction_sync.py`.
   - Wired guard into framework release lane: `task framework:release-tests`.
   - Updated framework release-focused lane snapshot: `task framework:release-tests` -> PASS (`160 passed`).
5. Extended agent-instruction sync to Codex policy sources:
   - Synchronized `.codex/AGENTS.md` and `.codex/rules/tech-lead-architect.md` wording with CLAUDE/Copilot
     for plugin families, 6-stage lifecycle, and stage-affinity rules.
   - Extended `tests/test_agent_instruction_sync.py` coverage to validate Claude + Copilot + Codex instruction files.
   - Updated framework release-focused lane snapshot: `task framework:release-tests` -> PASS (`161 passed`).

---

## 8. Phase 6-7: Boundary Enforcement (2026-03-22)

**Status:** Completed (WP6-WP10)

After code audit, additional violations were identified that require new waves:

### Known Violations

| Type | Location | Issue | State |
|------|----------|-------|-------|
| Instance literal | `mikrotik/terraform_mikrotik_generator.py` | Hardcoded endpoint removed | Resolved |
| Instance literal | `proxmox/terraform_proxmox_generator.py` | Hardcoded endpoint removed | Resolved |
| Hardcoded paths | `object_projection_loader.py` | Static mapping replaced by discovery | Resolved |
| Missing enforcement | `test_plugin_level_boundaries.py` | Cross-object import scan added | Resolved |
| Capability coupling | `terraform_mikrotik_generator.py` | Capability mapping externalized to manifest config + contract tests | Resolved |

### New Work Packages

Detailed implementation tracked in `adr/plan/0078-v5-unified-plugin-refactor-prep.md`:

1. **WP6: Instance Literal Isolation** — remove hardcoded IPs/hostnames from generators
2. **WP7: Cross-Object Import Prohibition** — add enforcement test
3. **WP8: Dynamic Object Discovery** — replace hardcoded module paths
4. **WP9: Capability-Template Externalization** — move mappings to config
5. **WP10: Projection Architecture Consolidation** — document ownership boundaries

### Execution Order

```
Batch B: WP6 (Instance Isolation) - completed
    ↓
Batch C: WP7 (Cross-Object Boundaries) - completed
    ↓
Batch D: WP8 (Dynamic Discovery) - completed
    ↓
Batch E: WP9 (Capability Externalization) - completed
    ↓
Batch F: WP10 (Projection Consolidation) - completed
```

### New Tests Required

1. `v5/tests/plugin_contract/test_plugin_level_boundaries.py::test_object_plugin_python_files_do_not_hardcode_private_or_local_url_hosts`
2. `v5/tests/plugin_contract/test_plugin_level_boundaries.py::test_object_modules_do_not_cross_import_other_object_modules`
3. `v5/tests/plugin_integration/test_object_projection_loader.py`
4. `v5/tests/plugin_contract/test_capability_template_config.py`
5. `v5/tests/plugin_contract/test_projection_ownership_boundaries.py`

### Extended Acceptance Criteria

1. No hardcoded IPs/hostnames in object-level generators.
2. No cross-object imports between object modules.
3. Object module discovery is fully dynamic.
4. Capability-template mappings externalized to config.
5. Projection ownership boundaries documented and tested.

**Result:** all acceptance criteria for boundary-enforcement waves are satisfied.
