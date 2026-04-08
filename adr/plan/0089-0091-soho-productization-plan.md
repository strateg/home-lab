# ADR 0089-0091 SOHO Productization Plan

**Status:** Active  
**Last Updated:** 2026-04-09  
**Scope:** Close implementation gaps for ADR 0089 (product profile), ADR 0090 (operator lifecycle), ADR 0091 (readiness evidence).

## 1. Objective

Deliver a production-grade SOHO contract stack with:
- strict profile/bundle validation,
- stable operator task surface (`product:*`),
- machine-checkable readiness evidence and release gates.

## 2. Current State

Completed now (highest-priority closure):
- [x] Added canonical schemas for profile/readiness:
  - `schemas/product-profile.schema.json`
  - `schemas/operator-readiness.schema.json`
- [x] Added validator + policy-driven migration transition checks:
  - `topology-tools/plugins/validators/soho_product_profile_validator.py`
  - `topology-tools/data/soho-migration-state-policy.yaml`
- [x] Reserved/registered SOHO diagnostics and governance controls:
  - `topology-tools/data/error-catalog.yaml` (`E7941`, `E7942`, `E7947`, `W7941`, `W7942`)
  - `configs/quality/adr0088-governance-policy.yaml` (allowlist + thresholds)
- [x] Added contract/integration tests:
  - `tests/plugin_contract/test_soho_contract_schemas.py`
  - `tests/plugin_contract/test_error_catalog_ranges.py`
  - `tests/plugin_integration/test_soho_product_profile_validator.py`

Validation evidence:
- `task validate:default` passes.
- targeted SOHO contract/integration tests pass.

## 3. Deliverables

1. SOHO profile governance in validate lane (blocking in `migrated-hard`).
2. Operator lifecycle entrypoints (`product:*`) as thin orchestration wrappers.
3. Readiness evidence schemas + producers + gate validator.
4. Acceptance/TUC evidence mapping for ADR0091 domains.

## 4. Implementation Steps

### Step A: ADR0089 hardening completion
- [x] Add canonical profile and bundle source data:
  - `topology/product-profiles/soho.standard.v1.yaml`
  - `topology/product-bundles/*.yaml`
- [x] Wire discover/compile outputs for resolved profile + effective bundle graph.
- [ ] Enforce legacy sunset date policy (blocking after sunset).

### Step B: ADR0090 operator lifecycle surface
- [x] Add task wrappers:
  - `product:init`, `product:doctor`, `product:plan`, `product:apply`, `product:backup`, `product:restore`, `product:update`, `product:audit`, `product:handover`
- [x] Define explicit precondition/postcondition contracts per task.
- [x] Add contract tests proving read-only tasks have no side effects.

### Step C: ADR0091 readiness evidence stack
- [ ] Add missing schemas:
  - `schemas/backup-status.schema.json`
  - `schemas/restore-readiness.schema.json`
  - `schemas/support-bundle-manifest.schema.json`
- [ ] Generate required reports and handover package structure under `generated/<project>/product/`.
- [ ] Add readiness gate validator for completeness and blocking rules (`green/yellow/red`).
- [ ] Add sanitization tests for operator-facing artifacts (ADR0072 compliance).

## 5. Acceptance Criteria

- [ ] `task validate:default` passes with all new validators enabled.
- [ ] `product:doctor` returns normalized status (`green|yellow|red`) from machine-readable evidence.
- [ ] `product:handover` produces complete mandatory artifact set.
- [ ] Build/release is blocked on critical readiness failures (`E794x`) and missing mandatory evidence.
- [ ] TUC evidence coverage exists for ADR0091 required domains.

## 6. File Touch Plan

Primary files/directories for next wave:
- `topology/product-profiles/`
- `topology/product-bundles/`
- `schemas/`
- `scripts/orchestration/`
- `topology-tools/plugins/validators/`
- `tests/plugin_contract/`
- `tests/plugin_integration/`
- `acceptance-testing/`

## 7. Execution Order

1. Complete ADR0089 data-source closure (Step A).
2. Implement operator wrapper surface (Step B).
3. Implement evidence + release gate stack (Step C).
4. Run full validation + targeted acceptance tests and record evidence.
