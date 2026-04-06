# ADR 0093 GAP ANALYSIS

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

## Primary gaps

1. Required fields/versioning not enforced.
2. No standardized migrated family status model.
3. CI gates for ownership-safe deletion are missing.
4. Compatibility mode has no contractual sunset.

## Risks

- Contract drift between schemas and runtime.
- Long-lived mixed mode due to unclear migration deadlines.
- False confidence if schema exists but runtime does not enforce it.

## Mitigation strategy

- Couple schema updates to runtime+tests in one change set.
- Define migration state + sunset per artifact family.
- Make ownership-safe obsolete checks part of blocking CI gates.
