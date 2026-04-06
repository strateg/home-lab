# ADR 0092 IMPLEMENTATION PLAN

## Wave 1 — Planning baseline

1. Introduce `ArtifactPlan` publication contract in generator runtime.
2. Add generation evidence publication hooks.
3. Pilot with Terraform MikroTik + Terraform Proxmox generators.
4. Add CI checks for `projection -> plan -> outputs` consistency.

## Wave 2 — IR foundation

1. Define typed IR families for migrated Terraform generators.
2. Add IR versioning and compatibility checks.
3. Add regression tests for `projection -> IR` stability.

## Wave 3 — Structured Ansible

1. Migrate inventory/group_vars/host_vars to structured serialization where applicable.
2. Preserve Jinja2 for human-oriented docs/runbooks.
3. Validate parity against existing generated baselines.

## Wave 4 — Hybrid expansion

1. Introduce selective programmatic emission for complex Terraform fragments.
2. Add family-level ownership and obsolete policy checks.
3. Harden explainability reports for build/audit consumption.

## Wave 5 — Advisory sandbox

1. Add optional AI advisory lane with strict redaction and trust boundaries.
2. Keep advisory outputs non-authoritative by default.
3. Require full deterministic validation pipeline before any publish path.
