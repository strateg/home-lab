# ADR 0076: Phase 13 Physical Extraction Cutover Checklist

**Date:** 2026-03-29
**Status:** Active
**Owner:** _TBD_
**Approver:** _TBD_
**Change Window:** _TBD_

Reference plan: `adr/plan/0076-phase13-physical-extraction-plan.md`

---

## 0. Entry Baseline (must be green before scheduling cutover window)

- [ ] `task framework:lock-refresh` completed.
- [ ] `task framework:strict` is green.
- [ ] `task validate:v5-passthrough` is green.

Evidence:

- [ ] `build/diagnostics/report.txt` attached.
- [ ] strict gate output attached.

---

## 1. Pre-Cutover Readiness

- [ ] Phase 13 plan approved by architecture owner.
- [ ] Cutover window agreed and communicated.
- [ ] Rollback owner assigned.
- [ ] Framework extraction dry-run completed.
- [ ] Project bootstrap dry-run completed.
- [ ] Lock verification passes in extracted project layout.
- [ ] Split rehearsal lane report published.

Evidence:

- [ ] Optional helper executed: `task framework:phase13-evidence` (writes `build/diagnostics/phase13/*`).
- [ ] Optional helper executed: `task framework:phase13-go-no-go` returns `GO`.
- [ ] `verify-framework-lock --strict` output attached (`build/diagnostics/phase13/verify-lock.txt`).
- [ ] `compile-topology --strict-model-lock` output attached (`build/diagnostics/phase13/compile.txt`).
- [ ] `validate-framework-compatibility-matrix.py` output attached (`build/diagnostics/phase13/compatibility.txt`).
- [ ] `audit-strict-runtime-entrypoints.py` output attached (`build/diagnostics/phase13/audit-entrypoints.txt`).
- [ ] Split rehearsal summary (`build/diagnostics/phase13/split-rehearsal.json`).
- [ ] Split rehearsal summary confirms ADR0089-0091 SOHO contract checks are green.

---

## 2. Go/No-Go Gate

Go conditions:

- [ ] No open `E781x` / `E782x` errors.
- [ ] Strict gates are green in both framework and project pipelines.
- [ ] Rollback rehearsal is green on candidate revisions.

No-Go triggers:

- [ ] Any unresolved strict lock mismatch.
- [ ] Any compatibility matrix failure for target version set.
- [ ] Missing release provenance/signature/SBOM for framework artifact.
- [ ] Split rehearsal lane fails in candidate revisions.
- [ ] Any critical `E794x` diagnostics in split-rehearsal SOHO evidence checks.

Decision:

- [ ] `GO`
- [ ] `NO-GO`

Approver sign-off:

- [ ] Architecture owner sign-off captured.
- [ ] CI/SRE owner sign-off captured.

---

## 3. Cutover Execution

- [ ] Publish extracted framework repository state (tag/release candidate + release artifacts).
- [ ] Point project repository framework dependency to extracted source.
- [ ] Regenerate `framework.lock.yaml` in project repository.
- [ ] Run strict validation suite in project repository.
- [ ] Run cutover readiness report.
- [ ] Confirm no manual hotfix applied outside tracked commits.

Evidence links:

- [ ] Framework release/tag:
- [ ] Framework checksums/sig/crt:
- [ ] Framework SBOM URI:
- [ ] Framework provenance URI:
- [ ] Project lock revision:
- [ ] CI run URLs:
- [ ] Cutover readiness report:

---

## 4. Post-Cutover Validation

- [ ] `task framework:strict` passes in project repo.
- [ ] `task validate:v5` passes in project repo.
- [ ] `task framework:release-tests` passes in project repo.
- [ ] Operational runbook references updated to extracted flow.
- [ ] ADR and plan statuses synchronized.
- [ ] Release notes and migration notice published.

---

## 5. Rollback Rehearsal (Post-Cutover)

- [ ] Execute rollback to previous framework revision.
- [ ] Regenerate lock on rollback target.
- [ ] Re-run strict compile and validation.
- [ ] Restore forward target and re-verify.

Evidence:

- [ ] `rehearse-framework-rollback.py` output attached (`build/diagnostics/phase13/rollback-rehearsal.txt`).
- [ ] Rollback decision log attached.

---

## 6. Closure

- [ ] Release note for Phase 13 cutover published.
- [ ] `adr/plan/v5-production-readiness.md` updated (Phase 13 status).
- [ ] `adr/plan/README.md` updated (plan moved from Active to Completed when closed).
- [ ] `docs/framework/adr0076-cutover-state.json` updated for physical extraction milestone.

Completed at: _TBD_
Closed by: _TBD_
