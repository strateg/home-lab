# CUTOVER CHECKLIST — ADR 0088

## Contract & Schema

- [ ] `semantic-keywords` schema exists and is validated in CI.
- [ ] Canonical service keys and aliases are documented and versioned.
- [ ] `@version` is required and validated for class/object/instance manifests.
- [ ] `@capability` is required and validated for capability declarations.
- [ ] `@schema` is required and validated when `@capability` is declared.
- [ ] `@title` is required and validated for class/object/instance/capability manifests.
- [ ] `@summary` is supported and normalized (nullable).
- [ ] `@layer` is required and validated for class/object/instance manifests.
- [ ] `@description` is supported and normalized (nullable).
- [ ] Instance shard grouping metadata uses canonical `@group`.
- [ ] Plain `group` key is rejected/forbidden in active instance shard contract.
- [ ] Alias collisions are rejected by validator diagnostics.
- [ ] Context-scoped semantic mapping is enforced (`@capability/@schema` only in capability-entry context).
- [ ] ADR 0067 partial-supersede boundaries are documented and accepted.

## Compiler/Runtime

- [ ] Class/object/instance loaders use semantic resolver (no hardcoded literals in critical path).
- [ ] Mixed canonical+alias keys in one node fail deterministically.
- [ ] Strict YAML loader is active (duplicate key = error) in compile/validate/generate runtime path.
- [ ] Effective JSON includes lineage/materialization fields for all entities.
- [ ] Effective JSON compatibility bridge fields are present/removed according to migration mode gates.

## Validation

- [ ] Class inheritance DAG checks (existence + cycle detection) enabled.
- [ ] `@extends` target-type checks enabled (`instance->object`, `object->class`, `class->class`).
- [ ] Instance object/class materialization consistency check enabled.

## Topology Migration

- [ ] All framework class/object manifests migrated to canonical keys.
- [ ] Project manifests/instances migrated to canonical keys.
- [ ] Instance shard headers are canonicalized to `@instance/@extends/@group/@version`.
- [ ] Legacy aliases either absent or explicitly allowed by configured mode.
- [ ] Migration scope excludes `archive/v4/` unconditionally (immutable reference) and excludes `generated/`/historical artifacts.
- [ ] Active instances root (`projects/*/topology/instances`) has zero legacy `class_ref/object_ref` fields.
- [ ] Legacy semantic key footprint is explicitly boundary-scoped (e.g., `_legacy`) and excluded from active-lane compliance KPIs.

## Post-cutover quality governance

- [ ] Metadata coverage targets are defined for class/object required semantic metadata and tracked in CI.
- [ ] Metadata gate policy is phased (`warn -> gate-new -> enforce`) and documented.
- [ ] Warning governance is explicit: accepted warning classes and escalation rules are defined.
- [ ] `W7816` duplicate-IP warning profile is either accepted by policy or escalated by rule (no implicit limbo state).

## Quality Gates

- [ ] `python topology-tools/compile-topology.py` passes.
- [ ] `python scripts/orchestration/lane.py validate-v5` passes.
- [ ] `python -m pytest tests -q` passes.
- [ ] Effective JSON contract tests pass with lineage assertions.
- [ ] E880x ADR0088 diagnostics are present in error catalog and covered by tests.

## Operational Readiness

- [ ] Migration mode switched to `enforce` in target environment.
- [ ] Operator docs updated with canonical key examples.
- [ ] Rollback plan documented (mode fallback to compatibility if needed).
