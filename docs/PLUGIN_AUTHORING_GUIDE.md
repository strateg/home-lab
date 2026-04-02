# Plugin Authoring Guide

**Last Updated:** 2026-03-29
**Related:** ADR 0063, ADR 0065, ADR 0080

This guide helps topology module developers create plugins that integrate with the v5
plugin microkernel and its stage/phase lifecycle (ADR 0080).

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Lifecycle: Stages and Phases](#lifecycle-stages-and-phases)
3. [Plugin Types](#plugin-types)
4. [Quick Start](#quick-start)
5. [Project Structure](#project-structure)
6. [Manifest Reference](#manifest-reference)
7. [PluginContext API](#plugincontext-api)
8. [Data Exchange (Publish/Subscribe)](#data-exchange-publishsubscribe)
9. [Phase Handlers](#phase-handlers)
10. [Conditional Execution (`when`)](#conditional-execution-when)
11. [Configuration](#configuration)
12. [Diagnostics and Error Handling](#diagnostics-and-error-handling)
13. [Parallel Execution Safety](#parallel-execution-safety)
14. [Testing](#testing)
15. [Best Practices](#best-practices)
16. [Migration from Legacy API](#migration-from-legacy-api)

---

## Architecture Overview

The plugin runtime follows a **microkernel** pattern (ADR 0063). The kernel handles:

- Manifest discovery and loading
- Dependency graph resolution
- Stage/phase execution ordering
- Timeout enforcement (default: 30s per plugin)
- Diagnostic aggregation
- Publish/subscribe data bus

Plugins are **pure units of work** — they receive a `PluginContext`, perform their task,
and return a `PluginResult`. All side effects go through the context API or declared file paths.

### Discovery Policy

1. Base manifest from CLI (`--plugins-manifest`) is loaded first.
2. Then `plugins.yaml` files from `class-modules/**` are loaded (lexicographic order).
3. Then `plugins.yaml` files from `object-modules/**` are loaded (lexicographic order).
4. Then project `plugins.yaml` files from project plugin root are loaded (lexicographic order).
5. Duplicate plugin IDs across manifests are **hard errors** (no override).

### Four-Level Boundary Model (ADR 0063 §4B)

```
Level 1: Global / Core          topology-tools/plugins/
Level 2: Class modules           topology/class-modules/**/plugins/
Level 3: Object modules          topology/object-modules/**/plugins/
Level 4: Project                 projects/<project>/plugins/ (monorepo) or <project-root>/plugins/ (standalone)
```

Rules:
- Class-level plugins **must not** reference `obj.*` or `inst.*` identifiers.
- Object-level plugins **must not** reference `inst.*` identifiers.
- A plugin may depend on plugins from its own level or higher only.
- Plugin IDs must remain globally unique across all discovered manifests (no level shadowing).

---

## Lifecycle: Stages and Phases

Every plugin runs within a **stage** and a **phase**. The kernel executes in strict order:

### Stages (ADR 0080 §2)

```
discover → compile → validate → generate → assemble → build
```

| Stage | Purpose | Plugin kinds |
|-------|---------|-------------|
| `discover` | Find and register plugin manifests | `discoverer` |
| `compile` | Transform raw YAML into compiled model | `compiler` |
| `validate` | Check model correctness | `validator_yaml`, `validator_json` |
| `generate` | Emit artifacts (Terraform, Ansible, docs) | `generator` |
| `assemble` | Build execution-root workspaces | `assembler` |
| `build` | Package, sign, verify release bundles | `builder` |

### Phases (ADR 0080 §3)

Within each stage, plugins execute in phase order:

```
init → pre → run → post → verify → finalize
```

| Phase | Semantic | Typical use |
|-------|----------|-------------|
| `init` | Load/prepare inputs | Module loaders, config resolvers |
| `pre` | Pre-conditions, governance checks | Schema guards, policy checks |
| `run` | Main business logic | Compilation, validation, generation |
| `post` | Post-processing, cross-cutting | Docs, diagrams, secondary outputs |
| `verify` | Quality gates | Integrity checks, contract validation |
| `finalize` | Summary and cleanup | Manifests, checksums, cleanup |

**Default phase is `run`.** Most plugins only need `run`; use other phases for
specialized lifecycle needs.

### Execution Order Within a Phase

Inside each `(stage, phase)` slice, plugins execute by:
1. `depends_on` DAG (dependency-respecting topological order)
2. `order` field (numeric tie-breaker)
3. Plugin `id` (lexical tie-breaker)

### Finalize Guarantee

`finalize` **always runs** for any started stage, even if an earlier phase fails.
Use `finalize` for cleanup, summary emission, and resource release.

---

## Plugin Types

### Discoverer Plugins (`kind: discoverer`)

Bootstrap discover-stage inventory/preflight logic before compile.

**Stage:** `discover`
**Order range:** 10–89

### Compiler Plugins (`kind: compiler`)

Transform or resolve the Object Model during compilation.

```python
from kernel.plugin_base import CompilerPlugin, PluginContext, PluginResult, Stage

class MyCompiler(CompilerPlugin):
    def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        diagnostics = []
        # Read raw YAML from ctx.raw_yaml or compiled model from ctx.compiled_json
        # Transform, resolve, publish results
        ctx.publish("my_output", {"resolved": "data"})
        return self.make_result(diagnostics)
```

**Stage:** `compile`
**Order range:** 30–89

### Validator Plugins (`kind: validator_yaml` / `validator_json`)

Check model correctness. Must not mutate data.

```python
from kernel.plugin_base import ValidatorJsonPlugin, PluginContext, PluginResult, Stage

class MyValidator(ValidatorJsonPlugin):
    def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        diagnostics = []
        compiled = ctx.compiled_json

        for instance in compiled.get("instances", []):
            if not instance.get("name"):
                diagnostics.append(self.emit_diagnostic(
                    code="E5001", severity="error", stage=stage,
                    message="Instance missing name",
                    path=f"instances[{instance.get('id', '?')}]",
                    hint="Add a 'name' field to the instance definition"
                ))

        return self.make_result(diagnostics)
```

**Stage:** `validate`
**Order range:** 90–189

### Generator Plugins (`kind: generator`)

Emit artifacts from the compiled model.

```python
from pathlib import Path
from kernel.plugin_base import GeneratorPlugin, PluginContext, PluginResult, Stage

class MyGenerator(GeneratorPlugin):
    def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        diagnostics = []
        out_dir = Path(ctx.output_dir) / "my-output"
        out_dir.mkdir(parents=True, exist_ok=True)

        files = []
        for item in ctx.compiled_json.get("items", []):
            out_file = out_dir / f"{item['id']}.tf"
            out_file.write_text(self._render(item))
            files.append(str(out_file))

        ctx.publish("my_generator_files", files)
        return self.make_result(diagnostics, output_data={"files": files})
```

**Stage:** `generate`
**Order range:** 190–399

### Assembler Plugins (`kind: assembler`)

Build execution-root workspaces (`.work/native`, `dist/`).

**Stage:** `assemble`
**Order range:** 400–499

### Builder Plugins (`kind: builder`)

Package, sign, verify release bundles.

**Stage:** `build`
**Order range:** 500–599

---

## Quick Start

### 1. Create Plugin File

```python
# topology/object-modules/mikrotik/plugins/validators/bridge_check.py

from kernel.plugin_base import (
    ValidatorJsonPlugin, PluginContext, PluginResult, Stage,
)

class BridgeValidator(ValidatorJsonPlugin):
    """Validate bridge interface naming and VLAN assignment."""

    def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        diagnostics = []
        max_len = ctx.config.get("max_bridge_name_length", 15)

        for bridge in ctx.compiled_json.get("bridges", []):
            name = bridge.get("name", "")
            if len(name) > max_len:
                diagnostics.append(self.emit_diagnostic(
                    code="E5401", severity="error", stage=stage,
                    message=f"Bridge name '{name}' exceeds {max_len} chars",
                    path=f"bridges.{name}",
                    hint=f"Shorten bridge name to {max_len} characters or fewer"
                ))

        return self.make_result(diagnostics)
```

### 2. Register in Manifest

```yaml
# topology/object-modules/mikrotik/plugins.yaml

schema_version: 1
plugins:
  - id: obj.mikrotik.validator.json.bridges
    kind: validator_json
    entry: plugins/validators/bridge_check.py:BridgeValidator
    api_version: "1.x"
    stages: [validate]
    phase: run
    order: 120
    depends_on: []
    config:
      max_bridge_name_length: 15
    config_schema:
      type: object
      properties:
        max_bridge_name_length:
          type: integer
          minimum: 1
          default: 15
    when:
      profiles: [production, modeled]
    description: "Validate bridge naming and VLAN constraints for MikroTik"
```

### 3. Write Tests

```python
# topology/object-modules/mikrotik/tests/test_bridge_validator.py

import pytest
from kernel.plugin_base import PluginContext, Stage

from plugins.validators.bridge_check import BridgeValidator


@pytest.fixture
def ctx():
    return PluginContext(
        topology_path="test",
        profile="production",
        model_lock={},
        compiled_json={
            "bridges": [
                {"name": "br-lan", "vlan_id": 100},
                {"name": "bridge-name-that-is-way-too-long", "vlan_id": 200},
            ]
        },
        config={"max_bridge_name_length": 15},
    )


def test_valid_bridge(ctx):
    ctx.compiled_json = {"bridges": [{"name": "br-lan", "vlan_id": 100}]}
    plugin = BridgeValidator("obj.mikrotik.validator.json.bridges")
    result = plugin.execute(ctx, Stage.VALIDATE)
    assert result.status.value == "SUCCESS"
    assert len(result.diagnostics) == 0


def test_long_bridge_name(ctx):
    plugin = BridgeValidator("obj.mikrotik.validator.json.bridges")
    result = plugin.execute(ctx, Stage.VALIDATE)
    assert result.has_errors
    assert result.diagnostics[0].code == "E5401"
```

### 4. Run

```bash
# Plugin is auto-discovered from object-module manifest
python topology-tools/compile-topology.py --profile production
```

---

## Project Structure

```
topology/object-modules/mikrotik/
├── plugins.yaml                     # Manifest — discovered by kernel
├── plugins/
│   ├── validators/
│   │   ├── bridge_check.py          # ValidatorJsonPlugin
│   │   └── device_names.py          # ValidatorYamlPlugin
│   ├── generators/
│   │   ├── terraform_mikrotik_generator.py  # GeneratorPlugin
│   │   └── bootstrap_mikrotik_generator.py  # GeneratorPlugin
├── templates/
│   ├── terraform/
│   │   ├── provider.tf.j2
│   │   └── bridges.tf.j2
│   └── bootstrap/
│       └── answer.toml.example.j2
├── tests/
│   ├── conftest.py
│   ├── test_bridge_validator.py
│   └── test_terraform_generator.py
└── testdata/
    ├── valid_topology.yaml
    └── expected_terraform/

topology-tools/plugins/generators/
├── terraform_helpers.py             # Shared Terraform helper functions
├── capability_helpers.py            # Shared capability-template mapping helpers
├── bootstrap_helpers.py             # Shared bootstrap-file config helpers
└── bootstrap_projections.py         # Shared bootstrap projection builders
```

---

## Manifest Reference

Every plugin is declared in a `plugins.yaml` manifest. Full field reference:

```yaml
schema_version: 1
plugins:
  - id: obj.mikrotik.validator.json.bridges     # Unique ID (required)
    kind: validator_json                          # Plugin kind (required)
    entry: plugins/validators/bridge_check.py:BridgeValidator  # Module:Class (required)
    api_version: "1.x"                            # API version (required)
    stages: [validate]                            # Stage list (required)
    phase: run                                    # Phase (default: run)
    order: 120                                    # Execution priority (required)

    # Dependencies
    depends_on: []                                # Plugin IDs this depends on
    requires_capabilities: []                     # Required capabilities

    # Configuration
    config: {}                                    # Default config values
    config_schema:                                # JSON Schema for config
      type: object
      properties: {}

    # Conditional execution (all conditions are AND)
    when:
      profiles: [production, modeled]             # Run only for these profiles
      capabilities: [cap.dns]                     # Run only if capabilities present
      pipeline_modes: [full]                      # Run only in these pipeline modes

    # Data bus contracts
    produces:
      - key: bridge_validation_report             # Published key name
        scope: stage_local                        # stage_local | pipeline_shared
        schema_ref: schemas/bridge_report.json    # Optional JSON Schema
        description: "Bridge validation results"
    consumes:
      - from_plugin: base.compiler.instance_rows  # Source plugin
        key: normalized_rows                      # Key to subscribe
        required: true                            # Fail if missing

    # Metadata
    compiled_json_owner: false                    # Only ONE per (stage, phase) can be true
    model_versions: ["0062-1.0"]                  # Supported model versions
    timeout: 30                                   # Seconds (default: 30)
    description: "Human-readable description"
```

### ID Convention

```
{level}.{module}.{kind}.{domain}.{name}

Examples:
  base.compiler.instance_rows          # Core compiler plugin
  base.generator.terraform_proxmox     # Core generator
  obj.mikrotik.validator.json.bridges  # Object-module validator
  cls.network.compiler.vlan_resolver   # Class-module compiler
```

### Order Ranges

| Stage | Range | Notes |
|-------|-------|-------|
| discover | 10–89 | Base manifest only |
| compile | 30–89 | Preserved from existing |
| validate | 90–189 | Preserved from existing |
| generate | 190–399 | Per ADR 0074 |
| assemble | 400–499 | New |
| build | 500–599 | New |

---

## PluginContext API

`PluginContext` is the shared context passed to every plugin. Key fields:

### Core Fields

| Field | Type | Description |
|-------|------|-------------|
| `topology_path` | `str` | Path to `topology.yaml` |
| `profile` | `str` | Runtime profile (`production`, `modeled`, etc.) |
| `model_lock` | `dict` | Framework dependency lock |
| `raw_yaml` | `dict` | Parsed YAML (for validators) |
| `compiled_json` | `dict` | Full compiled model (for validators/generators) |
| `output_dir` | `str` | Root output directory (for generators) |
| `config` | `dict` | Per-plugin configuration from manifest |

### Module Fields

| Field | Type | Description |
|-------|------|-------------|
| `classes` | `dict` | Class module metadata |
| `objects` | `dict` | Object module metadata |
| `capability_catalog` | `dict` | Capability definitions |
| `effective_capabilities` | `dict` | Resolved per-instance capabilities |
| `effective_software` | `dict` | Resolved per-instance software stacks |
| `instance_bindings` | `dict` | Instance-to-object bindings |

### Assemble/Build Fields

| Field | Type | Description |
|-------|------|-------------|
| `workspace_root` | `str` | `.work/native/` path |
| `dist_root` | `str` | `dist/` path |
| `assembly_manifest` | `dict` | Output of `assemble.finalize` |
| `signing_backend` | `str` | `age` / `gpg` / `none` |
| `release_tag` | `str` | Release version tag |
| `sbom_output_dir` | `str` | SBOM output directory |

### Diagnostic Fields

| Field | Type | Description |
|-------|------|-------------|
| `error_catalog` | `dict` | Error code definitions |
| `source_file` | `str` | Source YAML file path |
| `compiled_file` | `str` | Compiled JSON file path |

---

## Data Exchange (Publish/Subscribe)

Plugins exchange data through a typed publish/subscribe bus (ADR 0080 §6).

### Publishing

```python
def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
    result = self._compute_something(ctx.compiled_json)
    ctx.publish("my_result_key", result)
    return self.make_result([])
```

Declare in manifest:
```yaml
produces:
  - key: my_result_key
    scope: pipeline_shared
    description: "Computed result for downstream consumers"
```

### Subscribing

```python
def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
    rows = ctx.subscribe("base.compiler.instance_rows", "normalized_rows")
    # Use rows...
```

Declare in manifest:
```yaml
depends_on:
  - base.compiler.instance_rows
consumes:
  - from_plugin: base.compiler.instance_rows
    key: normalized_rows
    required: true
```

**Rules:**
1. You can only subscribe to plugins listed in your `depends_on`.
2. The producer must have `publish()`-ed the key before you subscribe.
3. `required: true` means missing data is a hard error.
4. Cross-stage subscriptions must use `pipeline_shared` scope keys.
5. `stage_local` keys are invalidated when their publishing stage ends.

### Scope

| Scope | Lifetime | Use when |
|-------|----------|----------|
| `stage_local` | Invalidated at stage end | Intermediate data not needed by later stages |
| `pipeline_shared` | Persists for entire pipeline | Data consumed by plugins in later stages |

---

## Phase Handlers

Most plugins only implement `execute()` for the `run` phase (default). For multi-phase
plugins, override phase-specific handlers:

```python
from kernel.plugin_base import CompilerPlugin, PluginContext, PluginResult, Stage, Phase

class MyMultiPhaseCompiler(CompilerPlugin):

    def on_init(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        """Load input files, resolve paths."""
        data = self._load_modules(ctx.topology_path)
        ctx.publish("loaded_modules", data)
        return self.make_result([])

    def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        """Main compilation logic (called during 'run' phase)."""
        modules = ctx.subscribe(self.plugin_id, "loaded_modules")
        result = self._compile(modules)
        ctx.publish("compiled_output", result)
        return self.make_result([])

    def on_verify(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        """Verify output integrity."""
        output = ctx.subscribe(self.plugin_id, "compiled_output")
        diagnostics = self._verify(output)
        return self.make_result(diagnostics)

    def on_finalize(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        """Emit summary, always runs even on failure."""
        return self.make_result([])
```

### Dispatch Rules

| Phase | Handler called | Fallback |
|-------|---------------|----------|
| `init` | `on_init(ctx, stage)` | Skip (no error) |
| `pre` | `on_pre(ctx, stage)` | Skip |
| `run` | `on_run(ctx, stage)` or `execute(ctx, stage)` | **Required** |
| `post` | `on_post(ctx, stage)` | Skip |
| `verify` | `on_verify(ctx, stage)` | Skip |
| `finalize` | `on_finalize(ctx, stage)` | Skip |

For the `run` phase, the kernel calls `on_run()` if defined, otherwise `execute()`.
All existing plugins with only `execute()` work unchanged.

---

## Conditional Execution (`when`)

Use `when` predicates to gate execution without code changes:

```yaml
when:
  profiles: [production]           # Only for production profile
  capabilities: [cap.ceph]        # Only if ceph capability is present
  pipeline_modes: [full]           # Only in full pipeline mode
```

All conditions are AND-ed. A skipped plugin returns `SKIPPED` status (not an error).

---

## Configuration

### Declaring Config

```yaml
config:
  terraform_version: ">= 1.6.0"
  strict_mode: false

config_schema:
  type: object
  properties:
    terraform_version:
      type: string
      default: ">= 1.6.0"
    strict_mode:
      type: boolean
      default: false
  required: [terraform_version]
```

### Accessing Config

```python
def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
    tf_version = ctx.config.get("terraform_version", ">= 1.6.0")
    strict = ctx.config.get("strict_mode", False)
    # ...
```

### Config Injection Precedence (ADR 0065)

1. Global defaults
2. Manifest `config` values
3. Environment variable overrides
4. Runtime/CLI overrides

Config is validated against `config_schema` at load time (pre-flight).
Validation failure is a **hard error** — plugin does not execute.

---

## Diagnostics and Error Handling

### Emitting Diagnostics

Use `self.emit_diagnostic()` for structured error/warning reporting:

```python
diagnostics.append(self.emit_diagnostic(
    code="E5401",                    # From error-catalog.yaml
    severity="error",                # "error" | "warning" | "info"
    stage=stage,                     # Current stage
    message="Bridge name too long",  # Human-readable
    path="bridges.br-wan",           # Resource path
    phase=Phase.RUN,                 # Optional: phase attribution
    hint="Shorten to 15 chars",      # Optional: remediation
    source_file="topology.yaml",     # Optional: source location
    source_line=42,                  # Optional
    source_column=5,                 # Optional
    confidence=1.0,                  # 0.0-1.0
))
```

### Returning Results

Use `self.make_result()` — it infers the status from diagnostics:

```python
return self.make_result(
    diagnostics=diagnostics,
    output_data={"files": generated_files},  # Optional
)
```

| Diagnostics content | Inferred status |
|---------------------|----------------|
| No diagnostics | `SUCCESS` |
| Warnings only | `PARTIAL` |
| Any errors | `FAILED` |

### Exception Handling

Unhandled exceptions are caught by the kernel and wrapped into `FAILED` with a traceback.
You don't need to catch everything — only catch exceptions you can handle meaningfully:

```python
def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
    diagnostics = []
    try:
        data = ctx.subscribe("base.compiler.instance_rows", "normalized_rows")
    except PluginDataExchangeError as exc:
        diagnostics.append(self.emit_diagnostic(
            code="E6901", severity="error", stage=stage,
            message=f"Cannot subscribe: {exc}",
            path="pipeline:data_bus"
        ))
        return self.make_result(diagnostics)

    # Main logic — let unexpected exceptions propagate to kernel
    self._validate(data)
    return self.make_result(diagnostics)
```

### Diagnostic Code Ranges

| Range | Domain |
|-------|--------|
| `E000x–E199x` | Data format/structure |
| `E200x–E299x` | Reference/relationship |
| `E300x–E399x` | Configuration/contract |
| `E400x–E499x` | Kernel/runtime |
| `E500x–E799x` | Domain-specific validation |
| `E800x` | Discover stage |
| `E810x` | Assemble stage |
| `E820x` | Build stage |
| `W800x` | Data bus undeclared key (transitional) |

---

## Parallel Execution Safety

When `--parallel-plugins` is enabled, plugins within the same `(stage, phase)` whose
DAG dependencies are satisfied may execute concurrently (ADR 0080 §9).

### Parallel-Safe Plugin Contract

Your plugin is parallel-safe if it:

1. **Does not assign `ctx.compiled_json`** (unless declared `compiled_json_owner: true`).
2. **Does not mutate** any shared `PluginContext` field other than through `ctx.publish()`.
3. **All outputs** go through `ctx.publish()` or to explicitly declared file paths.
4. **Side effects** are limited to file writes under declared output paths.

### What to Avoid

```python
# ❌ BAD: Mutating shared context
ctx.compiled_json["new_key"] = "value"

# ❌ BAD: Writing to undeclared paths
Path("/tmp/my_output.json").write_text(data)

# ✅ GOOD: Use publish for data sharing
ctx.publish("new_key", "value")

# ✅ GOOD: Write to declared output directory
(Path(ctx.output_dir) / "my-output" / "file.tf").write_text(data)
```

### Generator File Isolation

Each generator **must** write to non-overlapping paths. Declare your output files
in `produces` so the kernel can validate no two generators claim the same path.

### `compiled_json_owner`

Only **one plugin per `(stage, phase)`** may set `compiled_json_owner: true`.
This plugin is the sole writer of `ctx.compiled_json` in that phase.
All other plugins must treat `compiled_json` as read-only.

After the `compile` stage boundary, `compiled_json` is frozen — a deep-copied
read-only snapshot for all later stages.

---

## Testing

### Unit Tests (Plugin Isolation)

```python
import pytest
from kernel.plugin_base import PluginContext, Stage, PluginStatus

from plugins.validators.bridge_check import BridgeValidator


@pytest.fixture
def make_ctx():
    """Factory for test contexts with custom compiled_json."""
    def _make(compiled_json, config=None):
        return PluginContext(
            topology_path="test/topology.yaml",
            profile="production",
            model_lock={},
            compiled_json=compiled_json,
            config=config or {},
        )
    return _make


class TestBridgeValidator:
    def test_valid_bridges(self, make_ctx):
        ctx = make_ctx({"bridges": [{"name": "br-lan", "vlan_id": 100}]})
        plugin = BridgeValidator("obj.mikrotik.validator.json.bridges")
        result = plugin.execute(ctx, Stage.VALIDATE)

        assert result.status == PluginStatus.SUCCESS
        assert len(result.diagnostics) == 0

    def test_name_too_long(self, make_ctx):
        ctx = make_ctx(
            {"bridges": [{"name": "a-very-long-bridge-name", "vlan_id": 200}]},
            config={"max_bridge_name_length": 15},
        )
        plugin = BridgeValidator("obj.mikrotik.validator.json.bridges")
        result = plugin.execute(ctx, Stage.VALIDATE)

        assert result.status == PluginStatus.FAILED
        assert result.diagnostics[0].code == "E5401"

    def test_empty_bridges(self, make_ctx):
        ctx = make_ctx({"bridges": []})
        plugin = BridgeValidator("obj.mikrotik.validator.json.bridges")
        result = plugin.execute(ctx, Stage.VALIDATE)

        assert result.status == PluginStatus.SUCCESS
```

### Data Exchange Tests

```python
def test_subscribe_from_dependency(make_ctx):
    ctx = make_ctx({"instances": []})

    # Simulate upstream plugin publishing data
    ctx._current_plugin_id = "base.compiler.instance_rows"
    ctx._allowed_dependencies = set()
    ctx.publish("normalized_rows", [{"id": "node1"}])

    # Now test our plugin subscribing
    ctx._current_plugin_id = "obj.test.validator"
    ctx._allowed_dependencies = {"base.compiler.instance_rows"}

    rows = ctx.subscribe("base.compiler.instance_rows", "normalized_rows")
    assert rows == [{"id": "node1"}]
```

### Integration Tests

```python
def test_full_pipeline_with_plugin(tmp_path):
    """Run the actual pipeline and verify plugin output."""
    from kernel.plugin_registry import PluginRegistry

    registry = PluginRegistry(base_path=Path("topology-tools"))
    registry.load_manifest(Path("topology-tools/plugins/plugins.yaml"))

    ctx = PluginContext(
        topology_path=str(tmp_path / "topology.yaml"),
        profile="test-real",
        model_lock={},
        compiled_json=load_test_fixture("compiled.json"),
        output_dir=str(tmp_path / "generated"),
    )

    results = registry.execute_stage(Stage.VALIDATE, ctx)
    assert all(r.status != PluginStatus.FAILED for r in results)
```

---

## Best Practices

### Do

- **Declare everything** — `produces`, `consumes`, `depends_on`, `config_schema`.
- **Use `make_result()`** — don't construct `PluginResult` manually.
- **Use `emit_diagnostic()`** — structured diagnostics with error codes from the catalog.
- **Include `hint`** in diagnostics — actionable remediation advice.
- **Include `source_file`/`source_line`** when possible — helps users locate issues.
- **Keep plugins focused** — one concern per plugin. Split large plugins.
- **Set `timeout`** appropriately — default 30s may be too short for large generators.
- **Write tests** — unit tests with mock context, integration tests with real registry.
- **Use `pipeline_shared` scope** for data consumed by later stages.

### Don't

- **Don't mutate `ctx.compiled_json`** unless you're the declared `compiled_json_owner`.
- **Don't write files outside `ctx.output_dir`** (generators) or declared paths.
- **Don't import other plugins directly** — use `ctx.subscribe()` for data exchange.
- **Don't use global mutable state** — plugins may execute in parallel.
- **Don't swallow exceptions silently** — let unexpected errors propagate to kernel.
- **Don't hardcode paths** — use `ctx.output_dir`, `ctx.workspace_root`, etc.
- **Don't depend on execution order within the same phase** — use `depends_on` instead.

---

## Migration from Legacy API

The v5 plugin API replaced the earlier `topology_tools.plugin_api` module.

### Import Changes

| Legacy | Current |
|--------|---------|
| `from topology_tools.plugin_api import YamlValidatorPlugin` | `from kernel.plugin_base import ValidatorYamlPlugin` |
| `from topology_tools.plugin_api import JsonValidatorPlugin` | `from kernel.plugin_base import ValidatorJsonPlugin` |
| `from topology_tools.plugin_api import CompilerPlugin` | `from kernel.plugin_base import CompilerPlugin` |
| `from topology_tools.plugin_api import GeneratorPlugin` | `from kernel.plugin_base import GeneratorPlugin` |
| `PluginSeverity.ERROR` | `"error"` (string) |
| `PluginSeverity.WARNING` | `"warning"` (string) |
| `self.context.plugin_id` | `self.plugin_id` |
| `self.context.config` | `ctx.config` (passed as argument) |
| `self.context.log(...)` | Use standard `logging` module |

### Method Signature Changes

```python
# Legacy
def execute(self, yaml_dict, source_path) -> PluginResult:

# Current
def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
```

### Diagnostic Changes

```python
# Legacy
PluginDiagnostic(
    severity=PluginSeverity.ERROR,
    code="DEV001",
    message="Missing field",
    location={"file": source_path, "line": 1}
)

# Current
self.emit_diagnostic(
    code="E5001", severity="error", stage=stage,
    message="Missing field",
    path="devices.r1",
    source_file=ctx.source_file, source_line=1
)
```

### Manifest Changes

```yaml
# New required fields in manifest:
phase: run                          # Explicit phase (was implicit)
when:                               # Replaces profile_restrictions
  profiles: [production]
produces:                           # Declare outputs
  - key: my_output
    scope: pipeline_shared
consumes:                           # Declare inputs
  - from_plugin: base.compiler.x
    key: some_key
    required: true
```
