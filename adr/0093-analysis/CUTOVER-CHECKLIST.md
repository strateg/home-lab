# ADR 0093 CUTOVER CHECKLIST

## Schema completeness

- [ ] `ArtifactPlan` schema exists with required fields and enums.
- [ ] `ArtifactGenerationReport` schema exists with required summary fields.
- [ ] `schema_version` policy is documented and tested.

## Runtime completeness

- [ ] Pilot generators publish plan/report artifacts.
- [ ] Validate stage enforces schema for migrated families.
- [ ] Build/assemble stages consume generation metadata.

## Safety completeness

- [ ] Obsolete actions constrained to `retain|delete|warn`.
- [ ] `delete` path requires ownership proof.
- [ ] Default mode is non-destructive (`warn`) unless explicitly enabled.

## Migration completeness

- [ ] Family migration states are visible in diagnostics.
- [ ] Sunset policy for compatibility mode is documented.
- [ ] CI blocks regressions on migrated families.
