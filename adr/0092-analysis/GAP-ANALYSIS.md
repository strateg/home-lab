# ADR 0092 GAP ANALYSIS

## AS-IS

- Generator flow is mostly `projection -> template render -> file writes`.
- Explainability of generation decisions is limited.
- Obsolete detection and selective regeneration are not standardized.
- Mixed artifact families (Terraform/Ansible/docs) use inconsistent materialization approaches.

## TO-BE (ADR 0092)

- Planning-first generator behavior with explicit `ArtifactPlan`.
- Optional typed IR between projection and materialization.
- Hybrid rendering model (`jinja2|structured|programmatic`) with explicit mode per output.
- Deterministic generation evidence for audit/tests/build integration.

## Primary gaps

1. No normative planning contract before writes.
2. No common lifecycle metadata for generated/skipped/obsolete outputs.
3. No migration-safe protocol for obsolete deletion.
4. No explicit AI advisory trust boundary contract in runtime terms.

## Risks

- Over-scoping 0092 with implementation details better handled by 0093.
- Drift between planned architecture and incremental runtime adoption.
- Review complexity during mixed legacy/migrated generator period.

## Mitigation strategy

- Keep 0092 architecture-level and move strict runtime invariants to 0093.
- Enforce wave-based adoption and CI gates per migrated family.
- Require ownership proof + dry-run-safe defaults for obsolete management.
