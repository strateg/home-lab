# Master Migration Plan: ADR0075 -> ADR0074

**Дата:** 2026-03-20
**Статус:** Completed (E2E validated 2026-03-24)
**Последовательность:** Сначала ADR0075 (Stage 1), затем закрытие оставшихся задач ADR0074

---

## Layout Alignment Note (2026-03-27)

1. Этот документ зафиксирован как historical completed plan.
2. Исторические пути вида `v5/...` трактуются как pre-root-layout ссылки.
3. Текущий operational layout: корень репозитория + legacy baseline в `archive/v4`.
4. Для активного cutover-исполнения использовать `adr/plan/0078-cutover-checklist.md` и ADR0080 cutover artifacts.

---

## Цель

Перевести v5 на проектно-ориентированную структуру (`framework` + `project`) без поломки компилятора, валидаторов и генераторов, а затем завершить rollout генераторной архитектуры ADR0074 уже на новом контракте путей.

## Нормативный порядок

1. Выполнить ADR0075 Stage 1 (monorepo separation).
2. Только после стабилизации Stage 1 выполнять оставшиеся задачи ADR0074.
3. ADR0076 (multi-repo extraction) запускать отдельной волной после стабилизации 0075+0074.

---

## Wave 0: Подготовка и Freeze

### Задачи

1. Зафиксировать baseline:
   - `python -m pytest v5/tests -q -o addopts=''`
   - `V5_SECRETS_MODE=passthrough python v5/scripts/orchestration/lane.py validate-v5`
2. Ввести временный change freeze на изменения генераторов вне контекста 0075.
3. Подготовить migration branch и контрольные артефакты (`v5-build/diagnostics/*`).

### Definition of Done

1. Baseline green.
2. Есть отдельная ветка миграции.

---

## Wave 1: ADR0075 Stage 1 (Monorepo Separation)

### 1.1 Manifest Contract

1. Добавить в `v5/topology/topology.yaml` секции `framework:` и `project:`.
2. Убрать использование `paths:` из runtime контракта.
3. Ввести hard-error `E7808` при обнаружении legacy `paths.*`.

### 1.2 Project Root Introduction

1. Создать `v5/projects/home-lab/project.yaml`.
2. Перенести:
   - `v5/topology/instances` -> `v5/projects/home-lab/instances`
   - `v5/topology/instances/_legacy-home-lab` -> `v5/projects/home-lab/_legacy`
3. Перевести секреты на project-root:
   - целевой путь: `v5/projects/home-lab/secrets`
   - без fallback на `v5/secrets` в strict-профиле.

### 1.3 Compiler/Runtime Refactor

1. Обновить path resolution в `compile-topology.py` и `compiler_runtime.py`.
2. Обновить plugin context (`secrets_root`, `generator_artifacts_root`) с project-awareness.
3. Добавить диагностики `E7801..E7808` и валидацию strict-only контракта.

### 1.4 Script and Validation Refactor

1. Обновить `v5/scripts/validation/validate_v5_scaffold.py`.
2. Обновить `v5/scripts/validation/validate_v5_layer_contract.py`.
3. Обновить `v5/scripts/orchestration/lane.py` и phase/mapping scripts с жестких путей на project-root.

### 1.5 Tests

1. Обновить unit/integration tests на новый контракт путей.
2. Добавить негативные тесты на `E7808` (legacy paths запрещены).
3. Убрать сценарии fallback из актуального тестового контура.

### Definition of Done

1. Все тесты green.
2. `validate-v5` green.
3. Компилятор работает в project-aware strict-only режиме.
4. Любой legacy `paths.*` приводит к `E7808`.

---

## Wave 2: ADR0074 Completion on New Structure

### 2.1 Project-aware Generation Contract

1. Уточнить output ownership:
   - `v5-generated/<project>/terraform/...`
   - `v5-generated/<project>/ansible/...`
   - `v5-generated/<project>/bootstrap/...`
2. Обновить генераторы и projection contract tests под project context.

### 2.2 Runtime Assembly

1. Обновить `assemble-ansible-runtime.py` на project-qualified inventory/runtime roots.
2. Проверить ручные overrides в project scope.

### 2.3 Parity and Gates

1. Перебазировать parity tests на новый output layout.
2. Сохранить deterministic/snapshot гарантии.
3. Прогнать CI-эквивалент локально:
   - Terraform fmt/validate
   - ansible-inventory --list

### 2.4 Open Items from ADR0074

1. Закрыть hardware identity utility + strict placeholder closure.
2. Обновить cutover runbooks под project-aware layout.
3. Выполнить E2E dry-run.

### Definition of Done

1. ADR0074 open items закрыты без возврата к legacy paths.
2. Все generator gates green на project-qualified outputs.

---

## Wave 3: Stabilization and Cutover

### Задачи

1. Удалить legacy fallback полностью (не только по флагу).
2. Обновить документацию (`README`, operator workflow, manual artifact build).
3. Зафиксировать release notes: migration completed.

### Definition of Done

1. Legacy `paths` не используются в production профиле.
2. Документация и тесты соответствуют новой структуре.

---

## Wave 4 (Отдельно): ADR0076 Stage 2

1. Multi-repo extraction запускать только после Wave 3.
2. Отдельный roadmap и отдельные риски (dependency lock/integrity, CI cross-repo).

---

## Risk Register

1. **Path drift в скриптах**: закрывать через central path resolver и contract tests.
2. **Секреты не переехали в project-root**: блокировать release до миграции.
3. **Повторный рефакторинг генераторов**: избегается строгой последовательностью 0075 -> 0074.
4. **Диагностики конфликтуют по кодам**: для strict-only контракта использовать `E7808`; новые проектные коды выносить в отдельный диапазон без пересечений.

---

## Commit Strategy

1. `feat(0075): manifest contract framework/project + diagnostics`
2. `refactor(0075): move instances to v5/projects/home-lab`
3. `refactor(0075): rewire scripts and validators to project root`
4. `test(0075): add strict-only project-aware coverage (E7808)`
5. `refactor(0074): project-qualified generator output roots`
6. `feat(0074): runtime assembly project-aware`
7. `docs: cutover and operator workflow update`

---

## Контрольные команды (каждая волна)

1. `python -m pytest v5/tests -q -o addopts=''`
2. `V5_SECRETS_MODE=passthrough python v5/scripts/orchestration/lane.py validate-v5`
3. Для Wave 2+: локальные проверки generator gates (terraform/ansible) на project-qualified output.

---

## Execution Status (2026-03-20)

- [x] Wave 1: framework/project manifest contract + project root migration + strict diagnostics (`E7808`)
- [x] Wave 2.1: project-qualified generator output roots
- [x] Wave 2.2: project-aware ansible runtime assembly
- [x] Wave 2.4: hardware identity patch utility + secret-scoped strict placeholder closure
- [x] Wave 3: legacy fallback removal from strict model paths/projections
- [x] Wave 3: CI/workflow/documentation cutover updates
- [x] Phase 8 runbook published: `docs/runbooks/V5-E2E-DRY-RUN.md`
- [x] Phase 8 E2E dry-run executed (2026-03-24):
  - Compile: 0 errors, 14 warnings, 69 infos
  - Terraform Proxmox: init + fmt + validate ✅
  - Terraform MikroTik: init + fmt + validate ✅
  - Ansible inventory: 15 hosts ✅
  - Bootstrap: 3 devices ✅
- [x] Final validation:
  - `python -m pytest v5/tests -q -o addopts=''` -> `271 passed`
  - `V5_SECRETS_MODE=passthrough python v5/scripts/orchestration/lane.py validate-v5` -> `PASS`

---

## E2E Completion Summary (2026-03-24)

### Migration Status: ✅ COMPLETE

All blocking tasks resolved:
- v5 compiler strict mode operational
- Framework lock verification active
- E2E artifact generation validated
- No E-level errors in diagnostics

### Remaining Cosmetic Warnings (11)

| Code | Count | Description |
|------|-------|-------------|
| W7816 | 2 | IP reuse (expected: gateway, postgres) |
| W7888 | 9 | Deprecated inline resources |

### Resolved Warnings (2026-03-24)

| Code | Count | Resolution |
|------|-------|------------|
| W7845 | 3 | Added `security.ssl_certificate: self-signed` to HTTPS services |

### Next Steps (Optional)

1. ~~Add `security.ssl_certificate` to HTTPS services (W7845)~~ ✅
2. Migrate LXC to resource profiles (W7888) - requires resource profile taxonomy
3. v4 validator parity fixtures per deprecation matrix
