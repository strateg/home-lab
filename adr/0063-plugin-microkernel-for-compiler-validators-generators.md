# ADR 0063: Plugin Microkernel for Compiler, Validators, and Generators

**Date:** 2026-03-06
**Status:** In Progress (Phase 1 Complete)
**Related:** ADR 0062 (Topology v5 - Modular Class-Object-Instance Architecture)
**Extends:** ADR 0062 section "Open Questions" (generator/plugin packaging and loading model)

---

## Context

ADR 0062 fixed the Class -> Object -> Instance model and locked YAML -> JSON + diagnostics contracts.
The next scaling bottleneck is runtime extensibility:

- compiler logic is still concentrated in core orchestration code
- validators and generators are partially hardcoded by script paths
- module behavior is not yet loaded via a single plugin contract

We need one runtime model where:

1. core is a microkernel
2. class/object modules bring their own plugins
3. shared reusable plugins can be provided by base layer

---

## Decision

### 1. Adopt Microkernel Runtime

Introduce a microkernel responsible only for:

- loading topology and module manifests
- discovering and registering plugins
- dependency/order resolution between plugins
- executing pipeline stages
- aggregating diagnostics in canonical schema

Microkernel must not contain vendor-specific logic.

### 2. Make Plugins the Primary Extension Mechanism

Compiler, validators, and generators are all executed as plugins.

Normative plugin kinds:

1. `compiler` (transform/resolve hooks)
2. `validator_yaml` (source checks)
3. `validator_json` (compiled contract checks)
4. `generator` (artifact emitters)

### 3. Place Plugins Inside Modules

Plugins are stored with module code:

- class module plugins inside `topology/class-modules/...`
- object module plugins inside `topology/object-modules/...`

This keeps behavior colocated with class/object contracts.

### 4. Support Reusable Base Plugins

Allow reusable baseline plugins in core layer for cross-module reuse (for example common reference checks, shared emit helpers, generic diff checks).

Base plugins are referenced the same way as module plugins and participate in the same ordering/dependency graph.

### 5. Standardize Manifest Plugin Contract

Each module manifest must declare plugins with explicit metadata:

- `id` (globally unique)
- `kind` (`compiler|validator_yaml|validator_json|generator`)
- `entry` (`path.py:ClassName` or builtin alias)
- `api_version` (plugin API compatibility)
- `stages` (where it runs)
- `order` (deterministic execution)
- `depends_on` (plugin IDs)
- optional `capabilities` and `config_schema`

Example (abridged):

```yaml
plugins:
  - id: obj.mikrotik.validator.yaml.device
    kind: validator_yaml
    entry: validators/yaml/device.py:MikrotikDeviceYamlValidator
    api_version: "1.x"
    stages: [validate]
    order: 200
    depends_on: []
```

### 6. Enforce Deterministic Execution

Execution order is computed by:

1. stage boundary
2. dependency graph (`depends_on`)
3. stable numeric `order`
4. plugin `id` lexical tiebreak

Cycles or missing dependencies are hard errors.

### 7. Keep Diagnostics Contract Centralized

All plugin outcomes (success/warn/error/crash) must be emitted through canonical diagnostics envelope:

- `topology-tools/schemas/diagnostics.schema.json`
- `topology-tools/data/error-catalog.yaml`

Kernel wraps plugin exceptions into stable error codes with source context when available.

### 8. Version and Compatibility Rules

Plugin load is allowed only when all are compatible:

- kernel plugin API version
- model version from `model.lock`
- profile execution mode (`production|modeled|test-real`) when plugin declares restrictions

Incompatibility is fail-fast before stage execution.

---

## Consequences

### Positive

1. no hardcoded vendor branching in compiler pipeline
2. module behavior is self-contained and portable
3. easier incremental onboarding of new objects/classes
4. reusable base plugins reduce duplication
5. clearer boundaries for future `topology-base` extraction

### Negative

1. plugin lifecycle and compatibility management add complexity
2. manifest quality becomes critical for pipeline stability
3. debugging requires clear plugin attribution in diagnostics

---

## Risks and Mitigations

1. Risk: plugin order bugs
   - Mitigation: deterministic sort + cycle checks + order lints in CI
2. Risk: plugin API drift
   - Mitigation: explicit `api_version` negotiation and compatibility tests
3. Risk: hidden side effects inside plugins
   - Mitigation: contract tests and stage-scoped plugin interfaces
4. Risk: duplicate validation logic
   - Mitigation: promote shared checks to reusable base plugins

---

## Migration Plan

### Phase 1

- add plugin manifest schema
- add kernel plugin loader/registry
- wrap existing generators as `generator` plugins without behavior changes

### Phase 2

- migrate existing YAML semantic checks into `validator_yaml` plugins
- migrate compiled checks into `validator_json` plugins
- keep parity with current diagnostics and outputs

### Phase 3

- extract compiler transforms into `compiler` plugins
- remove residual hardcoded dispatch from orchestration
- enforce plugin-only extension policy for new modules

---

## Implementation Checklist

### Phase 1 - Plugin Infrastructure (Complete)

- [x] Plugin manifest schema (`v5/topology-tools/schemas/plugin-manifest.schema.json`)
- [x] Diagnostics schema with plugin attribution (`v5/topology-tools/schemas/diagnostics.schema.json`)
- [x] Kernel package with base interfaces (`v5/topology-tools/kernel/`)
  - [x] `plugin_base.py` - PluginBase, PluginKind, PluginContext, PluginResult
  - [x] `plugin_registry.py` - PluginRegistry, PluginManifest, PluginSpec
- [x] Error catalog with plugin error codes (`v5/topology-tools/data/error-catalog.yaml`)
- [x] Base reference validator plugin (`v5/topology-tools/plugins/validators/reference_validator.py`)
- [x] Plugin tests (`v5/tests/test_plugin_registry.py`)

### Phase 2 - Validator Migration (Pending)

- [ ] Migrate YAML semantic checks to `validator_yaml` plugins
- [ ] Migrate compiled JSON checks to `validator_json` plugins
- [ ] Integrate plugin execution into compile-topology.py
- [ ] Maintain parity with current diagnostics output

### Phase 3 - Compiler Transforms (Pending)

- [ ] Extract compiler transforms into `compiler` plugins
- [ ] Remove hardcoded dispatch from orchestration
- [ ] Enforce plugin-only extension policy

---

## References

- Consolidated architecture: `adr/0062-modular-topology-architecture-consolidation.md`
- Compiler entrypoint: `v5/topology-tools/compile-topology.py`
- Diagnostics schema: `v5/topology-tools/schemas/diagnostics.schema.json`
- Error catalog: `v5/topology-tools/data/error-catalog.yaml`
- Plugin manifest schema: `v5/topology-tools/schemas/plugin-manifest.schema.json`
- Kernel package: `v5/topology-tools/kernel/`
- Base plugins: `v5/topology-tools/plugins/`
