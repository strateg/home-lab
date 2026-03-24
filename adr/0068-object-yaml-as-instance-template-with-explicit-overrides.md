# ADR 0068: Object YAML Template with Typed Instance Placeholders

**Date:** 2026-03-10
**Status:** Accepted (E6806 enforcement active; Phase 3 `enforce` mode)
**Extends:** ADR 0062 (Class-Object-Instance merge contract)
**Related:** ADR 0067 (Entity-specific keys in YAML authoring)
**Implementation Plan:** `adr/0068-analysis/IMPLEMENTATION-PLAN.md`
**Enforcement:** `enforce` mode active (2026-03-24)

---

## TL;DR

1. Object YAML uses inline placeholders in normal fields: `@required:<format>` or `@optional:<format>`.
2. Instance provides only explicit values in `instance_overrides`.
3. Instance can override only placeholder-marked paths.
4. Required placeholders must always be resolved by instance values.
5. All placeholder formats are validated via `v5/topology-tools/data/instance-field-formats.yaml`.
6. Final effective model must not contain unresolved placeholders.

---

## Context

Need a contract where:

1. Object YAML stays visually normal (no wrapper structures for each field).
2. Instance provides only explicit per-instance values.
3. Compiler knows which object fields must be overridden and validates value format.

Previous path-list and envelope variants are more fragile or verbose in authoring.

---

## Decision

### 1. Object Uses Typed Placeholder Markers in Normal Fields

Overridable fields are declared directly as scalar placeholders:

```yaml
defaults:
  hardware_identity:
    serial_number: @required:string
    mac_addresses:
      wan: @required:mac
      lan1: @optional:mac
  management:
    ipv4: @required:ipv4
```

Marker grammar:

`@(required|optional):<format>`

Rules:

1. Field remains a regular YAML scalar.
2. Placeholder marks field as instance-overridable.
3. `required` means value MUST be provided by instance.
4. `optional` means value MAY be provided by instance.

### 2. Instance Provides Explicit Values

```yaml
instance_overrides:
  defaults:
    hardware_identity:
      serial_number: GL-AXT-001122
      mac_addresses:
        wan: "AA:BB:CC:DD:EE:01"
    management:
      ipv4: 192.168.20.1
```

Rules:

1. Instance may override only placeholder-marked paths.
2. Required placeholders must all be resolved by instance values.
3. Instance must not introduce new paths absent from object template.

### 3. Format Definitions Are Centralized

Field formats are defined in a single registry:

`v5/topology-tools/data/instance-field-formats.yaml`

This file is the source of truth for `<format>` tokens in placeholders.

Initial baseline formats:

- `string`
- `int`
- `number`
- `bool`
- `mac`
- `ipv4`
- `ipv6`
- `cidr`
- `hostname`
- `uri`
- `iso8601`

Class/object contracts may further restrict usage, but base format semantics come from this registry.

### 4. Compiler and Validation Semantics

Compiler/validator MUST enforce:

1. Placeholder syntax validity.
2. Required placeholder resolution in each instance.
3. Override path is placeholder-marked in object.
4. Instance value matches registry-defined format.
5. Effective model contains no unresolved placeholders after merge.
6. ADR 0062 class invariants remain enforced.

### 5. Effective Merge Order

Merge stays compatible with ADR 0062 and is clarified:

`Class.defaults -> Object.template -> Instance.instance_overrides`

Object placeholders are authoring-time template markers and must not survive into emitted effective JSON.

---

## Author Workflow

1. Object author places placeholders in fields that vary per instance.
2. Instance author fills only required/needed values under `instance_overrides`.
3. Reviewer checks that:
   - required placeholders are resolved,
   - no non-placeholder path is overridden,
   - values match declared formats.
4. Compiler validates and emits a placeholder-free effective model.

---

## Edge Cases (Normative)

1. `required` + missing override -> invalid.
2. `required` + `null` override -> invalid.
3. `optional` + missing override -> valid.
4. `optional` + `null` override -> invalid (use omission for "not provided").
5. Empty string is treated as a value and validated by the declared format.
6. Array/list overrides are full-value replacement only; partial index-based overrides are not supported in this ADR.

---

## Consequences

### Positive

1. Object YAML remains readable and close to natural shape.
2. Required per-instance data is explicit and machine-checkable.
3. Format validation becomes consistent across all objects.
4. Review checklist is simpler: placeholder path, required coverage, format validity.

### Trade-offs and Risks

1. Placeholder token is a reserved string pattern.
2. Compiler must implement placeholder parsing and normalization.
3. Migration is needed for fields currently using `null`/TODO values.
4. Authors must learn placeholder grammar and format names.

### Compatibility Impact

1. Legacy instance overrides of non-marked fields become invalid.
2. Objects needing per-instance values must migrate to placeholder markers.
3. Existing unresolved placeholders become hard errors at compile time.

---

## Migration Plan

1. Phase 1 (`warn`): detect violations and report, no hard fail.
2. Phase 2 (`warn+gate-new`): new/changed entities must comply; legacy debt tracked.
3. Phase 3 (`enforce`): all violations are compile-time errors.

Suggested acceptance criteria for status change to `Accepted`:

1. Validator supports all normative rules in this ADR.
2. Error catalog codes are implemented and documented.
3. Target topology set compiles with zero placeholder-policy violations.

---

## Validation Error Catalog (Minimum)

- `E6801_INVALID_PLACEHOLDER_SYNTAX`
- `E6802_REQUIRED_OVERRIDE_MISSING`
- `E6803_OVERRIDE_PATH_NOT_MARKED`
- `E6804_OVERRIDE_PATH_NOT_FOUND`
- `E6805_FORMAT_VALIDATION_FAILED`
- `E6806_UNRESOLVED_PLACEHOLDER_AFTER_MERGE`

---

## Rejected Alternatives

1. Path allowlist (`overridable_paths`) only: workable, but separates intent from field location and increases review effort.
2. Envelope wrapper per field: explicit, but too verbose and harms YAML readability.

Inline typed placeholders were chosen because they keep intent near the data while preserving deterministic validation.

---

## References

- `adr/0062-modular-topology-architecture-consolidation.md`
- `adr/0067-entity-specific-identifier-keys-in-yaml-authoring.md`
- `adr/0068-analysis/IMPLEMENTATION-PLAN.md` (implementation status)
- `adr/0068-analysis/OPERATOR-WORKFLOW.md` (operator guide for placeholder resolution)
- `v5/topology/object-modules/`
- `v5/topology/instances/`
- `v5/topology/instances/_legacy-home-lab/instance-bindings.yaml` (historical archive)
- `v5/topology-tools/data/instance-field-formats.yaml`
- `v5/topology-tools/plugins/validators/instance_placeholder_validator.py`
- `v5/topology-tools/compile-topology.py`
