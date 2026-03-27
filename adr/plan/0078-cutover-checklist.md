# 0078 v4->v5 Migration Cutover Checklist

**Date:** 2026-03-27
**Status:** Active (execution checklist)
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

- [ ] Выполнен freeze на не-критичные рефакторы до завершения cutover.
- [ ] Выполнены P1 smoke-gates:
- [ ] `task validate:default`
- [ ] `task test:default`
- [ ] `task ci:local`
- [ ] Подтверждена lifecycle-цепочка default runtime:
- [ ] `discover -> compile -> validate -> generate -> assemble -> build`.
- [ ] Подтверждены 5 семейств плагинов и 6-stage affinity:
- [ ] `discover -> discovery plugins (base.discover.*; compiler kind)`
- [ ] `compile -> compilers`
- [ ] `validate -> validators`
- [ ] `generate -> generators`
- [ ] `assemble -> assemblers`
- [ ] `build -> builders`
- [ ] Подтверждено отсутствие operational зависимости от root `v4/`/`v5/`.
- [ ] Создан cutover tag/snapshot.

---

## 5. Stabilization (T+1 .. T+7)

- [ ] Мониторинг CI на ошибки `E800x/E810x/E820x` и нарушения layout guard.
- [ ] Мониторинг acceptance TUC regression.
- [ ] Мониторинг parity drift относительно `archive/v4`.
- [ ] Все найденные инциденты triage-нуты и закрыты/эскалированы.
- [ ] Два последовательных green cycle получены:
- [ ] CI green
- [ ] acceptance green
- [ ] strict runtime audit green.

---

## 6. Rollback Triggers

- [ ] Любой P0 gate красный на protected branch.
- [ ] Acceptance suites красные после merge.
- [ ] `framework:audit-entrypoints` красный без hotfix в release window.

Если trigger сработал:

- [ ] Revert только offending commit(s).
- [ ] Повторно прогнать P0 gates.
- [ ] Возобновить cutover только после повторной валидации.

---

## 7. Exit Criteria

- [ ] Все пункты разделов 2-6 закрыты.
- [ ] Root-only layout стабилен (нет повторного появления root `v4/`/`v5/`).
- [ ] `archive/v4` compile воспроизводим.
- [ ] Все 5 семейств плагинов и полный 6-stage lifecycle (включая `discover`/`base.discover.*`) валидированы в default runtime.
- [ ] Cutover официально отмечен как завершенный в release notes/plan status.
