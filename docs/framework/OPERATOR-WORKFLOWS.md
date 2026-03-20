# Framework/Project Operator Workflows

**Status:** Active  
**Updated:** 2026-03-20  
**ADR:** 0076

---

## Scope

Этот документ фиксирует операционные процедуры для `framework.lock.yaml` и обновления framework при strict-policy.

---

## Baseline Validation Flow

```powershell
python v5/topology-tools/verify-framework-lock.py --strict
python v5/topology-tools/compile-topology.py --secrets-mode passthrough --strict-model-lock
python v5/scripts/lane.py validate-v5
```

Любая ошибка `E781x/E782x` блокирует дальнейший прогон.

---

## Framework Update Flow

1. Обновить framework-источник (в monorepo: изменения в `v5/topology/**` + `v5/topology-tools/**`; в submodule-модели: обновить submodule pointer).
2. Пересобрать lock:
   ```powershell
   python v5/topology-tools/generate-framework-lock.py --force
   ```
3. Проверить lock:
   ```powershell
   python v5/topology-tools/verify-framework-lock.py --strict
   ```
4. Прогнать compile + validate-v5.
5. Закоммитить обновления framework + lock вместе.

---

## Rollback Flow

1. Вернуть framework на предыдущую ревизию (git revert/checkout нужного состояния).
2. Перегенерировать `framework.lock.yaml`.
3. Повторить strict verify и compile.
4. Зафиксировать rollback-коммит с явным указанием причины.

Перед rollback в релизном окне рекомендуется выполнить rehearsal:

```powershell
python v5/topology-tools/rehearse-framework-rollback.py
```

Команда проверяет:

1. текущий lock strict-valid;
2. lock можно регенерировать из текущего контракта;
3. регенерированный lock повторно проходит strict verify;
4. contract-ключи lock не дрейфуют между текущим и регенерированным вариантом.

---

## Version Skew Policy

1. `project_min_framework_version` и `project_max_framework_version` проверяются на этапе verify.
2. Несовместимость версий возвращает `E7811`.
3. Несовместимая схема проекта возвращает `E7812`.
4. Устаревшая ревизия контракта lock возвращает `E7813`.

Для регрессионной проверки матрицы (baseline + expected-fail сценарии):

```powershell
python v5/topology-tools/validate-framework-compatibility-matrix.py
```

Для контроля отсутствия legacy/fallback поведения в runtime entrypoints:

```powershell
python v5/topology-tools/audit-strict-runtime-entrypoints.py
```

---

## CI Gates

В CI перед lane/compile должен выполняться:

```powershell
python v5/topology-tools/verify-framework-lock.py --strict
```

Рекомендуемый порядок в pipeline:

1. lock verify
2. compile
3. validate/project gates
4. terraform/ansible syntax checks

Сводный readiness-отчет (локально перед cutover freeze):

```powershell
python v5/topology-tools/cutover-readiness-report.py --quick
```

После production cutover состояние фиксируется в:

- `docs/framework/adr0076-cutover-state.json`

Ожидаемые поля readiness-отчета после cutover:

1. `production_cutover_complete: true`
2. `ready_for_operational_baseline: true`
3. `pending_external_steps: []`

Полный e2e dry-run чеклист: `docs/framework/CUTOVER-DRY-RUN-RUNBOOK.md`.

Шаблон workflow для внешнего project-репозитория:

- `docs/framework/templates/project-validate.yml`
