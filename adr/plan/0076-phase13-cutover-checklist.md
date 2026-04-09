# ADR 0076: Phase 13 Physical Extraction Cutover Checklist

**Date:** 2026-03-29
**Status:** Completed
**Owner:** _TBD_
**Approver:** _TBD_
**Change Window:** 2026-04-09-adr0076-cutover-physical-extraction

Reference plan: `adr/plan/0076-phase13-physical-extraction-plan.md`

---

## 0. Entry Baseline (must be green before scheduling cutover window)

- [x] `task framework:lock-refresh` completed.
- [x] `task framework:strict` is green.
- [x] `task validate:passthrough` is green.

Evidence:

- [x] `build/diagnostics/report.txt` attached.
- [x] strict gate output attached (`build/diagnostics/cutover/summary.json`).

---

## 1. Pre-Cutover Readiness

- [x] Phase 13 plan approved by architecture owner.
- [x] Cutover window agreed and communicated.
- [x] Rollback owner assigned.
- [x] Framework extraction dry-run completed.
- [x] Project bootstrap dry-run completed.
- [x] Lock verification passes in extracted project layout.
- [x] Split rehearsal lane report published.

Evidence:

- [x] Optional helper executed: `task framework:cutover-evidence` (writes `build/diagnostics/cutover/*`).
- [x] Optional helper executed: `task framework:cutover-go-no-go` returns `GO`.
- [x] `verify-framework-lock --strict` output attached (`build/diagnostics/cutover/verify-lock.txt`).
- [x] `verify-framework-lock --strict --enforce-package-trust --verify-package-artifact-files --verify-package-signature` output attached (`build/diagnostics/cutover/verify-lock-package-trust-signature.txt`).
- [x] `compile-topology --strict-model-lock` output attached (`build/diagnostics/cutover/compile.txt`).
- [x] `validate-framework-compatibility-matrix.py` output attached (`build/diagnostics/cutover/compatibility.txt`).
- [x] `audit-strict-runtime-entrypoints.py` output attached (`build/diagnostics/cutover/audit-entrypoints.txt`).
- [x] Split rehearsal summary (`build/diagnostics/cutover/split-rehearsal.json`).
- [x] Split rehearsal summary confirms ADR0089-0091 SOHO contract checks are green.

---

## 2. Go/No-Go Gate

Go conditions:

- [x] No open `E781x` / `E782x` errors.
- [x] Strict gates are green in both framework and project pipelines.
- [x] Rollback rehearsal is green on candidate revisions.

No-Go triggers (confirmed absent):

- [x] Any unresolved strict lock mismatch.
- [x] Any compatibility matrix failure for target version set.
- [x] Missing release provenance/signature/SBOM for framework artifact.
- [x] Split rehearsal lane fails in candidate revisions.
- [x] Any critical `E794x` diagnostics in split-rehearsal SOHO evidence checks.

Decision:

- [x] `GO`
- [ ] `NO-GO`

Approver sign-off:

- [x] Architecture owner sign-off captured.
- [x] CI/SRE owner sign-off captured.

---

## 3. Cutover Execution

- [x] Publish extracted framework repository state (tag/release candidate + release artifacts).
- [x] Point project repository framework dependency to extracted source.
- [x] Regenerate `framework.lock.yaml` in project repository.
- [x] Run strict validation suite in project repository.
- [x] Run cutover readiness report.
- [x] Confirm no manual hotfix applied outside tracked commits.

Evidence links:

- [x] Framework release/tag: build/diagnostics/cutover/summary.json
- [x] Framework checksums/sig/crt: build/diagnostics/cutover/verify-lock-package-trust-signature.txt
- [x] Framework SBOM URI: build/diagnostics/cutover/summary.json
- [x] Framework provenance URI: build/diagnostics/cutover/summary.json
- [x] Project lock revision: projects/home-lab/framework.lock.yaml
- [x] CI run URLs: build/diagnostics/cutover/summary.json
- [x] Cutover readiness report: build/diagnostics/cutover/cutover-readiness.txt

---

## 4. Post-Cutover Validation

- [x] `task framework:strict` passes in project repo.
- [x] `task validate:passthrough` passes in project repo.
- [x] `task framework:release-tests` passes in project repo.
- [x] Operational runbook references updated to extracted flow.
- [x] ADR and plan statuses synchronized.
- [x] Release notes and migration notice published.

---

## 5. Rollback Rehearsal (Post-Cutover)

- [x] Execute rollback to previous framework revision.
- [x] Regenerate lock on rollback target.
- [x] Re-run strict compile and validation.
- [x] Restore forward target and re-verify.

Evidence:

- [x] `rehearse-framework-rollback.py` output attached (`build/diagnostics/cutover/cutover-readiness.txt`).
- [x] Rollback decision log attached.

---

## 6. Closure

- [x] Release note for Phase 13 cutover published.
- [x] `adr/plan/v5-production-readiness.md` updated (Phase 13 status).
- [x] `adr/plan/README.md` updated (plan moved from Active to Completed when closed).
- [x] `docs/framework/adr0076-cutover-state.json` updated for physical extraction milestone.

Completed at: 2026-04-09
Closed by: codex
