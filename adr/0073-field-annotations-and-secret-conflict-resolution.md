# ADR 0073: Field Annotation System and Secret Conflict Resolution

**Date:** 2026-03-18  
**Status:** Accepted (implemented)  
**Depends on:** ADR 0068, ADR 0072

---

## Context

Current object templates and instance data use ADR0068 typed placeholders (`@required:<type>`, `@optional:<type>`) and ADR0072 side-car secret merge.

Two operational gaps were found:

1. Annotation logic was not centralized, making updates risky and inconsistent.
2. Secret fields could exist in both plaintext instance files and side-car secrets, producing ambiguity/conflicts during merge (for example `hardware_identity.mac_addresses.wan/lan1/lan2` on `rtr-slate`).

Also, `<TODO_...>` markers leak implementation details and are redundant when secret field intent is explicitly modeled.

---

## Decision

### 1) Introduce a centralized annotation registry and parser

All supported field annotations are defined in a single module:

- `v5/topology-tools/field_annotations.py`

All tooling that interprets field annotations MUST use this parser, not custom regexes.

### 2) Use one annotation token per field

Canonical token grammar:

- `@<name>` or `@<name>:<type>`

A field has exactly one annotation token.

Combined semantics are expressed as a single composed annotation name (not multiple tokens), for example:

- `@optional_secret:mac`
- `@required_secret:string`

### 3) Supported annotations (initial set)

- `@required:<type>`
- `@optional:<type>`
- `@secret`
- `@required_secret:<type>`
- `@optional_secret:<type>`

`<type>` must exist in the ADR0068 format registry.

### 4) Secret resolution and conflict policy

In `inject/strict` secrets modes:

- Fields marked with secret annotations are resolved from side-car decrypted data.
- If a plaintext value conflicts with side-car value on the same path, compilation emits hard error `E7212`.
- Plaintext is not silently overwritten for non-secret-marked fields.
- In `strict`, unresolved secret annotations emit error (`E7211`/existing strict unresolved checks).

This removes ambiguity and prevents accidental secret drift between cleartext and encrypted sources.

### 5) Migration direction

- Replace `<TODO_...>` markers on secret-bearing paths with explicit secret annotations.
- Keep non-secret fields as plain values.

Applied in this change for:

- `v5/topology/instances/l1_devices/rtr-slate.yaml`
- `v5/topology/instances/l1_devices/rtr-mikrotik-chateau.yaml`
- related object templates switched from `@optional:mac` to `@optional_secret:mac` for secret MAC paths.

---

## Consequences

### Positive

1. One authoritative annotation definition point.
2. Deterministic secret merge semantics.
3. Explicitly modeled secret intent in templates and instances.
4. Easier future extension of annotation vocabulary.

### Trade-offs

1. Existing templates/instances may require migration to secret-aware annotations.
2. Conflict errors can surface previously hidden data inconsistencies.

---

## Validation Criteria

1. Annotation parsing across validators/compilers uses `field_annotations.py`.
2. `@optional_secret:mac` and `@secret` are accepted by validators.
3. Secret-annotated fields are resolved from side-car data in `inject/strict`.
4. Plaintext vs side-car mismatches trigger `E7212`.
5. Full test suite remains green after migration.

