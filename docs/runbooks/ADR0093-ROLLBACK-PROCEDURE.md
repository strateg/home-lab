# ADR0093 Rollback Procedure

## Purpose

This runbook defines the operational rollback flow for generators using
`migration_mode` under ADR0093.

## Policy Baseline

- ADR0093 compatibility mode is closed for target families.
- `migration_mode: legacy` is not allowed for scheduled ADR0093 targets and fails validate stage (`E9399`).
- Rollback is temporary and must converge back to `migrating`/`migrated`.

## Trigger Conditions

- Generator enters `migration_mode: rollback` after regression.
- CI reports rollback escalation warnings (`W9403`) or missing rollback metadata (`W9402`).
- Sunset hard-error (`E9399`) or artifact contract conflict (`E9391`) requires temporary rollback.

## Required Metadata

Update rollback policy (`topology-tools/data/generator-rollback-policy.yaml`) with:

- target generator plugin id
- `rollback_started_at` in `YYYY-MM-DD`
- optional adjusted `max_rollback_days` (default is `7`)

## Procedure

1. Set target generator to `migration_mode: rollback`.
2. Record `rollback_started_at` in rollback policy.
3. Run:
   - `V5_SECRETS_MODE=passthrough python scripts/orchestration/lane.py validate-v5`
   - relevant generator integration tests.
4. Verify evidence artifacts:
   - `dist/<project>/generator-readiness-evidence.json`
   - `dist/<project>/reports/restore-readiness.json`
   - `dist/<project>/reports/rollback-events.json`
5. Fix root cause in feature branch.
6. Return generator to `migration_mode: migrating` or `migrated`.
7. Remove rollback policy entry after successful verification.

## Escalation Rules

- `W9402`: rollback started date is missing; treat as governance gap.
- `W9403`: rollback duration exceeded policy threshold; escalate to maintainer review.
- Repeated `W9403` across releases blocks migration completion sign-off.
- `E9399`: target generator still in `legacy`; immediate remediation required (no legacy fallback path).

## Exit Criteria

- No generator remains in `migration_mode: rollback` for the release.
- Rollback policy contains no stale entries.
- Readiness artifacts report `status != blocked` for generator migration profile.
