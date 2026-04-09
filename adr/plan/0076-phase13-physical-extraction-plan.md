# ADR 0076: Phase 13 Physical Extraction Plan

**Date:** 2026-03-29
**Status:** Active
**Depends on:** ADR 0076 Stage 2 baseline (`submodule-first`)
**Supersedes:** none (extends `adr/plan/0076-multi-repo-extraction-plan.md`)

---

## Objective

Execute the physical split from current root repository into independent repositories:

1. `infra-topology-framework` (framework source of truth)
2. `home-lab` (project source of truth)

while preserving ADR0076 strict lock/compatibility guarantees and rollback ability.

---

## Current State Audit (2026-03-29)

### What is already strong

1. ADR0076 Stage 2 contracts are implemented:
   - lock schema + strict diagnostics (`E7811..E7813`, `E7821..E7828`),
   - lock verify/generate utilities,
   - compatibility matrix, rollback rehearsal, runtime entrypoint audit.
2. Extraction/bootstrap toolchain exists:
   - `extract-framework-history.py`, `extract-framework-worktree.py`,
   - `bootstrap-framework-repo.py`, `bootstrap-project-repo.py`, `init-project-repo.py`.
3. CI templates for split model exist:
   - `docs/framework/templates/framework-release.yml`,
   - `docs/framework/templates/project-validate.yml`.

### Current blockers and inconsistencies

1. Baseline strict gates are currently red in root repo:
   - `task framework:strict` fails with `E7824` (framework integrity mismatch),
   - `task validate:v5-passthrough` fails on same `E7824`.
2. Documentation inconsistency remains:
   - multiple docs still describe Stage 2 as final target, while Phase 13 physical split is now active.
3. Supply-chain trust validation gap for package mode:
   - strict verify checks only presence of `signature/provenance/sbom` mappings, not cryptographic validity.
4. Framework release workflow still uses provenance placeholder:
   - not a real attestation chain for final physical-cutover baseline.
5. No deterministic, automated "split rehearsal" lane in current CI:
   - extraction + external project bootstrap + strict compile/verify are not run as one integrated gate.

### Implication

Phase 13 cannot safely enter execution window until baseline strict gates are green and the split rehearsal gate is added.

---

## Scope

In scope:

1. history-preserving framework extraction
2. project bootstrap and strict compile against extracted framework
3. cross-repository CI/CD split and governance
4. cutover + rollback evidence

Out of scope:

1. ADR0053 / ADR0047 policy decisions
2. functional topology redesign
3. plugin architecture redesign not tied to extraction

---

## Execution Strategy

## Wave P0: Baseline Stabilization (hard prerequisite)

### WS0.1 Lock Integrity Recovery

- [ ] Regenerate `projects/home-lab/framework.lock.yaml` from current trusted root.
- [ ] Re-run strict gates until baseline is green.
- [ ] Store diagnostics snapshot as entry evidence for Phase 13.

Entry Gate:

- `task framework:lock-refresh`
- `task framework:strict`
- `task validate:v5-passthrough`

### WS0.2 Governance Sync

- [ ] Align ADR0076 operational docs to "Stage 2 complete, Phase 13 active".
- [ ] Freeze cutover branch/tag policy.
- [ ] Assign accountable owners for cutover and rollback.

---

## Wave P1: Extraction Readiness Hardening

### WS1.1 Split Rehearsal Lane (missing gate)

- [x] Add CI/local task that performs end-to-end rehearsal:
  - extract framework with history,
  - bootstrap external project repo,
  - generate+verify lock in extracted layout,
  - compile in strict mode (`passthrough` secrets mode).
- [x] Publish rehearsal report under `build/diagnostics/phase13/`.

Gate:

- `python topology-tools/utils/extract-framework-history.py ...`
- `python topology-tools/utils/bootstrap-project-repo.py ...`
- `python topology-tools/verify-framework-lock.py --strict ...`
- `python topology-tools/compile-topology.py --strict-model-lock ...`

### WS1.1b SOHO Product-Contract Bridge (ADR0089-0091)

- [x] Enforce SOHO contract checks in split rehearsal summary:
  - mandatory handover/report files present,
  - ADR0091 D3 evidence domains present,
  - normalized support bundle completeness state present.
- [ ] Add semantic parity comparison against monorepo baseline for operator-readiness payload.
- [ ] Promote split-rehearsal summary as mandatory Phase13 CI artifact.

### WS1.2 Contract Hardening for Extracted Mode

- [ ] Add explicit tests for extracted-repo lock revision behavior (no accidental monorepo bypass in extracted topology).
- [ ] Add guard tests for distribution include-path stability after extraction.
- [ ] Add contract test for generated project skeleton paths (`topology/instances`, `generated`, `generated-artifacts`).
- [ ] Add extracted-mode contract test for `product:doctor` status derivation from generated machine-readable evidence.
- [ ] Add extracted-mode contract test for `product:handover` completeness gate behavior.

### WS1.3 Trust Pipeline Hardening

- [ ] Replace provenance placeholder flow with real attestation publication/verification path.
- [ ] Add strict verification for package-mode trust fields (not only existence checks).

---

## Wave P2: Physical Extraction Execution

### WS2.1 Framework Repository Cut

- [ ] Execute history-preserving extraction to framework target repository.
- [ ] Validate extracted repository test matrix.
- [ ] Publish signed/tagged framework candidate release.

Gate:

- framework CI green on extracted repository,
- release artifact set complete and verifiable.

### WS2.2 Project Repository Cut

- [ ] Bootstrap/align project repository to consume extracted framework.
- [ ] Update `framework.lock.yaml` to extracted framework release revision.
- [ ] Validate strict compile/validation gates in project repository.

Gate:

- project CI green with strict lock verification before compile.

---

## Wave P3: Cutover and Post-Cutover Stabilization

### WS3.1 Cutover Window

- [ ] Execute `adr/plan/0076-phase13-cutover-checklist.md`.
- [ ] Record Go/No-Go decision with evidence links.
- [ ] Publish release note for physical cutover.

### WS3.2 Rollback Rehearsal After Cutover

- [ ] Rehearse rollback on post-cutover revisions.
- [ ] Verify forward restore and lock re-validation.
- [ ] Record rollback rehearsal evidence.

---

## Dependencies Between Workstreams

1. WS0 -> WS1 -> WS2 -> WS3 is strict sequence.
2. WS1.3 (trust hardening) must complete before WS2.1 release candidate approval.
3. No cutover execution is allowed while WS0 baseline gate is red.

---

## Deliverables

1. Extracted `infra-topology-framework` repository with preserved history and green CI.
2. Extracted `home-lab` project repository consuming extracted framework under strict lock policy.
3. Integrated split rehearsal lane and diagnostics evidence.
4. Completed cutover checklist with Go/No-Go and rollback evidence.
5. Updated ADR/runbook docs where extracted flow is canonical.

---

## Risk Register (Phase 13)

| Risk | Impact | Mitigation |
|------|--------|------------|
| Baseline lock drift (`E7824`) before cutover | False readiness, broken strict gates | Mandatory WS0 lock-refresh + strict gate evidence |
| Extraction script divergence from real repo layout | Broken extracted repo | CI rehearsal lane with real extraction path |
| Package trust checks are metadata-only | Weak supply-chain guarantees | Implement cryptographic verification in WS1.3 |
| Cutover docs lag behind runtime state | Operator error in window | Governance sync in WS0.2 and WS3.1 |
| Rollback path not executable post-cutover | Prolonged outage | Mandatory WS3.2 rehearsal before closure |

---

## Definition of Done

1. WS0 baseline gates are green and evidenced.
2. Split rehearsal lane is green and repeatable.
3. Physical framework and project repositories are cut and validated.
4. Cutover checklist is fully completed with signed Go decision.
5. Post-cutover rollback rehearsal is green.
6. `adr/plan/v5-production-readiness.md` marks Phase 13 as completed.
