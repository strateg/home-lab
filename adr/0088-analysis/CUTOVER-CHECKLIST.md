# CUTOVER CHECKLIST — ADR 0088

**Status:** Implemented (2026-04-29)

## Contract & Schema

- [x] `semantic-keywords` schema exists and is validated in CI. (`topology/semantic-keywords.yaml`)
- [x] Canonical service keys and aliases are documented and versioned.
- [x] `@version` is required and validated for class/object/instance manifests.
- [x] `@capability` is required and validated for capability declarations.
- [x] `@schema` is required and validated when `@capability` is declared.
- [x] `@title` is required and validated for class/object/instance/capability manifests.
- [x] `@summary` is supported and normalized (nullable).
- [x] `@layer` is required and validated for class/object/instance manifests.
- [x] `@description` is supported and normalized (nullable).
- [x] Instance shard grouping metadata uses canonical `@group`.
- [x] Plain `group` key is rejected/forbidden in active instance shard contract.
- [x] Alias collisions are rejected by validator diagnostics.
- [x] Context-scoped semantic mapping is enforced (`@capability/@schema` only in capability-entry context).
- [x] ADR 0067 partial-supersede boundaries are documented and accepted.

## Compiler/Runtime

- [x] Class/object/instance loaders use semantic resolver (no hardcoded literals in critical path).
- [x] Mixed canonical+alias keys in one node fail deterministically.
- [x] Strict YAML loader is active (duplicate key = error) in compile/validate/generate runtime path.
- [x] Effective JSON includes lineage/materialization fields for all entities.
- [x] Effective JSON compatibility bridge fields are present/removed according to migration mode gates.

## Validation

- [x] Class inheritance DAG checks (existence + cycle detection) enabled.
- [x] `@extends` target-type checks enabled (`instance->object`, `object->class`, `class->class`).
- [x] Instance object/class materialization consistency check enabled.

## Topology Migration

- [x] All framework class/object manifests migrated to canonical keys.
- [x] Project manifests/instances migrated to canonical keys.
- [x] Instance shard headers are canonicalized to `@instance/@extends/@group/@version`.
- [x] Legacy aliases either absent or explicitly allowed by configured mode.
- [x] Migration scope excludes `archive/v4/` unconditionally (immutable reference) and excludes `generated/`/historical artifacts.
- [x] Active instances root (`projects/*/topology/instances`) has zero legacy `class_ref/object_ref/group` fields.
- [x] Legacy semantic key footprint is explicitly boundary-scoped (e.g., `_legacy`) and excluded from active-lane compliance KPIs.

## Post-cutover quality governance

- [x] Metadata coverage targets are defined for class/object required semantic metadata and tracked in CI.
- [x] Metadata gate policy is phased (`warn -> gate-new -> enforce`) and documented.
- [x] Warning governance is explicit: accepted warning classes and escalation rules are defined.
- [x] `W7816` duplicate-IP warning profile is either accepted by policy or escalated by rule (no implicit limbo state).

## Quality Gates

- [x] `python topology-tools/compile-topology.py` passes.
- [x] `python scripts/orchestration/lane.py validate-v5` passes.
- [x] `python -m pytest tests -q` passes.
- [x] Effective JSON contract tests pass with lineage assertions.
- [x] E880x ADR0088 diagnostics are present in error catalog and covered by tests.
- [x] E8807 (`legacy group` -> `@group`) is present in error catalog and covered by tests.

## Operational Readiness

- [x] Migration mode switched to `enforce` in target environment.
- [x] Operator docs updated with canonical key examples.
- [x] Rollback plan documented (mode fallback to compatibility if needed).

---

## Completion Evidence (2026-04-29)

- `topology/semantic-keywords.yaml` — canonical registry with version 1.0.0
- 151 instance files using `@instance/@extends/@group/@version` format
- 51 class files with canonical keys
- 120 object files with canonical keys
- All validators enforcing semantic contracts
