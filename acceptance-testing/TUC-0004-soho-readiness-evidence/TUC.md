# TUC-0004: SOHO Readiness Evidence and Handover Gate

## Metadata

- `id`: `TUC-0004`
- `status`: `implemented`
- `owner`: `architecture-runtime`
- `created_at`: `2026-04-09`
- `target_date`: `2026-04-12`
- `related_adrs`: `adr/0089-soho-product-profile-and-bundle-contract.md`, `adr/0090-soho-operator-lifecycle-and-task-ux-contract.md`, `adr/0091-soho-readiness-evidence-and-handover-artifacts.md`

## Objective

Prove that ADR0091 readiness evidence and handover package contracts are emitted deterministically and enforce release-time blocking on critical readiness failures.

## Scope

- In scope:
  - `product:doctor` normalized status derivation from machine-readable evidence.
  - `product:handover` package completeness gate (`generated/<project>/product/handover` + `generated/<project>/product/reports`).
  - build-stage SOHO readiness diagnostics (`E7943..E7946`) and report generation.
- Out of scope:
  - live infra apply execution.
  - hardware-discovery and external monitoring backends.

## Preconditions

- v5 plugin-first runtime is active.
- `task validate:default` passes.
- Build lane can write generated artifacts under `generated/home-lab/`.

## Inputs

- Source inputs:
  - `topology/topology.yaml`
  - `projects/home-lab/project.yaml`
- Runtime/build settings:
  - `taskfiles/product.yml`
  - `topology-tools/plugins/plugins.yaml`
- Fixtures/test data:
  - `tests/plugin_integration/test_soho_readiness_builder.py`
  - `tests/plugin_integration/test_product_doctor_script.py`
  - `tests/plugin_integration/test_product_handover_check_script.py`

## Expected Outcomes

- Operator package artifacts are generated in deterministic structure.
- `product:doctor` reports `green|yellow|red` and source evidence path.
- Missing mandatory evidence triggers blocking diagnostics in SOHO readiness builder.

## Acceptance Criteria

1. `task product:doctor` prints normalized status/source JSON and writes `build/diagnostics/product-doctor.json`.
2. `task product:handover` validates mandatory package files through `handover_check.py` before bundle creation.
3. Integration tests validate success and failure paths for SOHO readiness package + doctor/handover helpers.
4. ADR0091 D3 evidence domains are present in machine-readable operator readiness output.

## Risks and Open Questions

- Current baseline may stay `yellow/partial` without explicit migrated-hard profile in `project.yaml`.
- Migration-window policy for `partial` completeness remains configurable and should be revisited before production cutover.
