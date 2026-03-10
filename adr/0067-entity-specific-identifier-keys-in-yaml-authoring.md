
# ADR 0067: Entity-Specific Identifier Keys in YAML Authoring

**Date:** 2026-03-10
**Status:** Proposed
**Related:** ADR 0062 (Class-Object-Instance contract), ADR 0060 (Compiler and diagnostics contract), ADR 0063 (Plugin microkernel)

---

## Context

In v5 authoring, many YAML documents still use a generic `id` key for all entity types.

Examples:

- class module: `id: class.router`
- object module: `id: obj.router.mikrotik.rb5009`
- instance binding row: `id: inst.device.router1`

This is consistent for tooling, but less explicit for humans during reviews and migrations.
Proposal from refactoring discussion:

- in class YAML use `class` instead of `id`
- in object YAML use `object` instead of `id`
- in instance YAML use `instance` instead of `id`

At the same time, current compiler/validators/plugins are largely built around canonical internal field `id`, and a hard cutover can cause avoidable breakage across:

- loaders and normalizers
- validation rules and diagnostics paths
- plugin contracts and tests
- migration tooling and docs

We need a controlled decision boundary: improve authoring clarity without destabilizing the v5 lane.

---

## Decision

Adopt a **phased migration** to entity-specific authoring keys, while keeping `id` as canonical internal representation during transition.

### 1. Authoring Contract (Transitional)

Allow both forms per entity:

- class YAML: `id` or `class`
- object YAML: `id` or `object`
- instance rows: `id` or `instance`

Normalization rule:

- canonical runtime field remains `id`
- compiler maps entity-specific key to canonical `id`

Conflict rule:

- if both keys are present and values differ, emit hard validation error

### 2. Canonical Runtime Contract (Unchanged)

Compiler output JSON, plugin context, and diagnostics contracts continue to use canonical `id` so existing plugin APIs remain stable in this ADR scope.

### 3. Migration Phases

1. Phase A (Compatibility): dual-key support in loaders/validators + conflict diagnostics.
2. Phase B (Repository migration): update authored YAML to entity-specific keys.
3. Phase C (Enforcement): warn on legacy `id` in source YAML.
4. Phase D (Optional hardening): decide whether legacy `id` remains forever for compatibility or is fully removed in a future ADR.

### 4. Acceptance Criteria for Phase B/C Start

Before moving past compatibility phase, require:

- no regression in compiler output parity (`--enable-plugins` vs baseline)
- updated contract and integration tests for dual-key handling
- explicit migration guidance in docs for contributors

---

## Consequences

### Positive

1. Source YAML becomes semantically clearer by entity type.
2. Review diffs become easier to reason about (field intent is explicit).
3. Migration risk is reduced by keeping internal canonical `id` during rollout.

### Trade-offs and Risks

1. Temporary dual-key support increases parser/validator complexity.
2. Ambiguity risk appears if contributors use mixed keys inconsistently.
3. Additional diagnostics and test matrix are required during transition.

### Compatibility Impact

- Backward compatibility is preserved in Phase A by accepting legacy `id`.
- No plugin API break is introduced in this ADR.
- Full deprecation/removal of legacy `id` is intentionally deferred to a separate explicit decision.

---

## References

- `adr/0062-modular-topology-architecture-consolidation.md`
- `adr/0060-yaml-to-json-compiler-diagnostics-contract.md`
- `adr/0063-plugin-microkernel-for-compiler-validators-generators.md`
- `v5/topology-tools/compile-topology.py`
