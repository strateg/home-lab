# Development Plans

This directory contains implementation plans for major development efforts.

## Active Plans

| Plan | Status | Description |
|------|--------|-------------|
| [v5-post-migration-roadmap-2026-03-27.md](v5-post-migration-roadmap-2026-03-27.md) | Active | Post-migration development roadmap: governance, ADR0079 docs/diagrams, production hardening |
| [v5-production-readiness.md](v5-production-readiness.md) | Active | Master plan for v5 deployment capability |
| [0083-0085-implementation-plan.md](0083-0085-implementation-plan.md) | Active | Cross-document analysis of ADR 0083/0084/0085 deploy-domain implementation |
| [0083-0085-unified-sequence.md](0083-0085-unified-sequence.md) | Active | Unified implementation sequence with concrete next steps |
| [PROJECT-SWOT-2026-04-09.md](PROJECT-SWOT-2026-04-09.md) | Active | Whole-project SWOT across architecture, runtime, deploy domain, productization, and governance |
| [PROJECT-TOWS-2026-04-09.md](PROJECT-TOWS-2026-04-09.md) | Active | Strategy matrix derived from the whole-project SWOT with prioritized actions |

## Completed Plans

| Plan | Completed | Description |
|------|-----------|-------------|
| [0075-0074-master-migration-plan.md](0075-0074-master-migration-plan.md) | 2026-03-20 | Framework/project separation + generator completion |
| [0078-plugin-layering-and-v4-v5-migration-plan.md](0078-plugin-layering-and-v4-v5-migration-plan.md) | 2026-03-22 | Plugin level-boundary hardening + staged v4->v5 migration closure |
| [0078-cutover-checklist.md](0078-cutover-checklist.md) | 2026-03-27 | Execution checklist for v4->v5 migration cutover closure |
| [0078-v4-validator-deprecation-matrix.md](0078-v4-validator-deprecation-matrix.md) | 2026-03-27 | Historical staged deprecation matrix (migration cutover closed; moved to backlog tracking) |
| [0078-v5-unified-plugin-refactor-prep.md](0078-v5-unified-plugin-refactor-prep.md) | 2026-03-22 | Unified plugin boundary hardening (WP6-WP10) |
| [0078-wave-d-v4-validator-mapping.md](0078-wave-d-v4-validator-mapping.md) | 2026-03-22 | v4 validator mapping and parity closure notes |
| [0076-multi-repo-extraction-plan.md](0076-multi-repo-extraction-plan.md) | 2026-03-24 | ADR0076 Stage 2 closure (completed in submodule-first mode) |
| [0076-phase13-physical-extraction-plan.md](0076-phase13-physical-extraction-plan.md) | 2026-04-09 | ADR0076 cutover physical framework/project repository extraction |
| [0076-phase13-cutover-checklist.md](0076-phase13-cutover-checklist.md) | 2026-04-09 | ADR0076 cutover execution checklist for physical extraction |
| [phase1-generator-framework.md](phase1-generator-framework.md) | Superseded | Generator plugin infrastructure (see ADR 0074) |
| [0081-framework-artifact-first-execution-plan.md](0081-framework-artifact-first-execution-plan.md) | 2026-04-09 | ADR0081 implementation plan for artifact-first framework + 1:N project repositories |
| [0089-0091-soho-productization-plan.md](0089-0091-soho-productization-plan.md) | 2026-04-09 | Implementation track for ADR0089 product profile, ADR0090 operator lifecycle, ADR0091 readiness evidence |

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
