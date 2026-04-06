# ADR 0093 IMPLEMENTATION PLAN

## Wave 1 — Schema and invariants

1. Add JSON schema for `ArtifactPlan` and `ArtifactGenerationReport`.
2. Mark required fields and enums (`renderer`, obsolete `action`).
3. Add `schema_version` and compatibility policy.

## Wave 2 — Runtime integration

1. Publish plan/report artifacts from pilot generators.
2. Validate schema in runtime validate stage for migrated families.
3. Add family migration status output: `legacy|migrating|migrated`.

## Wave 3 — Build/assemble wiring

1. Consume generation metadata in assemble/build stages.
2. Publish summarized metadata for diagnostics/support bundles.
3. Add consistency checks across planned/generated/skipped/obsolete.

## Wave 4 — Compatibility sunset

1. Define sunset milestones for pilot families.
2. Promote migrated family missing plan/report to hard error.
3. Keep legacy mode only for non-migrated families until sunset.

## Wave 5 — Expansion

1. Roll out contract to additional generator families.
2. Keep parity tests for mixed mode until all target families migrated.
3. Remove compatibility shims after sunset completion.
