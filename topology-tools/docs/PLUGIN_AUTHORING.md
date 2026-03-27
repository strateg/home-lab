# Plugin Authoring Guide

This guide explains how to write plugins for the v5 topology compiler (ADR 0063).

## Overview

The v5 topology compiler uses a microkernel architecture where discovery, compilation, validation,
generation, assembly, and build logic are implemented as plugins. This enables:

- Modular extension of the compiler pipeline
- Independent development and testing of checks
- Ordered execution with dependency resolution
- Inter-plugin data exchange

## Plugin Types

| Kind | Base Class | Input | Output | Stage |
|------|------------|-------|--------|-------|
| `discoverer` | `DiscovererPlugin` | Runtime bootstrap context | Discovery inventory/preflight | `discover` |
| `compiler` | `CompilerPlugin` | Parsed YAML | Transformed data | `compile` |
| `validator_yaml` | `ValidatorYamlPlugin` | Parsed YAML + source | Diagnostics | `validate` |
| `validator_json` | `ValidatorJsonPlugin` | Compiled JSON | Diagnostics | `validate` |
| `generator` | `GeneratorPlugin` | Compiled JSON | Generated files | `generate` |
| `assembler` | `AssemblerPlugin` | Compiled JSON + artifact roots | Assembled execution workspace | `assemble` |
| `builder` | `BuilderPlugin` | Assembled workspace | Release package/verification outputs | `build` |

Kind/stage affinity is enforced at manifest load:

1. `discoverer -> discover`
2. `compiler -> compile`
3. `validator_yaml|validator_json -> validate`
4. `generator -> generate`
5. `assembler -> assemble`
6. `builder -> build`

## Quick Start

### 1. Create Plugin Module

```python
# topology-tools/plugins/validators/my_validator.py
from __future__ import annotations

from typing import Any

from kernel.plugin_base import (
    PluginContext,
    PluginDiagnostic,
    PluginResult,
    Stage,
    ValidatorJsonPlugin,
)


class MyValidator(ValidatorJsonPlugin):
    """Custom validation plugin."""

    def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        diagnostics: list[PluginDiagnostic] = []

        # Access instance bindings
        bindings = ctx.instance_bindings.get("instance_bindings", {})

        for group_name, rows in bindings.items():
            if not isinstance(rows, list):
                continue

            for row in rows:
                if not isinstance(row, dict):
                    continue

                instance_id = row.get("instance", "<unknown>")
                # ... validation logic ...

                if some_error_condition:
                    diagnostics.append(
                        self.emit_diagnostic(
                            code="E9001",
                            severity="error",
                            stage=stage,
                            message="Validation failed for instance",
                            path=f"instance:{group_name}:{instance_id}",
                            hint="Fix the issue by ...",
                        )
                    )

        return self.make_result(diagnostics)
```

### 2. Register in Manifest

Registration policy:

1. Shared/global plugins (cross-object) are registered in:
   - `topology-tools/plugins/plugins.yaml`
2. Object-scoped plugins are registered in object module manifest:
   - `topology/object-modules/<object-id>/plugins.yaml`

Example for shared/global plugin (central manifest):

```yaml
- id: my.validator.custom
  kind: validator_json
  entry: plugins/validators/my_validator.py:MyValidator
  api_version: "1.x"
  stages: [validate]
  order: 200
  depends_on: []
  timeout: 30
  config: {}
  config_schema:
    type: object
    properties: {}
    required: []
  description: My custom validation plugin
```

Example for object-scoped plugin (module manifest):

```yaml
- id: object_mikrotik.validator_json.router_ports
  kind: validator_json
  entry: plugins/validators/mikrotik_router_ports_validator.py:MikrotikRouterPortsValidator
  api_version: "1.x"
  stages: [validate]
  order: 241
  depends_on: [base.validator.references]
  timeout: 30
  config: {}
  config_schema:
    type: object
    properties: {}
    required: []
  description: Validates MikroTik router ports.
```

### 3. Run with Plugins

```bash
python3 topology-tools/compile-topology.py \
    --topology topology/topology.yaml
```

Manifest discovery order is deterministic:

1. base manifest (`topology-tools/plugins/plugins.yaml`)
2. class module manifests (`topology/class-modules/**/plugins.yaml`)
3. object module manifests (`topology/object-modules/**/plugins.yaml`)

## Plugin Context

The `PluginContext` provides access to all data needed for plugin execution:

```python
@dataclass
class PluginContext:
    # Paths
    topology_path: str
    profile: str
    source_file: str        # For validator_yaml
    compiled_file: str      # For validator_json
    output_dir: str         # For generators

    # Data
    raw_yaml: dict          # Parsed YAML (before compilation)
    instance_bindings: dict # Instance binding table
    compiled_json: dict     # Compiled JSON output
    model_lock: dict        # model.lock pins

    # Module data
    classes: dict           # Class definitions
    objects: dict           # Object definitions
    capability_catalog: dict

    # Derived data (from compile stage)
    effective_capabilities: dict
    effective_software: dict

    # Plugin configuration (from manifest)
    config: dict

    # Error catalog for code lookups
    error_catalog: dict
```

## Emitting Diagnostics

Use `emit_diagnostic()` to create standardized diagnostic messages:

```python
diagnostic = self.emit_diagnostic(
    code="W3201",                    # Error code from error-catalog.yaml
    severity="warning",              # "error" | "warning" | "info"
    stage=stage,                     # Current pipeline stage
    message="Description of issue",
    path="instance:devices:srv-01",  # Entity path
    hint="How to fix this",          # Optional fix hint
    source_file="topology.yaml",     # Optional source location
    source_line=42,
    source_column=5,
    confidence=0.9,                  # 0.0-1.0, default 1.0
)
```

### Error Codes

Error codes must be registered in `topology-tools/data/error-catalog.yaml`:

```yaml
codes:
  E9001:
    severity: error
    stage: validate
    title: My Custom Error
    hint: How to resolve this error.
  W9001:
    severity: warning
    stage: validate
    title: My Custom Warning
    hint: Consider fixing this issue.
```

## Plugin Result

The `make_result()` helper automatically determines status from diagnostics:

```python
# Automatic status based on diagnostics:
# - No errors/warnings -> SUCCESS
# - Warnings only -> PARTIAL
# - Any errors -> FAILED

return self.make_result(
    diagnostics=diagnostics,
    duration_ms=elapsed,
    output_data={"key": "value"},  # Optional output data
)
```

Alternatively, use factory methods:

```python
return PluginResult.success(self.plugin_id, diagnostics=diagnostics)
return PluginResult.partial(self.plugin_id, diagnostics=diagnostics)
return PluginResult.failed(self.plugin_id, diagnostics=diagnostics)
return PluginResult.timeout(self.plugin_id)
return PluginResult.skipped(self.plugin_id, reason="Dependency failed")
```

## Inter-Plugin Communication

Plugins can exchange data using `publish()` and `subscribe()`:

### Publisher (Compiler Plugin)

```python
class CapabilityCompiler(CompilerPlugin):
    def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        diagnostics = []

        # Derive capabilities from objects
        derived_caps: dict[str, list[str]] = {}
        for obj_id, obj_data in ctx.objects.items():
            caps = obj_data.get("capabilities", [])
            derived_caps[obj_id] = caps

        # Publish for dependent validators
        ctx.publish("derived_capabilities", derived_caps)
        ctx.publish("capability_stats", {
            "total": len(derived_caps),
            "objects": list(derived_caps.keys()),
        })

        return self.make_result(diagnostics)
```

### Subscriber (Validator Plugin)

```python
class CapabilityValidator(ValidatorJsonPlugin):
    def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        diagnostics = []

        # Subscribe to data from compiler plugin
        try:
            derived_caps = ctx.subscribe(
                "base.compiler.capabilities",
                "derived_capabilities"
            )
        except PluginDataExchangeError as e:
            # Handle gracefully if compiler didn't run
            diagnostics.append(
                self.emit_diagnostic(
                    code="W4301",
                    severity="warning",
                    stage=stage,
                    message=f"Cannot validate: {e}",
                    path="plugin:base.compiler.capabilities",
                )
            )
            return self.make_result(diagnostics)

        # Use derived_caps for validation
        for obj_id, caps in derived_caps.items():
            # ... validation logic ...

        return self.make_result(diagnostics)
```

### Dependency Declaration

To subscribe to another plugin's data, declare it in `depends_on`:

```yaml
- id: base.validator.capability_contract
  kind: validator_json
  entry: validators/capability_contract_validator.py:CapabilityContractValidator
  depends_on: [base.compiler.capabilities]  # Required for subscribe()
```

The registry enforces that:
1. Plugins can only subscribe to plugins listed in `depends_on`
2. Dependencies are executed before dependents (respects `order` within stage)
3. Cross-stage dependencies work (compile plugins run before validate plugins)

Contract note:
- compile-derived data must be consumed via `subscribe()`.
- do not use `ctx.config` as a transport channel for compiler outputs.

## Manifest Schema

Full manifest schema for reference:

```yaml
schema_version: 1
plugins:
  - id: string                    # Unique plugin ID (reverse-domain style)
    kind: string                  # discoverer | compiler | validator_yaml | validator_json | generator | assembler | builder
    entry: string                 # path/to/module.py:ClassName
    api_version: string           # "1.x" (semver pattern)
    stages: [string]              # [discover] | [compile] | [validate] | [generate] | [assemble] | [build]
    order: integer                # Execution order (lower = earlier)
    depends_on: [string]          # Plugin IDs this plugin depends on
    timeout: integer              # Execution timeout in seconds
    config: object                # Plugin configuration
    config_schema:                # JSON Schema for config validation
      type: object
      properties: {}
      required: []
    description: string           # Human-readable description
```

### Field Details

| Field | Required | Default | Description |
|-------|----------|---------|-------------|
| `id` | Yes | - | Unique identifier, recommend reverse-domain: `org.example.plugin` |
| `kind` | Yes | - | Plugin type, must match class's `kind` property |
| `entry` | Yes | - | Preferred: `plugins/<family>/module.py:ClassName` where family matches `kind` |
| `api_version` | Yes | - | Currently `"1.x"` |
| `stages` | Yes | - | Pipeline stages where plugin runs |
| `order` | No | 100 | Lower values execute first |
| `depends_on` | No | `[]` | Plugin IDs required to run before this plugin |
| `timeout` | No | 30 | Maximum execution time in seconds |
| `config` | No | `{}` | Plugin-specific configuration |
| `config_schema` | No | `{}` | JSON Schema for config validation |
| `description` | No | - | Human-readable description |

Stage-specific `order` ranges are enforced by runtime:

1. `discover`: 10-89
2. `compile`: 30-89
3. `validate`: 90-189
4. `generate`: 190-399
5. `assemble`: 400-499
6. `build`: 500-599

Entry family affinity is enforced for structured entry paths:

1. `discoverer -> plugins/discoverers/...`
2. `compiler -> plugins/compilers/...`
3. `validator_yaml|validator_json -> plugins/validators/...`
4. `generator -> plugins/generators/...`
5. `assembler -> plugins/assemblers/...`
6. `builder -> plugins/builders/...`

## Testing Plugins

### Unit Tests

```python
# tests/plugin_api/test_my_validator.py
import pytest
from kernel.plugin_base import Phase, PluginContext, PluginExecutionScope, Stage
from plugins.validators.my_validator import MyValidator


def test_validator_success():
    plugin = MyValidator("test.validator", "1.x")
    ctx = PluginContext(
        topology_path="/test/topology.yaml",
        profile="test",
        model_lock={},
        instance_bindings={"instance_bindings": {}},
    )
    scope = PluginExecutionScope(
        plugin_id="test.validator",
        allowed_dependencies=frozenset(),
        phase=Phase.RUN,
        stage=Stage.VALIDATE,
        config={},
    )
    token = ctx._set_execution_scope(scope)
    try:
        result = plugin.execute(ctx, Stage.VALIDATE)
    finally:
        ctx._clear_execution_scope(token)

    assert result.status.value == "SUCCESS"
    assert len(result.diagnostics) == 0


def test_validator_detects_error():
    plugin = MyValidator("test.validator", "1.x")
    ctx = PluginContext(
        topology_path="/test/topology.yaml",
        profile="test",
        model_lock={},
                instance_bindings={
                    "instance_bindings": {
                        "devices": [{"instance": "bad-device", "error_field": True}]
                    }
                },
    )
    scope = PluginExecutionScope(
        plugin_id="test.validator",
        allowed_dependencies=frozenset(),
        phase=Phase.RUN,
        stage=Stage.VALIDATE,
        config={},
    )
    token = ctx._set_execution_scope(scope)
    try:
        result = plugin.execute(ctx, Stage.VALIDATE)
    finally:
        ctx._clear_execution_scope(token)

    assert result.status.value == "FAILED"
    assert any(d.code == "E9001" for d in result.diagnostics)
```

### Integration Tests

```python
# tests/plugin_integration/test_my_plugin.py
import pytest
from kernel.plugin_registry import PluginRegistry


def test_plugin_loads_and_executes(tmp_path):
    manifest_path = tmp_path / "plugins.yaml"
    manifest_path.write_text("""
schema_version: 1
plugins:
  - id: test.validator
    kind: validator_json
    entry: validators/my_validator.py:MyValidator
    api_version: "1.x"
    stages: [validate]
    order: 100
    depends_on: []
    timeout: 30
    config: {}
""")

    registry = PluginRegistry(str(manifest_path))
    assert "test.validator" in registry.list_plugins()

    # ... test execution ...
```

## Best Practices

1. **Use standard error codes**: Register codes in `error-catalog.yaml`
2. **Use subscribe-first contracts**: For required compile data, use `subscribe()` and emit explicit diagnostics on missing data
3. **Provide helpful hints**: Include actionable fix suggestions
4. **Respect timeouts**: Long-running plugins should checkpoint progress
5. **Test with declared dependencies**: Seed required published data in tests and keep `depends_on` accurate
6. **Use warnings for evolving contracts**: Emit warnings for soft constraints, errors for hard failures
7. **Document dependencies**: Clearly state what data you expect from `depends_on` plugins

## ADR0078 Boundary Rules

For object-scoped plugins (compilers/validators/generators), follow these rules:

1. Do not hardcode instance-specific endpoints in object plugin Python code (private IP or `.local` URLs).
2. Do not import peer object modules directly; object-to-object imports are forbidden.
3. Use dynamic object projection discovery via `load_object_projection_module()`; do not add static object path maps.
4. Capability-driven generator templates must be configured in module manifest `config.capability_templates`.
5. Keep object-specific logic in object modules; keep cross-object projection logic in shared/core modules.

Example `capability_templates` config in object module manifest:

```yaml
config:
  capability_templates:
    - capability_key: has_qos
      template: terraform/qos.tf.j2
      output_file: qos.tf
    - capability_key: has_wireguard
      template: terraform/vpn.tf.j2
      output_file: vpn.tf
    - capability_key: has_containers
      template: terraform/containers.tf.j2
      output_file: containers.tf
```

## ADR0068 Placeholder Policy Notes

When working with `base.validator.instance_placeholders`:

1. Placeholder tokens are reserved: `@required:<format>` and `@optional:<format>`.
2. To keep a literal string that starts with a placeholder-looking token in object YAML, prefix with `@@` so it is not parsed as a placeholder marker.
3. Instance payload must not contain unresolved placeholder tokens; validator emits `E6806`.
4. Rollout policy is configurable in plugin config:
   - `enforcement_mode: warn`
   - `enforcement_mode: warn+gate-new` (strict for selected statuses via `gate_statuses`)
   - `enforcement_mode: enforce` (strict for all rows)

## ADR0073 Secret Annotation Notes

Secret-aware annotations are also valid field markers:

1. `@secret`
2. `@required_secret:<format>`
3. `@optional_secret:<format>`

Compiler integration is split into two plugins:

1. `base.compiler.annotation_resolver` parses annotations and publishes:
   - `object_annotations`
   - `object_secret_annotations`
   - `row_annotations_by_instance`
   - `annotation_formats`
2. `base.compiler.instance_rows` consumes published annotation data for side-car secret merge and typed secret validation.

If your plugin needs annotation metadata, declare explicit dependency and subscribe:

```yaml
- id: my.compiler.consumer
  kind: compiler
  entry: compilers/my_consumer.py:MyConsumer
  stages: [compile]
  depends_on: [base.compiler.annotation_resolver]
```

```python
row_annotations = ctx.subscribe(
    "base.compiler.annotation_resolver",
    "row_annotations_by_instance",
)
formats = ctx.subscribe(
    "base.compiler.annotation_resolver",
    "annotation_formats",
)
```

Diagnostics used by secret merge flow:

1. `E7211`: unresolved secret marker in strict semantics
2. `E7212`: plaintext and decrypted side-car conflict on same path
3. `E7213`: decrypted value does not satisfy typed annotation format

## Pipeline Stages

```
Input/State
    │
    ▼
┌─────────────────┐
│ DISCOVER Stage  │  ← DiscovererPlugin (manifest/runtime bootstrap)
└─────────────────┘
    │
    ▼
┌─────────────────┐
│  COMPILE Stage  │  ← CompilerPlugin (transform, derive data)
└─────────────────┘
    │
    ▼
┌─────────────────┐
│ VALIDATE Stage  │  ← ValidatorYamlPlugin, ValidatorJsonPlugin
└─────────────────┘
    │
    ▼
┌─────────────────┐
│ GENERATE Stage  │  ← GeneratorPlugin (emit artifacts)
└─────────────────┘
    │
    ▼
┌─────────────────┐
│ ASSEMBLE Stage  │  ← AssemblerPlugin (workspace assembly + verification)
└─────────────────┘
    │
    ▼
┌─────────────────┐
│  BUILD Stage    │  ← BuilderPlugin (bundle/SBOM/release manifest)
└─────────────────┘
    │
    ▼
Release Output
```

## References

- ADR 0063: Plugin Microkernel Architecture
- ADR 0065: Plugin API Contract Specification
- ADR 0066: Plugin Testing and CI Strategy
- Source: `topology-tools/kernel/plugin_base.py`
- Source: `topology-tools/kernel/plugin_registry.py`
- Error catalog: `topology-tools/data/error-catalog.yaml`
