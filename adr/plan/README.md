# Development Plans

This directory contains implementation plans for major development efforts.

## Active Plans

| Plan | Status | Description |
|------|--------|-------------|
| [0076-multi-repo-extraction-plan.md](0076-multi-repo-extraction-plan.md) | Draft | Framework extraction and multi-repo distribution |
| [0078-plugin-layering-and-v4-v5-migration-plan.md](0078-plugin-layering-and-v4-v5-migration-plan.md) | Active | Plugin level-boundary hardening + staged v4->v5 tooling migration |
| [v5-production-readiness.md](v5-production-readiness.md) | Active | Master plan for v5 deployment capability |
| [phase1-generator-framework.md](phase1-generator-framework.md) | Superseded | Generator plugin infrastructure (see ADR 0074) |

## Completed Plans

| Plan | Completed | Description |
|------|-----------|-------------|
| [0075-0074-master-migration-plan.md](0075-0074-master-migration-plan.md) | 2026-03-20 | Framework/project separation + generator completion |

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
