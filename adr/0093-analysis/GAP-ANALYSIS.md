# ADR 0093 GAP ANALYSIS

**Last updated:** 2026-04-06
**Status:** Gaps addressed in ADR update

## AS-IS

- No strict runtime schema contract for `ArtifactPlan` and generation reports.
- Validate/build stages do not consistently consume generation metadata.
- Legacy and migrated generators are not explicitly state-tracked.
- Obsolete actions lack unified safety protocol.

## TO-BE (ADR 0093)

- Strict schema and invariants for `ArtifactPlan` and `ArtifactGenerationReport`.
- Compatibility mode with explicit migration states and sunset.
- Validate/assemble/build consumption of generation metadata is mandatory for migrated families.
- Obsolete handling governed by action taxonomy and ownership proof.
- **NEW:** Ownership proof contract with three verification methods.
- **NEW:** Concrete sunset milestones per artifact family.
- **NEW:** Rollback procedure with escalation policy.

## Primary Gaps — Status

| Gap | Description | Status | Addressed By |
| --- | ----------- | ------ | ------------ |
| G1 | Required fields/versioning not enforced | **CLOSED** | D9 (schema invariants) |
| G2 | No standardized migrated family status model | **CLOSED** | D10, D14 (migration_mode states) |
| G3 | CI gates for ownership-safe deletion missing | **CLOSED** | D12 (ownership proof contract) |
| G4 | Compatibility mode has no contractual sunset | **CLOSED** | D13 (concrete sunset milestones) |
| G5 | No rollback procedure | **CLOSED** | D14 (rollback procedure) |

## Residual Risks

| Risk | Probability | Impact | Mitigation |
| ---- | ----------- | ------ | ---------- |
| Schema drift between plan/report and runtime | Medium | High | Couple schema + runtime + tests in single PR |
| Ownership proof false negatives | Low | High | Three verification methods (plan + prefix + marker) |
| Sunset too aggressive for complex families | Low | Medium | 2-week grace period, warnings before hard error |
| Rollback used to avoid migration | Low | Low | 7-day escalation policy |

## Mitigation Strategy

1. **Schema + Runtime coupling**: All schema changes must include runtime implementation and tests in same PR.
2. **Ownership proof**: Three-method verification ensures reliable ownership detection.
3. **Sunset policy**: Graduated enforcement (warning → blocking warning → hard error).
4. **Rollback limits**: Automatic escalation prevents permanent rollback state.

## Acceptance Criteria Mapping

| Gap | Acceptance Criteria |
| --- | ------------------- |
| G1 | AC-1, AC-2 (schemas exist) |
| G2 | AC-13 (migration status visible) |
| G3 | AC-7 through AC-11 (ownership proof) |
| G4 | AC-12 through AC-15 (sunset milestones) |
| G5 | AC-16 through AC-20 (rollback procedure) |
