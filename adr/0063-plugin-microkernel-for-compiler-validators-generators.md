# ADR 0063: Plugin Microkernel for Compiler, Validators, and Generators

**Date:** 2026-03-06
**Status:** Implemented (plugin-first runtime; legacy fallback removed)
**Related:** ADR 0062 (Topology v5 - Modular Class-Object-Instance Architecture), ADR 0065 (Plugin API Contract), ADR 0066 (Plugin Testing and CI Strategy)
**Extends:** ADR 0062 section "Open Questions" (generator/plugin packaging and loading model)

---

## Context

ADR 0062 fixed the Class -> Object -> Instance model and locked YAML -> JSON + diagnostics contracts.
At the time this ADR was introduced, the next scaling bottleneck was runtime extensibility:

- compiler logic was still concentrated in core orchestration code
- validators and generators were partially hardcoded by script paths
- module behavior was not yet loaded via a single plugin contract

This ADR defines the foundational runtime model that later ADRs operationalize.

We need one runtime model where:

1. core is a microkernel
2. class/object modules bring their own plugins
3. shared reusable plugins can be provided by base layer

### Relationship to Later ADRs

This ADR remains the architectural foundation for runtime/plugin boundaries.
Later ADRs refine or operationalize specific aspects:

1. `ADR 0068` defines domain-level placeholder and explicit-override contracts executed within plugin-managed compile/validate flow.
2. `ADR 0069` operationalizes plugin-first compiler cutover, thin orchestrator ownership, parity gates, and rollback governance.
3. `ADR 0071` changes instance storage authoring to sharded files while preserving downstream plugin consumption of normalized assembled payload.

---

## Decision

### 1. Adopt Microkernel Runtime

Introduce a microkernel responsible only for:

- loading topology and module manifests
- discovering and registering plugins
- dependency/order resolution between plugins
- executing pipeline stages
- aggregating diagnostics in canonical schema
- wrapping plugin exceptions into error codes with source context
- enforcing timeout limits per plugin (default: 30s)

Microkernel must not contain vendor-specific logic.

#### Error Handling and Recovery Strategy

The microkernel applies this error handling policy:

**Timeout (>30s per plugin):**
- Hard kill plugin process/thread
- Return TIMEOUT status
- Emit critical diagnostic
- Continue if stage is non-critical (validate), fail-fast if critical (compile)

**Config Validation Error:**
- Catch before stage execution
- Return FAILED status
- Hard error (fail-fast all stages)

**Plugin Exception during execute():**
- Catch exception and traceback
- Include traceback in PluginResult.error_traceback
- Return FAILED status
- Emit error diagnostic with standardized code
- Continue if stage is non-critical, fail-fast if critical

**Missing Dependency:**
- Detect in dependency resolution phase (pre-stage)
- Fail-fast before stage execution
- Emit critical diagnostic

**Capability Mismatch:**
- Detect in pre-flight checks before plugin execution
- Fail-fast
- Hard error before stage execution

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

### 4A. Deterministic Module-Level Manifest Discovery and Merge

Runtime loads plugin manifests with deterministic merge policy:

1. explicit base manifest from CLI/config (`--plugins-manifest`)
2. module manifests discovered under class modules root (`**/plugins.yaml`)
3. module manifests discovered under object modules root (`**/plugins.yaml`)

Within each module root, manifests are sorted lexicographically by relative path.

Duplicate plugin IDs across manifests are hard load errors (no override behavior).
First-loaded definition is retained, duplicate declarations are rejected with diagnostics.

### 5. Standardize Manifest Plugin Contract

Each module manifest must declare plugins with explicit metadata:

- `id` (globally unique, format: `{module_id}.{plugin_kind}.{specific_name}`)
- `kind` (`compiler|validator_yaml|validator_json|generator`)
- `entry` (`path.py:ClassName` or builtin alias)
- `api_version` (plugin API compatibility, format: `major.x` e.g., `1.x`)
- `stages` (where it runs: `validate|compile|generate`, multiple allowed)
- `order` (deterministic execution within stage, higher number = later)
- `depends_on` (list of plugin IDs that must execute before this one)
- `config` (static configuration defaults as YAML)
- `config_schema` (JSON Schema for config validation)
- optional `capabilities` and `requires_capabilities`

Example (abridged):

```yaml
plugins:
  - id: obj.mikrotik.validator.yaml.device
    kind: validator_yaml
    entry: plugins/yaml_validators/device.py:MikrotikDeviceYamlValidator
    api_version: "1.x"
    stages: [validate]
    order: 200
    depends_on: []
    config:
      max_device_count: 1000
      enable_strict: false
    config_schema:
      type: object
      properties:
        max_device_count:
          type: integer
          minimum: 1
          default: 1000
        enable_strict:
          type: boolean
          default: false
      required: []
```

#### Plugin Kinds Specification

**compiler** - Transform and resolve Object Model
- Input: `dict` (parsed YAML Object Model)
- Output: `dict` (transformed Object Model in output_data)
- Runs in: `compile` stage
- Contract: Must not mutate input, return valid Object Model structure

**validator_yaml** - Check source YAML syntax and semantics
- Input: `dict` (parsed YAML), `str` (source file path)
- Output: `List[PluginDiagnostic]` (validation issues)
- Runs in: `validate` stage
- Contract: Must provide source location (line/column) when available

**validator_json** - Validate compiled Object Model consistency
- Input: `dict` (compiled JSON), `str` (compiled file path)
- Output: `List[PluginDiagnostic]` (consistency issues)
- Runs in: `validate` stage
- Contract: May reference outputs from compiler plugins via context

**generator** - Emit artifacts (code, configs, docs)
- Input: `dict` (compiled JSON), `Path` (output directory)
- Output: File listing and metadata in output_data
- Runs in: `generate` stage
- Contract: Must create output_dir if not exists, support incremental generation

Detailed interface specifications are provided in ADR 0065 (Plugin API Contract Specification).

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

Each plugin emits `PluginResult` with standardized structure (see ADR 0064):

```python
@dataclass
class PluginResult:
    plugin_id: str
    api_version: str
    status: PluginStatus  # SUCCESS|PARTIAL|FAILED|TIMEOUT|SKIPPED
    duration_ms: float
    diagnostics: List[PluginDiagnostic]
    output_data: Optional[Dict[str, Any]]  # transformed model or generated files
    error_traceback: Optional[str]  # full exception traceback if crashed
```

Kernel aggregates all PluginResult objects into final diagnostics report with:
- Plugin attribution (which plugin emitted this?)
- Severity levels (ERROR > WARNING > INFO)
- Source locations (file, line, column when available)
- Error codes mapped to error-catalog.yaml descriptions

### 8. Version and Compatibility Rules

Plugin load is allowed only when all are compatible:

- kernel plugin API version (e.g., plugin requires `1.x`, kernel supports `1.2`)
- model version from `model.lock`
- profile execution mode (`production|modeled|test-real`) when plugin declares restrictions

Incompatibility is fail-fast before stage execution.

**Compatibility Matrix:**

A plugin with `api_version: "1.x"` is compatible with kernel supporting:
- `1.0`, `1.1`, `1.2`, ..., `1.n` (minor version bumps)
- NOT compatible with `2.x` or `0.x`

Breaking changes require kernel major version bump. Kernel publishes compatibility matrix:

```yaml
kernel:
  version: "0.5.0"
  plugin_api_version: "1.2"
  supported_api_versions:
    - "1.x"  # plugins targeting 1.0 through 1.x work
  model_versions:
    - "0062-1.0"  # compatible model versions
  execution_profiles:
    - production
    - modeled
    - test-real
```

### 8A. Canonical Inter-Stage Compiled Model Boundary

This ADR defines stage/plugin execution architecture.
The canonical compiled-model handoff between `compile`, `validate`, and `generate` stages is later refined by `ADR 0069` as a versioned `ctx.compiled_json` contract.

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

### Clarified Boundary Consequences

1. Source storage/layout changes are normalized before downstream plugin execution.
2. Plugins consume normalized assembled payload or canonical compiled model, not arbitrary source-layout-specific file scans.
3. Runtime evolution should preserve microkernel boundaries even when domain contracts or authoring formats evolve.

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

This section is retained as historical migration summary for the original rollout of the plugin microkernel.
Active plugin-first cutover governance, parity rules, rollback protocol, and thin-orchestrator ownership are defined by `ADR 0069` and its analysis documents.

### Phase 1 (Week 1)

- Define plugin API protocol with base classes
- Implement kernel plugin loader/registry
- Add manifest plugin schema with validation
- Create PluginContext and PluginResult classes
- Document in ADR 0065 (Plugin API Contract Specification)

### Phase 2 (Week 2-3)

- Wrap existing generators as `generator` plugins without behavior changes
- Migrate existing YAML semantic checks into `validator_yaml` plugins
- Migrate compiled checks into `validator_json` plugins
- Keep parity with current diagnostics and outputs
- Add compatibility tests (plugin results match old validator output)

### Phase 3 (Week 4-5)

- Extract compiler transforms into `compiler` plugins
- Implement context.subscribe() for inter-plugin communication
- Remove residual hardcoded dispatch from orchestration
- Enforce plugin-only extension policy for new modules

### Phase 4 (Post-stabilization)

- Superseded by ADR 0069 cutover implementation
- Legacy dispatcher fallback is retired in runtime
- Plugin-first execution is mandatory in `compile-topology.py`

---

## Testing Requirements

Every plugin must include:

1. **Unit Tests** - Logic tested in isolation
   - Valid input cases
   - Error/edge cases
   - Configuration validation
   - Location context accuracy (for validators)

2. **Contract Tests** - Plugin vs Kernel compatibility
   - Plugin can be loaded from manifest
   - Config is injected correctly
   - Output format matches PluginResult contract
   - Timeout is enforced

3. **Integration Tests** - Full pipeline
   - Plugin runs in correct stage
   - Dependencies are honored (depends_on)
   - Diagnostics appear in aggregated report
   - Plugin results integrated with other plugins

4. **Regression Tests** - Parity with legacy
   - Output matches old validator (during migration)
   - No new false positives/negatives
   - No performance regression >10%

CI must:
- Run all plugin tests before merge
- Collect plugin execution metrics
- Alert if any plugin exceeds timeout threshold
- Validate manifest completeness

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

### Phase 2 - Validator Migration (Complete)

- [x] Decision recorded: migration of remaining YAML semantic checks to `validator_yaml` is deferred (no active unmet YAML-semantics scope in current runtime).
- [x] Migrate compiled JSON checks to `validator_json` plugins
  - [x] `model_lock_validator.py` - validates model.lock pinning
  - [x] `embedded_in_validator.py` - validates embedded_in references per ADR 0064
- [x] Integrate plugin execution into compile-topology.py
  - [x] Plugin-first execution is default CLI behavior
  - [x] `--plugins-manifest` flag for custom manifest path
  - [x] Plugin diagnostics converted with `plugin_id` attribution
  - [x] Timeout (E4101) and crash (E4102) error handling
- [x] Maintain parity with current diagnostics output

### Phase 3 - Inter-Plugin Communication (Complete)

- [x] Implement context.publish(key, value) for data publication
- [x] Implement context.subscribe(plugin_id, key) for data retrieval
- [x] Add dependency enforcement (only depends_on plugins can be queried)
- [x] Add error handling for missing data/invalid dependencies
- [x] Add tests for publish/subscribe (4 new tests, 16 total)
- [x] Sample compiler plugin (`plugins/compilers/capability_compiler.py`)
- [x] Sample validator using subscribe (`plugins/validators/capability_contract_validator.py`)
- [x] Shared PluginContext across COMPILE and VALIDATE stages
- [x] Module-level plugin manifest discovery and deterministic merge policy

### Phase 4 - Full Migration (Cutover Applied)

- [x] Legacy dispatcher removed from orchestrator runtime path
- [x] Plugin-first pipeline is enforced
- [x] Compile/validate data exchange uses publish/subscribe contracts
- [x] Remaining YAML semantic checks migration is explicitly deferred and treated as non-goal for current cutover baseline; revisit only when a concrete YAML-stage contract gap appears.

---

## References

- ADR 0062: `adr/0062-modular-topology-architecture-consolidation.md`
- ADR 0065: `adr/0065-plugin-api-contract-specification.md` (detailed API contracts)
- ADR 0066: `adr/0066-plugin-testing-and-ci-strategy.md` (test pyramid and CI gates)
- Plugin Authoring Guide: `v5/topology-tools/docs/PLUGIN_AUTHORING.md`
- Compiler entrypoint: `v5/topology-tools/compile-topology.py`
- Diagnostics schema: `v5/topology-tools/schemas/diagnostics.schema.json`
- Plugin manifest schema: `v5/topology-tools/schemas/plugin-manifest.schema.json`
- Error catalog: `v5/topology-tools/data/error-catalog.yaml`
- Kernel package: `v5/topology-tools/kernel/`
- Base plugins: `v5/topology-tools/plugins/`
- Plugin tests: `v5/tests/test_plugin_registry.py`
- `adr/0068-object-yaml-as-instance-template-with-explicit-overrides.md`
- `adr/0069-plugin-first-compiler-refactor-and-thin-orchestrator.md`
- `adr/0071-sharded-instance-files-and-flat-instances-root.md`
