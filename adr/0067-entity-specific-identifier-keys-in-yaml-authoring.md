# ADR 0067: Entity-Specific Identifier Keys in YAML Authoring

**Date:** 2026-03-10
**Status:** Implemented (Hard Cutover)
**Related:** ADR 0062 (Class-Object-Instance contract), ADR 0060 (Compiler and diagnostics contract), ADR 0063 (Plugin microkernel)

---

## Context

v5 authoring previously used a generic `id` key for heterogeneous entity types. This reduced readability in reviews and caused frequent ambiguity in tooling and diagnostics.

Target naming is entity-specific:

- class module key: `class`
- object module key: `object`
- instance binding row key: `instance`

Earlier transition plan considered dual-key compatibility (`id` + new key). This ADR records the final implemented decision: immediate hard cutover without legacy `id` support for class/object/instance entities.


---

## Decision

Adopt strict, non-transitional entity-specific keys.

### 1. Source YAML Contract (Strict)

- Class module files MUST define `class` and MUST NOT use `id` as entity identifier.
- Object module files MUST define `object` and MUST NOT use `id` as entity identifier.
- Instance binding rows MUST define `instance` and MUST NOT use `id` as entity identifier.

### 2. Loader/Validator Contract (No Fallback)

- Compiler and validation tooling read only `class`/`object`/`instance` for these entities.
- No dual-key fallback to legacy `id` is provided.
- Legacy inputs using `id` for these entities are invalid in v5 lane.

### 3. Runtime and Artifact Contract

- Effective topology output uses `instance` field for instance identity.
- Plugin validators and v5 scripts use `instance` in instance-binding rows.
- Class/object identity flows through `class` and `object` module keys.

### 4. Scope Boundaries

- This decision applies to class/object/instance modeling entities.
- Other domains that legitimately use `id` (for example capability catalog entries or plugin manifest fields) are out of scope for this ADR and remain unchanged.


---

## Consequences

### Positive

1. Source YAML is unambiguous by entity type.
2. Review and diagnostics readability improve.
3. Tooling paths are simpler (single key per entity type, no compatibility branch).

### Trade-offs and Risks

1. This is a breaking change for any external/legacy inputs still using `id` for class/object/instance.
2. Third-party scripts and cached fixtures must be updated to new keys.
3. Cross-version interoperability requires explicit migration rather than transparent fallback.

### Compatibility Impact

- No backward compatibility for legacy `id` in class/object/instance entities.
- v5 lane is intentionally strict to avoid long-lived transitional complexity.
- Migration is complete inside repository scope.

---

## References

- `adr/0062-modular-topology-architecture-consolidation.md`
- `adr/0060-yaml-to-json-compiler-diagnostics-contract.md`
- `adr/0063-plugin-microkernel-for-compiler-validators-generators.md`
- `v5/topology-tools/compile-topology.py`
- `v5/topology/instances/`
- `v5/topology/instances/_legacy-home-lab/instance-bindings.yaml` (historical archive)
- `v5/tests/test_plugin_registry.py`
