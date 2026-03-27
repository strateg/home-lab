# V5 Post-Migration Development Roadmap

**Date:** 2026-03-27
**Status:** Active
**Purpose:** Convert completed v4->v5 migration into production-ready, fully documented, and governance-clean operating model.

---

## 1. Source Documents (Analyzed)

1. `adr/REGISTER.md`
2. `adr/plan/v5-production-readiness.md`
3. `adr/0079-v5-documentation-and-diagram-generation-migration.md`
4. `adr/0079-analysis/IMPLEMENTATION-PLAN.md`
5. `adr/0080-analysis/IMPLEMENTATION-PLAN.md`
6. `adr/0080-analysis/CUTOVER-CHECKLIST.md`
7. `adr/plan/0078-plugin-layering-and-v4-v5-migration-plan.md`
8. `adr/plan/0078-cutover-checklist.md`

---

## 2. Baseline (As-Is)

1. ADR0078 migration cutover is closed.
2. ADR0080 runtime lifecycle/contracts are implemented and gated.
3. Root layout is canonical (`topology/`, `topology-tools/`, `projects/`, `tests/`).
4. Legacy v4 is archived under `archive/v4` for parity/rollback reference only.
5. Remaining work is post-migration productization, not structural v4->v5 migration.

---

## 3. Priority Stack

## P0 (Mandatory)

1. ADR and plan governance cleanup (status consistency, stale `planned` markers).
2. Placeholder hardening completion (`E6806` strict deterministic enforcement).
3. CI policy freeze for v5-default lane and legacy-v4 maintenance-only lane.

## P1 (High)

1. ADR0079 delivery: docs/diagram migration to projection-first v5 generators.
2. Operational runbook closure for deployment, backup/restore, DR, monitoring alerts.

## P2 (Decision/Expansion)

1. ADR0053 final decision (`native` vs `dist` execution default).
2. ADR0047 observability modularization: execute next phases or formally defer.

## P3 (Optional Strategic)

1. ADR0076 physical framework/project repository extraction (if business-required).

---

## 4. Execution Waves

## Wave A - Governance and Contract Closure (P0)

- [x] Reconcile `adr/REGISTER.md` statuses with implemented state and completed plans.
- [x] Sweep ADR docs for stale contradictory `planned` statements and add historical markers where needed.
- [x] Consolidate active delivery source to:
  - [x] `adr/plan/v5-production-readiness.md`
  - [x] this roadmap
- [x] Define closure decisions for older Proposed ADRs (`0031`, `0032`, `0033`, `0034`, `0035`, `0036`, `0045`, `0049`) as accepted/deferred/superseded with explicit references.

**Gate:**

1. `python -m pytest -o addopts= tests/test_root_layout_docs_contract.py tests/test_agent_instruction_sync.py -q`

## Wave B - E6806 and Strict Identity Enforcement (P0)

- [x] Replace remaining placeholder identities in active strict profiles.
- [x] Enforce unresolved-placeholder blocking in strict mode.
- [x] Add CI gate for unresolved placeholders on strict profiles.
- [x] Document repeatable identity capture workflow.

**Gate:**

1. `task validate:v5`
2. `task framework:cutover-readiness-quick`

## Wave C - ADR0079 Documentation/Diagram Migration (P1)

- [ ] Implement missing projection modules from `adr/0079-analysis/IMPLEMENTATION-PLAN.md`.
- [ ] Migrate template set from minimal v5 coverage to planned full set.
- [ ] Implement icon manager and icon mapping registry.
- [ ] Add Mermaid render validation quality gate to CI.
- [ ] Lock deterministic docs generation between repeated runs.

**Gate:**

1. `task framework:release-tests`
2. `task ci:local-with-legacy`

## Wave D - Operational Readiness Runbooks (P1)

- [ ] Publish/refresh deployment procedures (Proxmox, MikroTik, services).
- [ ] Publish troubleshooting playbooks per infrastructure component.
- [ ] Publish backup/restore and DR procedures.
- [ ] Publish monitoring alert runbooks.
- [ ] Validate end-to-end service deployment chain with documented evidence.

**Gate:**

1. `task acceptance:tests-all`
2. `task framework:cutover-readiness`

## Wave E - Policy Decisions and Expansion (P2/P3)

- [ ] ADR0053: lock execution default (`native` or `dist`) and align task/docs/CI.
- [ ] ADR0047: choose execute-now vs deferred trigger and update status accordingly.
- [ ] ADR0076: decide whether to start physical multi-repo extraction.

**Gate:**

1. ADR status updates committed with linked evidence.
2. No regression in `task ci:local-with-legacy`.

---

## 5. Definition of Done (Roadmap)

1. Active ADR/plan statuses are coherent and non-contradictory.
2. Strict placeholder policy (`E6806`) is enforced and CI-gated.
3. ADR0079 docs/diagram migration scope is delivered and quality-gated.
4. Operational runbooks exist and are validated by executable gates.
5. Decision ADRs (`0053`, `0047`, `0076`) are explicitly resolved (implement/defer) with documented rationale.
