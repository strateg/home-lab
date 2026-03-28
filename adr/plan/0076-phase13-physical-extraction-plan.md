# ADR 0076: Phase 13 Physical Extraction Plan

**Date:** 2026-03-29
**Status:** Active
**Depends on:** ADR 0076 Stage 2 baseline (`submodule-first`)
**Supersedes:** none (extends `adr/plan/0076-multi-repo-extraction-plan.md`)

---

## Objective

Execute the **physical** split from current root repository into independent repositories:

1. `infra-topology-framework` (framework source of truth)
2. `home-lab` (project repository)

without breaking ADR0076 strict lock/compatibility guarantees.

---

## Baseline

Already completed (Stage 2):

- strict lock contract and diagnostics (`E781x`, `E782x`)
- lock/rollback/compatibility/audit gates in CI
- framework/project bootstrap utilities
- submodule-first operational flow and cutover evidence

Remaining for Phase 13:

- finalize physical ownership boundaries
- run production-grade cutover from root-development model to extracted repo model

---

## Scope

In scope:

1. history-preserving framework extraction
2. project repository bootstrap with strict lock verification
3. CI split and release/cutover checks across repositories
4. cutover execution and rollback rehearsal evidence

Out of scope:

1. ADR0053/ADR0047 policy decisions
2. functional topology model redesign
3. plugin architecture changes unrelated to repo split

---

## Priority Plan

## P0 - Contract and Governance Freeze

- [ ] Freeze Phase 13 contracts in ADR/plan docs and resolve contradictory statuses.
- [ ] Lock branch/tag policy for cutover window (`framework` tag + `project` lock update).
- [ ] Confirm strict gates list as mandatory Go/No-Go inputs.

Gate:

- `task framework:strict`
- `task framework:cutover-readiness-quick`

## P1 - Physical Extraction Execution

### WP1: Framework Repository Extraction

- [ ] Run `topology-tools/extract-framework-history.py` for history-preserving extraction.
- [ ] Validate extracted repository layout against `framework.yaml`.
- [ ] Run framework-side test gates in extracted repo.

Gate:

- `python topology-tools/extract-framework-history.py ...`
- `python -m pytest -o addopts= tests/plugin_api tests/plugin_contract tests/plugin_integration -q`

### WP2: Project Repository Bootstrap

- [ ] Run `topology-tools/bootstrap-project-repo.py` with framework submodule pointer.
- [ ] Seed project data (`instances`, `secrets`, `overrides`) and verify compile path.
- [ ] Generate and verify `framework.lock.yaml` in extracted project repo.

Gate:

- `python topology-tools/generate-framework-lock.py --topology topology/topology.yaml --force`
- `python topology-tools/verify-framework-lock.py --strict`
- `python topology-tools/compile-topology.py --topology topology/topology.yaml --strict-model-lock --secrets-mode passthrough --artifacts-root generated`

### WP3: Cross-Repo CI Hardening

- [ ] Enable framework release workflow from extracted framework repo.
- [ ] Enable project validate workflow with strict lock gates.
- [ ] Re-run compatibility matrix against target cutover versions.

Gate:

- `python topology-tools/validate-framework-compatibility-matrix.py`
- `python topology-tools/audit-strict-runtime-entrypoints.py`

## P2 - Cutover and Stabilization

### WP4: Production Cutover

- [ ] Execute `adr/plan/0076-phase13-cutover-checklist.md`.
- [ ] Publish release note for physical extraction cutover.
- [ ] Update operator docs to make extracted flow canonical.

### WP5: Post-Cutover Verification

- [ ] Run full readiness and release gates from project repo.
- [ ] Rehearse rollback to previous framework revision and restore.
- [ ] Record evidence paths in ADR plan and runbooks.

Gate:

- `task framework:cutover-readiness`
- `task framework:release-tests`
- `task validate:v5`
- `python topology-tools/rehearse-framework-rollback.py`

---

## Deliverables

1. Extracted `infra-topology-framework` repository with preserved history.
2. Extracted `home-lab` project repository with strict lock workflow.
3. CI workflows operating cross-repository (framework release + project verify).
4. Signed cutover checklist evidence and rollback rehearsal evidence.

---

## Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| History breaks during extraction | Use `extract-framework-history.py`; validate commit ancestry and blame |
| Lock drift across repositories | Enforce `verify-framework-lock --strict` in all project pipelines |
| Version skew after cutover | Run compatibility matrix before and after lock bump |
| Rollback not executable in pressure window | Mandatory `rehearse-framework-rollback.py` evidence before Go |
| Human process errors in cutover window | Use checklist with signed owner/approver checkpoints |

---

## Definition of Done

1. Physical repositories created and validated.
2. Strict gates green in extracted project flow.
3. Cutover checklist fully completed with evidence links.
4. Rollback rehearsal passed after cutover.
5. `adr/plan/v5-production-readiness.md` marks Phase 13 completed.
