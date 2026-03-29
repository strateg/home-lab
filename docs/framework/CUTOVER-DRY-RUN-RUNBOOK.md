# ADR0076 Cutover Dry-Run Runbook

**Status:** Active
**Updated:** 2026-03-20
**ADR:** 0076

---

## Scope

Документ фиксирует dry-run последовательность перед финальным multi-repo cutover.

Цель: проверить strict-gates, воспроизводимость lock и готовность bootstrap-процедур без переключения production CI.

---

## Prerequisites

1. Рабочее дерево чистое (`git status` без незакоммиченных изменений).
2. Python окружение готово для `tests` и `scripts/orchestration/lane.py`.
3. Текущий проект: `projects/home-lab`.

---

## Phase A: Strict Gate Baseline

```powershell
python topology-tools/generate-framework-lock.py --force
python topology-tools/verify-framework-lock.py --strict
python topology-tools/utils/rehearse-framework-rollback.py
python topology-tools/utils/validate-framework-compatibility-matrix.py
python topology-tools/utils/audit-strict-runtime-entrypoints.py
```

Критерий PASS: все команды завершаются с `exit code 0`.

---

## Phase B: Full Readiness Report

```powershell
python topology-tools/utils/cutover-readiness-report.py
```

Артефакт:

- `build/diagnostics/cutover-readiness.json`

Критерий PASS:

1. `ready_for_cutover: true`
2. `summary.failed: 0`
3. Все gate entries в `gates[]` имеют `ok: true`

---

## Phase C: Framework Extraction Dry-Run

```powershell
python topology-tools/utils/bootstrap-framework-repo.py `
  --output-root build/infra-topology-framework-bootstrap `
  --include-tests `
  --preserve-history `
  --force
```

Проверить наличие:

1. `build/infra-topology-framework-bootstrap/framework.yaml`
2. `build/infra-topology-framework-bootstrap/topology-tools/`
3. `build/infra-topology-framework-bootstrap/.github/workflows/release.yml`

Framework-focused test gate (локальный аналог release CI):

```powershell
python -m pytest -o addopts= `
  build/infra-topology-framework-bootstrap/tests/plugin_api `
  build/infra-topology-framework-bootstrap/tests/plugin_contract `
  build/infra-topology-framework-bootstrap/tests/plugin_integration/test_framework_lock.py `
  build/infra-topology-framework-bootstrap/tests/plugin_integration/test_build_framework_distribution.py `
  build/infra-topology-framework-bootstrap/tests/plugin_integration/test_extract_framework_worktree.py `
  build/infra-topology-framework-bootstrap/tests/plugin_integration/test_extract_framework_history.py -q
```

---

## Phase D: Project Bootstrap Dry-Run

```powershell
python topology-tools/utils/bootstrap-project-repo.py `
  --framework-root build/infra-topology-framework-bootstrap `
  --output-root build/project-bootstrap/home-lab `
  --project-id home-lab `
  --seed-project-root projects/home-lab `
  --init-git `
  --framework-submodule-url D:/Workspaces/PycharmProjects/home-lab/build/infra-topology-framework-bootstrap `
  --framework-submodule-path framework `
  --force
```

Проверить наличие:

1. `build/project-bootstrap/home-lab/topology.yaml`
2. `build/project-bootstrap/home-lab/project.yaml`
3. `build/project-bootstrap/home-lab/framework.lock.yaml`
4. `build/project-bootstrap/home-lab/.github/workflows/validate.yml`

Strict compile rehearsal для external project layout:

```powershell
python build/project-bootstrap/home-lab/framework/topology-tools/verify-framework-lock.py `
  --repo-root build/project-bootstrap/home-lab `
  --topology topology.yaml `
  --project-root build/project-bootstrap/home-lab `
  --project-manifest build/project-bootstrap/home-lab/project.yaml `
  --framework-root build/project-bootstrap/home-lab/framework `
  --lock-file build/project-bootstrap/home-lab/framework.lock.yaml `
  --strict

python build/project-bootstrap/home-lab/framework/topology-tools/compile-topology.py `
  --repo-root build/project-bootstrap/home-lab `
  --topology topology.yaml `
  --strict-model-lock `
  --secrets-mode passthrough `
  --parallel-plugins `
  --output-json generated/effective-topology.json `
  --diagnostics-json generated/diagnostics.json `
  --diagnostics-txt generated/diagnostics.txt `
  --artifacts-root generated-artifacts
```

Примечание: параллельный режим плагинов включен по умолчанию.
Для отладки/локального сравнения используйте `--no-parallel-plugins`.

---

## Phase E: Exit Criteria

Dry-run считается успешным, если одновременно выполняются условия:

1. Phase A и Phase B проходят без ошибок.
2. Framework/project bootstrap каталоги созданы и содержат ожидаемые manifest/workflow файлы.
3. В diagnostics нет unresolved `E781x/E782x`.

Production cutover выполняется отдельным change-window после dry-run PASS.

После выполнения change-window зафиксировать completion marker:

- `docs/framework/adr0076-cutover-state.json` (`production_cutover_complete: true`).
