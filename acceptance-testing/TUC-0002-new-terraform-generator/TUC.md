# TUC-0002: New Terraform Generator

## Metadata

- `id`: `TUC-0002`
- `status`: `planned`
- `owner`: `topology-tools`
- `created_at`: `2026-04-08`
- `target_date`: `2026-04-10`
- `related_adrs`:
  - `adr/0074-v5-generator-architecture.md`
  - `adr/0092-smart-artifact-generation-and-hybrid-rendering.md`
  - `adr/0093-artifact-plan-schema-and-generator-runtime-integration.md`

## Objective

Validate that a newly introduced Terraform generator follows generator runtime contracts and emits deterministic artifacts.

## Scope

- In scope:
  - Plugin manifest wiring for the new generator.
  - Projection -> ArtifactPlan -> outputs contract.
  - Obsolete handling safety (`retain|warn|delete` with ownership proof).
  - Terraform output presence and semantic checks for the new family.
- Out of scope:
  - Real infra apply in production.
  - Cross-provider behavior not owned by the new generator.

## Preconditions

- New Terraform generator plugin exists in manifest and entry path resolves.
- `topology-tools/compile-topology.py` strict mode is functional.
- Framework lock is synchronized.

## Inputs

- Topology: `topology/topology.yaml`
- Plugin manifests:
  - `topology-tools/plugins/plugins.yaml`
  - `topology/object-modules/**/plugins.yaml`
- Expected generator tests:
  - `tests/plugin_integration/test_terraform_*.py`
- Optional exact plugin id (for quality gate):
  - env `NEW_TERRAFORM_PLUGIN_ID`

## Expected Outcomes

- Compile succeeds in strict mode.
- New generator publishes valid `artifact_plan` and `artifact_generation_report`.
- Generated Terraform files for the new family are deterministic across repeated runs.

## Acceptance Criteria

1. Integration tests for new Terraform generator pass.
2. Artifact contract schema checks pass (`artifact-plan`, `artifact-generation-report`).
3. No hard errors from artifact contract assembler and sunset validators.
4. TUC quality gate passes.

## Risks and Open Questions

- Final plugin id and artifact family may change during implementation.
- Provider-specific required fields may require additional test fixtures.
