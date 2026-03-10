# ADR 0068 Implementation Plan

**ADR:** `adr/0068-object-yaml-as-instance-template-with-explicit-overrides.md`
**Date:** 2026-03-10
**Status:** In Progress (Plugin-first implementation)

---

## Goal

Implement ADR0068 via plugin architecture (ADR0063), not core compiler branching.

Primary contract:

- object placeholders: `@required:<format>` / `@optional:<format>`
- instance values: `instance_overrides`
- centralized formats: `v5/topology-tools/data/instance-field-formats.yaml`

---

## Plugin Strategy

### Plugin

- ID: `base.validator.instance_placeholders`
- Kind: `validator_json`
- Entry: `v5/topology-tools/plugins/validators/instance_placeholder_validator.py`

### Why plugin

1. Keeps `compile-topology.py` stable and thin.
2. Enables incremental rollout by manifest order/config.
3. Keeps ADR0068 policy independently testable.

---

## Implementation Phases

### Phase 1: Validator Plugin Baseline

Files:

- `v5/topology-tools/plugins/validators/instance_placeholder_validator.py`
- `v5/topology-tools/plugins/plugins.yaml`

Tasks:

1. Parse placeholders in object templates.
2. Validate placeholder syntax and known format token.
3. Validate `instance_overrides` against placeholder-marked paths.
4. Enforce required placeholders per instance.

Status: Implemented.

### Phase 2: Format Registry and Error Catalog

Files:

- `v5/topology-tools/data/instance-field-formats.yaml`
- `v5/topology-tools/data/error-catalog.yaml`

Tasks:

1. Validate override values by registry formats.
2. Wire ADR0068 diagnostics (`E6801`..`E6806`) into catalog.

Status: Implemented (base set).

### Phase 3: Plugin Test Coverage

Files:

- `v5/tests/plugin_integration/test_instance_placeholder_plugin.py`

Tasks:

1. Positive path test.
2. Missing required test.
3. Non-marked override test.
4. Invalid format test.
5. Unknown format token test.

Status: Implemented.

### Phase 4: Topology Migration Rollout

Files:

- `v5/topology/object-modules/**` (targeted)
- `v5/topology/instances/home-lab/instance-bindings.yaml` (targeted)

Tasks:

1. Replace selected null/TODO fields with placeholders.
2. Add corresponding `instance_overrides` values.
3. Run compile with `--enable-plugins` and fix diagnostics.

Status: Pending.

### Phase 5: Hardening and Contract Finalization

Files:

- `v5/topology-tools/plugins/validators/instance_placeholder_validator.py`
- `v5/topology-tools/docs/PLUGIN_AUTHORING.md` (optional docs addendum)

Tasks:

1. Add strict unresolved-placeholder policy (`E6806`) where applicable.
2. Add optional profile-gated enforcement mode (`warn` -> `enforce`).
3. Document escape/literal conventions for reserved marker tokens.

Status: Pending.

---

## Acceptance Criteria

1. ADR0068 validation is enforced by plugin manifest entry.
2. Format source of truth remains `instance-field-formats.yaml`.
3. `pytest` plugin integration tests are green.
4. Target topology compiles cleanly with plugins enabled after migration phase.
