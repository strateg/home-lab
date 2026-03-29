# 0078 v4->v5 Migration Cutover Checklist

**Date:** 2026-03-27
**Status:** Completed (cutover closed 2026-03-27)
**Related plan:** `adr/plan/0078-plugin-layering-and-v4-v5-migration-plan.md`
**Related ADR0080 docs:**
- `adr/0080-analysis/CUTOVER-PLAN.md`
- `adr/0080-analysis/CUTOVER-CHECKLIST.md`

---

## 1. Scope

Этот checklist используется для фактического выполнения cutover шагов плана миграции v4->v5
в текущем root-layout репозитория.

Связка с completed-документами:

1. `0075-0074-master-migration-plan.md` — завершенный foundation baseline.
2. `0078-v5-unified-plugin-refactor-prep.md` — завершенный boundary-enforcement prep (WP6-WP10).
3. `0078-wave-d-v4-validator-mapping.md` — завершенный validator parity mapping.
4. `0078-plugin-layering-and-v4-v5-migration-plan.md` — завершенный migration baseline/policy.
5. Этот checklist — единственный активный execution-документ для финального cutover.

---

## 2. Pre-Cutover Readiness (T-1)

- [x] Root layout подтвержден: в корне репозитория отсутствуют `v4/` и `v5/`.
- [x] Legacy baseline доступен в `archive/v4/`.
- [x] Инструкции синхронизированы для всех агентов:
- [x] `CLAUDE.md`
- [x] `.codex/AGENTS.md`
- [x] `.codex/rules/tech-lead-architect.md`
- [x] `.github/copilot-instructions.md`
- [x] Для каждого переносимого v4 check/plugin зафиксирован stage-анализ:
- [x] определена целевая стадия (`discover|compile|validate|generate|assemble|build`)
- [x] stage assignment отражен в mapping/plan.

---

## 3. Mandatory Gates (P0)

- [x] `task validate:workspace-layout`
- [x] `task framework:audit-entrypoints`
- [x] `task acceptance:tests-all`
- [x] v4 baseline compile from archive:

```bash
python archive/v4/topology-tools/compile-topology.py \
  --topology archive/v4/topology.yaml \
  --output-json build/diagnostics/v4-archive-effective.json \
  --diagnostics-json build/diagnostics/v4-archive-diagnostics.json \
  --diagnostics-txt build/diagnostics/v4-archive-diagnostics.txt
```

- [x] Результаты P0 сохранены в `build/diagnostics/` и доступны для review.

Execution snapshot (2026-03-27):

- `validate:workspace-layout` -> PASS
- `framework:audit-entrypoints` -> PASS
- `framework:lock-refresh` -> PASS (required to clear `E7824` framework integrity mismatch)
- `acceptance:tests-all` -> PASS (`10 passed`)
- `archive/v4 compile` -> PASS (`errors=0`, diagnostics в `build/diagnostics/v4-archive-*`)

---

## 4. Cutover Execution (T0)

- [x] Выполнен freeze на не-критичные рефакторы до завершения cutover.
- [x] Выполнены P1 smoke-gates:
- [x] `task validate:default`
- [x] `task test:default`
- [x] `task ci:local`
- [x] Подтверждена lifecycle-цепочка default runtime:
- [x] `discover -> compile -> validate -> generate -> assemble -> build`.
- [x] Подтверждены 6 семейств плагинов и 6-stage affinity:
- [x] `discover -> discoverers (base.discover.*; discoverer kind)`
- [x] `compile -> compilers`
- [x] `validate -> validators`
- [x] `generate -> generators`
- [x] `assemble -> assemblers`
- [x] `build -> builders`
- [x] Подтверждено отсутствие operational зависимости от root `v4/`/`v5/`.
- [x] Создан cutover tag/snapshot (`cutover-0078-2026-03-27`).

Execution snapshot (2026-03-27):

- `validate:default` -> PASS (`errors=0`, `warnings=11`)
- `test:default` -> PASS (`603 passed`, `3 skipped`)
- `ci:local` -> PASS (quality + strict runtime + phase1 gate + tests)
- Stage inventory from `topology-tools/plugins/plugins.yaml`:
  - `discover=4`, `compile=7`, `validate=36`, `generate=6`, `assemble=4`, `build=3`
  - `base.discover.*` plugins confirmed as `kind=discoverer`, `stages=[discover]`
- Root layout guard re-checked: root `v4/` and root `v5/` are absent.
- Legacy phase1 bootstrap script migrated to archive baseline:
  - `topology-tools/utils/bootstrap-phase1-mapping.py` now uses `archive/v4/...` paths by default.
- Freeze/tag:
  - Non-critical refactor freeze observed through T0/T+1 execution window.
  - Cutover snapshot tag created: `cutover-0078-2026-03-27`.

---

## 5. Stabilization (T+1 .. T+7)

- [x] Мониторинг CI на ошибки `E800x/E810x/E820x` и нарушения layout guard.
- [x] Мониторинг acceptance TUC regression.
- [x] Мониторинг parity drift относительно `archive/v4`.
- [x] Все найденные инциденты triage-нуты и закрыты/эскалированы.
- [x] Два последовательных green cycle получены:
- [x] CI green
- [x] acceptance green
- [x] strict runtime audit green.

Stabilization snapshot (2026-03-27):

- Cycle #1:
  - `task validate:workspace-layout` -> PASS
  - `task framework:audit-entrypoints` -> PASS
  - `task acceptance:tests-all` -> PASS (`10 passed`)
  - `python archive/v4/topology-tools/compile-topology.py ...` -> PASS (`errors=0`)
  - `task ci:local` -> PASS
- Cycle #2:
  - `task validate:workspace-layout` -> PASS
  - `task framework:audit-entrypoints` -> PASS
  - `task acceptance:tests-all` -> PASS (`10 passed`)
  - `python archive/v4/topology-tools/compile-topology.py ...` -> PASS (`errors=0`)
  - `task ci:local` -> PASS
- Incident handling:
  - Initial `E7824` lock-integrity mismatch observed during stabilization run.
  - Resolved via `task framework:lock-refresh`; subsequent cycles green.
- Post-cutover hardening revalidation (2026-03-27, after module plugin-path migration):
  - `task framework:release-tests` -> PASS (`165 passed`)
  - `task framework:cutover-readiness-quick` -> PASS
  - `task framework:cutover-readiness` -> PASS
  - `task ci:local-with-legacy` -> PASS (`v5: 616 passed, 3 skipped; acceptance: 10 passed; parity: 22 passed, 3 skipped`)

---

## 6. Rollback Triggers

- [x] Trigger conditions monitored during cutover window; rollback triggers did not fire.

Defined rollback triggers:

1. Любой P0 gate красный на protected branch.
2. Acceptance suites красные после merge.
3. `framework:audit-entrypoints` красный без hotfix в release window.

If trigger fires:

1. Revert только offending commit(s).
2. Повторно прогнать P0 gates.
3. Возобновить cutover только после повторной валидации.

---

## 7. Exit Criteria

- [x] Все пункты разделов 2-6 закрыты.
- [x] Root-only layout стабилен (нет повторного появления root `v4/`/`v5/`).
- [x] `archive/v4` compile воспроизводим.
- [x] Все 6 семейств плагинов и полный 6-stage lifecycle (включая `discover`/`base.discover.*`) валидированы в default runtime.
- [x] Cutover официально отмечен как завершенный в release notes/plan status.
