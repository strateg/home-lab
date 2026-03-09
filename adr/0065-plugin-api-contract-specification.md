# ADR 0065: Plugin API Contract Specification

**Date:** 2026-03-09
**Status:** Proposed
**Related:** ADR 0062 (Topology v5 Architecture), ADR 0063 (Plugin Microkernel), ADR 0066 (Plugin Testing and CI Strategy)

---

## Context

ADR 0063 defines the microkernel model and plugin kinds, but implementation requires a stable API contract:

- plugin authors need typed interfaces and predictable lifecycle hooks
- kernel implementation needs a strict result/diagnostic envelope
- manifests need deterministic loading and compatibility checks
- CI needs contract tests against one canonical API version

Without a formal API contract, plugin behavior will drift across modules and break deterministic execution.

---

## Decision

### 1. Introduce Plugin API v1 Namespace

Plugin API v1 is published under import path:

- `topology_tools.plugin_api`

Repository implementation target:

- `v5/topology_tools/plugin_api/`

This path is normative for plugin imports and test fixtures, independent from CLI script paths under `v5/topology-tools/`.

### 2. Standardize Core Data Contracts

Plugin API MUST define these enums:

- `PluginStatus`: `SUCCESS|PARTIAL|FAILED|TIMEOUT|SKIPPED`
- `PluginSeverity`: `ERROR|WARNING|INFO`

Plugin API MUST define these dataclasses:

- `PluginLocation(file: str, line: int | None, column: int | None)`
- `PluginDiagnostic(severity, code, message, location, context, timestamp)`
- `PluginResult(plugin_id, api_version, status, duration_ms, diagnostics, output_data, error_traceback)`
- `PluginContext(kernel, plugin_id, module_id, stage, profile, model_version, config)`

`PluginResult` is the only accepted return envelope for plugin execution.
Kernel MUST aggregate diagnostics exclusively from `PluginResult.diagnostics`.

### 3. Define Base Plugin Interfaces

Plugin API MUST expose:

- `BasePlugin` (abstract)
- `YamlValidatorPlugin`
- `JsonValidatorPlugin`
- `CompilerPlugin`
- `GeneratorPlugin`

`BasePlugin` MUST provide:

- constructor with `PluginContext`
- `validate_config() -> PluginResult`
- helper methods for success/failure result creation
- helper for diagnostics construction

Kind-specific `execute()` contracts:

- `YamlValidatorPlugin.execute(yaml_dict: dict[str, Any], source_path: str) -> PluginResult`
- `JsonValidatorPlugin.execute(json_dict: dict[str, Any], compiled_path: str) -> PluginResult`
- `CompilerPlugin.execute(model_dict: dict[str, Any]) -> PluginResult`
- `GeneratorPlugin.execute(json_dict: dict[str, Any], output_dir: Path) -> PluginResult`

Plugins MUST NOT mutate input objects in-place.

### 4. Define Inter-Plugin Data Exchange

`PluginContext` MUST provide:

- `publish(key: str, value: Any) -> None`
- `subscribe(plugin_id: str, key: str) -> Any`

Rules:

- only plugins listed in `depends_on` may be queried with `subscribe()`
- missing published data is a plugin-level failure, not a kernel crash
- exchange payloads are runtime-only and are not persisted automatically

### 5. Define Configuration Injection Contract

Kernel MUST construct `context.config` with precedence:

1. global defaults
2. manifest plugin `config`
3. environment overrides
4. runtime/CLI overrides

Configuration MUST be validated against manifest `config_schema` before `execute()`.
Invalid configuration is a fail-fast plugin error at pre-flight stage.

### 6. Define API Compatibility Rules

Manifest field `api_version` uses major compatibility contract:

- plugin `1.x` is compatible with kernel `1.0..1.n`
- plugin `1.x` is incompatible with kernel `2.x`

Kernel MUST reject incompatible plugins before stage execution and emit a critical diagnostic.

### 7. Define Manifest Entry Validation

`entry` format is mandatory:

- `<relative_path.py>:<ClassName>` or builtin alias

Loader MUST validate:

- file exists under module root (or alias is known builtin)
- class is importable
- class inherits one of API base interfaces
- declared `kind` matches class interface

Failures are hard errors in discovery phase.

### 8. Define Error Mapping Contract

Any unhandled plugin exception MUST be wrapped by kernel into:

- `PluginResult.status=FAILED`
- populated `error_traceback`
- standardized diagnostic code from error catalog mapping

Kernel timeout MUST produce:

- `PluginResult.status=TIMEOUT`
- diagnostic with timeout code and plugin attribution

---

## Consequences

### Positive

1. plugin development becomes contract-first and testable in isolation
2. kernel remains orchestration-focused and vendor-agnostic
3. CI can enforce one compatibility matrix for all modules
4. migration from hardcoded validators/generators becomes incremental

### Negative

1. additional upfront work to build API package and adapter tests
2. stricter manifests may block previously permissive module loading
3. plugin authors must follow dataclass/result envelope conventions

---

## Migration Plan

### Phase 1 (API foundation)

- create `v5/topology_tools/plugin_api/` package
- implement enums, dataclasses, base classes, context helpers
- add unit tests for API objects and helper behavior

### Phase 2 (loader compatibility)

- implement manifest entry validation against API classes
- add contract tests for entry loading, kind matching, version checks
- integrate config schema validation in pre-flight

### Phase 3 (runtime adoption)

- migrate first validator/generator plugins to API v1
- enforce API envelope in microkernel execution path
- deprecate direct non-plugin dispatch paths after parity checks

---

## References

- ADR 0062: `adr/0062-modular-topology-architecture-consolidation.md`
- ADR 0063: `adr/0063-plugin-microkernel-for-compiler-validators-generators.md`
- ADR 0066: `adr/0066-plugin-testing-and-ci-strategy.md`
- Authoring guide: `docs/PLUGIN_AUTHORING_GUIDE.md`
- Implementation examples: `docs/PLUGIN_IMPLEMENTATION_EXAMPLES.md`
- Compiler baseline: `v5/topology-tools/compile-topology.py`
