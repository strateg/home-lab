# ADR 0093 Schema Version Policy

## Scope

This policy covers:

- `schemas/artifact-plan.schema.json`
- `schemas/artifact-generation-report.schema.json`

and all runtime payloads emitted through ADR0093 generator contract keys.

## Current Baseline

- Writer baseline: `schema_version: "1.0"`
- Reader compatibility range: `>=1.0,<2.0`
- Runtime enforces `major == 1` for both ArtifactPlan and ArtifactGenerationReport payloads.

## Compatibility Rules

1. Minor updates (`1.x` -> `1.y`) are backward-compatible.
2. Readers must accept any `1.x` payload that passes schema validation.
3. Writers should emit the current baseline (`1.0`) until a newer minor is explicitly rolled out.
4. Major updates (`1.x` -> `2.0`) are breaking and require:
   - new schema files and migration notes,
   - dual-read support during migration window,
   - CI coverage for old+new sample payloads,
   - explicit ADR addendum or successor ADR.

## Runtime Behavior

- Unsupported major version is treated as contract validation error.
- Validation fails before downstream assemble/build stages consume payloads.
- Error text must include supported compatibility range for operator diagnostics.

## Change Process

For any schema version change:

1. Update this policy.
2. Update schema files and tests.
3. Update runtime validator compatibility logic.
4. Regenerate lock/evidence artifacts if framework contract changed.
