# ADR 0096 Schema Version Policy

## Scope

This policy covers the ADR0096 machine-readable contract:

- `docs/ai/ADR-RULE-MAP.yaml`
- `schemas/adr-rule-map.schema.json`
- `scripts/validation/validate_agent_rules.py`
- `scripts/validation/report_adr_rule_coverage.py`

and any tooling that consumes `source_adr`, adapter registry, or scoped rule-pack metadata from the rule map.

## Current Baseline

- Writer baseline: `schema_version: 1`
- Reader compatibility epoch: `1`
- Current repository tooling expects the ADR rule map to remain in compatibility epoch `1`.

## Compatibility Rules

1. `schema_version` is a compatibility epoch, not a changelog counter for every additive field.
2. Additive schema changes may stay on epoch `1` only when repository readers and writers are updated atomically in the same change set.
3. New required fields may stay on epoch `1` only when:
   - the repository-owned writer (`docs/ai/ADR-RULE-MAP.yaml`) is updated together with the schema and validator/tests;
   - no external compatibility promise outside the repository is being preserved.
4. Breaking changes require `schema_version` bump to the next integer when they would invalidate existing external consumers or require a migration window.
5. A future epoch `2` change requires:
   - updated schema and validator logic,
   - migration notes for adapter/tooling consumers,
   - explicit regression coverage for supported old/new inputs during transition,
   - ADR0096 addendum or successor ADR if the contract meaning changes materially.

## Runtime / Validation Behavior

- `task validate:agent-rules` and `task validate:agent-rules-strict` enforce schema conformance for the current rule map.
- `task validate:agent-rule-coverage` is diagnostic-only and must keep consuming the current compatibility epoch.
- Unsupported schema epochs are treated as validation failures, not soft warnings.

## Change Process

For any ADR0096 schema contract change:

1. Update this policy.
2. Update `docs/ai/ADR-RULE-MAP.yaml` when the canonical writer shape changes.
3. Update `schemas/adr-rule-map.schema.json`.
4. Update validators/reporters/tests that consume the rule map.
5. Update ADR0096 status/SWOT artifacts when the change closes or opens a tracked governance gap.
