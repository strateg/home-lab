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
2. Python окружение готово для `v5/tests` и `v5/scripts/lane.py`.
3. Текущий проект: `v5/projects/home-lab`.

---

## Phase A: Strict Gate Baseline

```powershell
python v5/topology-tools/generate-framework-lock.py --force
python v5/topology-tools/verify-framework-lock.py --strict
python v5/topology-tools/rehearse-framework-rollback.py
python v5/topology-tools/validate-framework-compatibility-matrix.py
python v5/topology-tools/audit-strict-runtime-entrypoints.py
```

Критерий PASS: все команды завершаются с `exit code 0`.

---

## Phase B: Full Readiness Report

```powershell
python v5/topology-tools/cutover-readiness-report.py
```

Артефакт:

- `v5-build/diagnostics/cutover-readiness.json`

Критерий PASS:

1. `ready_for_cutover: true`
2. `summary.failed: 0`
3. Все gate entries в `gates[]` имеют `ok: true`

---

## Phase C: Framework Extraction Dry-Run

```powershell
python v5/topology-tools/bootstrap-framework-repo.py `
  --output-root v5-build/infra-topology-framework-bootstrap `
  --include-tests `
  --force
```

Проверить наличие:

1. `v5-build/infra-topology-framework-bootstrap/framework.yaml`
2. `v5-build/infra-topology-framework-bootstrap/topology-tools/`
3. `v5-build/infra-topology-framework-bootstrap/.github/workflows/release.yml`

---

## Phase D: Project Bootstrap Dry-Run

```powershell
python v5/topology-tools/bootstrap-project-repo.py `
  --framework-root . `
  --output-root v5-build/project-bootstrap/home-lab `
  --project-id home-lab `
  --force
```

Проверить наличие:

1. `v5-build/project-bootstrap/home-lab/topology.yaml`
2. `v5-build/project-bootstrap/home-lab/project.yaml`
3. `v5-build/project-bootstrap/home-lab/framework.lock.yaml`
4. `v5-build/project-bootstrap/home-lab/.github/workflows/validate.yml`

Примечание: bootstrap-скелетон содержит пустые `instances/` и `secrets/`.
Полноценный compile/generate PASS ожидается только после переноса проектных данных.

---

## Phase E: Exit Criteria

Dry-run считается успешным, если одновременно выполняются условия:

1. Phase A и Phase B проходят без ошибок.
2. Framework/project bootstrap каталоги созданы и содержат ожидаемые manifest/workflow файлы.
3. В diagnostics нет unresolved `E781x/E782x`.

Production cutover выполняется отдельным change-window после dry-run PASS.
