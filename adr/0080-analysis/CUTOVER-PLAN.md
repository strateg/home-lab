# ADR 0080 Prioritized Cutover Plan

**ADR:** `adr/0080-unified-build-pipeline-stage-phase-and-plugin-data-bus.md`
**Date:** 2026-03-27
**Status:** Active operational plan

---

## 1. Scope

План фиксирует operational cutover после завершения ADR0080 runtime-изменений с учетом текущего layout:

1. Активная разработка и запуск идут из корня репозитория.
2. Legacy baseline `v4` хранится в `archive/v4`.
3. Root-директории `v4/` и `v5/` не допускаются.

---

## 2. Priorities

### P0 (blockers, must be green before cutover close)

1. Layout guard:
   - `task validate:workspace-layout`
   - результат: в корне нет `v4/` и `v5/`.
2. Strict runtime guard:
   - `task framework:audit-entrypoints`
   - результат: strict runtime audit green.
3. Acceptance baseline:
   - `task acceptance:tests-all`
   - результат: TUC acceptance suites green.
4. Legacy reproducibility:
   - `python archive/v4/v4/topology-tools/compile-topology.py --topology archive/v4/v4/topology.yaml --output-json build/diagnostics/v4-archive-effective.json --diagnostics-json build/diagnostics/v4-archive-diagnostics.json --diagnostics-txt build/diagnostics/v4-archive-diagnostics.txt`
   - результат: v4 compile from archive runs successfully.

### P1 (cutover execution)

1. Confirm root-only operation in task/CI entrypoints:
   - `task validate:default`
   - `task test:default`
   - `task ci:local`
2. Confirm plugin lifecycle path (discover/compile/validate/generate/assemble/build) in default runtime.
3. Confirm 5 plugin families in active manifests/runtime contracts:
   - `compilers`, `validators`, `generators`, `assemblers`, `builders`.
4. Confirm stage affinity is respected:
   - `compile -> compilers`
   - `validate -> validators`
   - `generate -> generators`
   - `assemble -> assemblers`
   - `build -> builders`
5. Confirm no operational dependency on root `v4/` or root `v5/`.

### P2 (post-cutover hardening)

1. Keep parity checks against `archive/v4` in regression lanes.
2. Keep acceptance TUC workflow as mandatory release gate.
3. Keep layout/strict audit checks in preflight and CI.
4. Update runbooks/docs when command contracts change.

---

## 3. Cutover Sequence

### Stage A — Pre-cutover (T-1)

1. Freeze non-critical refactors.
2. Run all P0 gates.
3. Publish gate report in `build/diagnostics/` and attach to release notes.

### Stage B — Cutover (T0)

1. Run P1 validation set on target branch.
2. Tag cutover snapshot (git tag/release marker).
3. Announce root layout as single active lane.

### Stage C — Stabilization (T+1 .. T+7)

1. Monitor CI for `W/E800x`, `E810x`, `E820x`, and layout violations.
2. Triage regressions with priority:
   - production breakage,
   - acceptance regression,
   - legacy parity drift vs `archive/v4`.
3. Close cutover when 2 consecutive green cycles pass (CI + acceptance + strict audit).

---

## 4. Rollback Policy

Rollback trigger (any one):

1. P0 gate fails on protected branch.
2. Acceptance suites red after cutover merge.
3. Runtime strict audit red with no hotfix inside release window.

Rollback action:

1. Revert only offending cutover commits.
2. Re-run P0 gates.
3. Re-open cutover after fix is merged and revalidated.

---

## 5. Exit Criteria

Cutover is considered closed when:

1. P0/P1/P2 controls are active in CI/task flows.
2. Root-only layout is stable (no recreated `v4/`/`v5/` in root).
3. `archive/v4` compile remains reproducible.
4. Acceptance TUC and strict runtime audit are green on release branch.
5. Все 5 семейств плагинов и их stage affinity входят в validated default runtime cutover gates.
