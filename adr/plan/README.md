# Development Plans

This directory contains implementation plans for major development efforts.

## Active Plans

| Plan | Status | Description |
|------|--------|-------------|
| [0076-multi-repo-extraction-plan.md](0076-multi-repo-extraction-plan.md) | Draft | Framework extraction and multi-repo distribution |
| [v5-production-readiness.md](v5-production-readiness.md) | Active | Master plan for v5 deployment capability |
| [phase1-generator-framework.md](phase1-generator-framework.md) | Superseded | Generator plugin infrastructure (see ADR 0074) |

## Completed Plans

| Plan | Completed | Description |
|------|-----------|-------------|
| [0075-0074-master-migration-plan.md](0075-0074-master-migration-plan.md) | 2026-03-20 | Framework/project separation + generator completion |
| [0078-plugin-layering-and-v4-v5-migration-plan.md](0078-plugin-layering-and-v4-v5-migration-plan.md) | 2026-03-22 | Plugin level-boundary hardening + staged v4->v5 migration closure |
| [0078-cutover-checklist.md](0078-cutover-checklist.md) | 2026-03-27 | Execution checklist for v4->v5 migration cutover closure |
| [0078-v4-validator-deprecation-matrix.md](0078-v4-validator-deprecation-matrix.md) | 2026-03-27 | Historical staged deprecation matrix (migration cutover closed; moved to backlog tracking) |
| [0078-v5-unified-plugin-refactor-prep.md](0078-v5-unified-plugin-refactor-prep.md) | 2026-03-22 | Unified plugin boundary hardening (WP6-WP10) |
| [0078-wave-d-v4-validator-mapping.md](0078-wave-d-v4-validator-mapping.md) | 2026-03-22 | v4 validator mapping and parity closure notes |

## Migration Agreement (0075/0078)

1. `0075-0074-master-migration-plan.md` is historical closure of framework/project split + generator completion.
2. `0078-v5-unified-plugin-refactor-prep.md` and `0078-wave-d-v4-validator-mapping.md` are completed implementation artifacts (inventory/mapping/parity inputs).
3. `0078-plugin-layering-and-v4-v5-migration-plan.md` is completed migration closure and policy baseline.
4. `0078-cutover-checklist.md` was the execution source for final cutover actions and is now completed.
5. Active migration/runtime evolution after cutover follows ADR0080 artifacts and current active plans.

## Plan Structure

Each plan follows this format:

1. **Objective** - What we're trying to achieve
2. **Current State** - Where we are now
3. **Deliverables** - What will be produced
4. **Implementation Steps** - How to do it
5. **Acceptance Criteria** - How to know we're done
6. **Files to Create/Modify** - Specific changes needed

## Tracking Progress

- Update checkboxes in plan files as tasks complete
- Create GitHub Issues for each phase if using issue tracking
- Update ADR statuses when milestones are reached

## Relationship to ADRs

Plans implement decisions recorded in ADRs:
- Plans are tactical (how to do it)
- ADRs are strategic (what and why)

When a plan completes, update the related ADR status.
