# Release Notes: ADR0076 Production Cutover

**Date:** 2026-03-20
**Scope:** ADR0076 Wave 4 (Production Cutover)

## Summary

ADR0076 multi-repo flow promoted to production baseline for `home-lab`.

## Completed

1. Strict lock verification and rollback rehearsal are mandatory CI gates.
2. Compatibility matrix gate (`E7811/E7812/E7813`) is enforced in primary workflows.
3. Strict runtime entrypoint audit is wired into CI and local readiness checks.
4. Production announcement and freeze switch are recorded in `docs/framework/adr0076-cutover-state.json`.

## Operational Baseline

1. Legacy integrated flow is treated as frozen and no longer the rollout target.
2. Framework update flow is lock-first (`generate-framework-lock` -> `verify-framework-lock --strict` -> compile/validate).
3. Pre-release dry-run uses `docs/framework/CUTOVER-DRY-RUN-RUNBOOK.md`.

## References

- `adr/0076-framework-distribution-and-multi-repository-extraction.md`
- `adr/plan/0076-multi-repo-extraction-plan.md`
- `docs/framework/OPERATOR-WORKFLOWS.md`
