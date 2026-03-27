# ADR 0058-0071 Remaining Work Backlog

- Date: 2026-03-12
- Revised: 2026-03-27
- Scope: ADR stack from `0058` to `0071`
- Goal: close remaining implementation and documentation gaps after plugin-first and sharded-instance cutovers
- Tracking: Phase 11 in `adr/plan/v5-production-readiness.md`

## Priority P0

### 1) Close ADR0069 status promotion
- Problem:
  - `adr/0069-plugin-first-compiler-refactor-and-thin-orchestrator.md` is still `Proposed` while cutover docs are `Completed`.
- Actions:
  - Change ADR0069 status to `Accepted`.
  - Mark status-promotion item as done in `adr/0069-analysis/CUTOVER-CHECKLIST.md`.
  - Add short evidence pointer block in ADR0069 (tests/artifacts/commit).
- Done criteria:
  - ADR0069 status is `Accepted`.
  - Checklist has no contradictory open item about promotion.
  - No doc conflicts across `adr/0069*`.

### 2) Finish ADR0068 hardening phase
- Problem:
  - `adr/0068-analysis/IMPLEMENTATION-PLAN.md` still has pending Phase 4/5 items.
  - `E6806` is defined in catalog but not fully enforced in runtime behavior as a final unresolved-placeholder guard.
- Actions:
  - Implement strict unresolved-placeholder detection (`E6806`) on effective compiled model.
  - Introduce enforcement mode policy (`warn` -> `warn+gate-new` -> `enforce`) in validator/plugin config.
  - Migrate plan text from old monolith wording to sharded instances reality (`instances_root`).
  - Extend tests for enforcement modes and `E6806`.
- Done criteria:
  - `E6806` covered by integration tests.
  - Enforce mode blocks unresolved placeholders deterministically.
  - ADR0068 implementation plan status updated from in-progress/pending to completed.

### 3) Remove stale contract examples after 0071/TUC updates
- Problem:
  - Some docs still reference outdated channel naming/examples.
- Actions:
  - Normalize examples to canonical ids (`inst.*`) where required by current rules.
  - Update `acceptance-testing/TUC-0001-router-data-channel-mikrotik-glinet/TUC.md` stale “planned/not created” lines.
  - Update outdated references to legacy `instance-bindings.yaml` in ADR0068 references.
- Done criteria:
  - No stale “planned” statement for already implemented TUC-0001 artifacts.
  - ADR examples align with current runtime and naming rules.

## Priority P1

### 4) Decide and lock ADR0063 YAML-validator tail
- Problem:
  - ADR0063 still has unchecked optional item: remaining YAML semantic checks migration.
- Actions:
  - Choose one:
    - complete migration to `validator_yaml`, or
    - mark as explicit non-goal/deferred with rationale and scope boundary.
  - Update ADR0063 checklist accordingly.
- Done criteria:
  - No ambiguous open checkbox in ADR0063 for active scope.
  - Decision documented and test impact stated.

### 5) Convert ADR0062 “planned” cross-layer refs to executable backlog
- Problem:
  - ADR0062 lists several cross-layer relations as `planned` without explicit implementation tracker.
- Actions:
  - Create focused execution backlog per relation (`storage.pool_ref`, `storage.volume_ref`, `network.bridge_ref`, `network.vlan_ref`, `observability.target_ref`, `operations.target_ref`, `power.source_ref`).
  - Define validator ownership and diagnostics per relation.
- Done criteria:
  - Each planned relation has owner, validator location, and acceptance test target.
  - Status can be tracked independently from ADR narrative text.

## Priority P2

### 6) Documentation consistency sweep for historical vs authoritative docs
- Problem:
  - Some analysis docs remain historical but can still increase cognitive load.
- Actions:
  - Add/refresh “historical/superseded” headers where missing.
  - Ensure `adr/PLUGIN-RUNTIME-ADR-MAP.md` remains the entry map for current authority.
- Done criteria:
  - Clear separation between authoritative ADRs and archival analysis docs.
  - Reduced contradictory guidance for maintainers.

## Suggested Execution Order

1. P0.1 ADR0069 status promotion
2. P0.3 stale example cleanup (fast consistency win)
3. P0.2 ADR0068 hardening (`E6806` + modes + tests)
4. P1.4 ADR0063 YAML-validator decision
5. P1.5 ADR0062 planned-relations execution backlog
6. P2.6 archival doc consistency sweep

## Exit Signal for This Backlog

- ADR0069 is `Accepted`.
- ADR0068 plan is marked completed with enforced `E6806` behavior.
- TUC/ADR examples are aligned with current runtime contracts.
- Remaining items are explicitly tracked as implementation backlog, not implicit ADR TODOs.
