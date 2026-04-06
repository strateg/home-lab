# OPERATOR WORKFLOW — ADR0088

## Canonical key usage (active lane)

Use canonical semantic keys only in topology source manifests:

1. Class manifests:
   - `@class`, `@version`, `@title`, `@layer`, optional `@summary`, optional `@description`, optional `@extends`.
2. Object manifests:
   - `@object`, `@extends`, `@version`, `@title`, `@layer`, optional `@summary`, optional `@description`.
3. Instance manifests:
   - `@instance`, `@extends`, `@version`, `@title`, `@layer`, optional `@summary`, optional `@description`.
4. Capability entries:
   - `@capability`, `@schema`, `@title`, optional `@summary`.

Legacy aliases (`class_ref`, `object_ref`, legacy capability alias forms) are not permitted in active lane source paths.

## Validation workflow

1. Standard validation:
   - `V5_SECRETS_MODE=passthrough python scripts/orchestration/lane.py validate-v5`
2. ADR0088 governance is executed by lane in default `enforce` mode.
3. Standalone governance report:
   - `python scripts/validation/validate_adr0088_governance.py --mode enforce --diagnostics-json build/diagnostics/report.json --output-json build/diagnostics/adr0088-governance-report.json`

## Rollback / emergency fallback (temporary)

If emergency work is blocked by governance strictness, temporary fallback is allowed only as an explicit operator decision:

1. Set temporary process-level override:
   - `ADR0088_GOVERNANCE_MODE=warn`
2. Re-run validation lane:
   - `ADR0088_GOVERNANCE_MODE=warn V5_SECRETS_MODE=passthrough python scripts/orchestration/lane.py validate-v5`
3. Create remediation task to restore `enforce` and close semantic debt.
4. Remove override and revalidate with default enforce mode before merge/cutover.

Fallback is intended for short-lived incident handling, not for routine development.
