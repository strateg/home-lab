# Plugin Envelope Model Guide

**ADR:** 0097
**Status:** Active
**Updated:** 2026-04-21

This guide explains the actor-style dataflow execution model for plugins introduced in ADR 0097.

---

## Overview

The plugin runtime uses an **envelope model** for execution:

1. **Snapshot** — Immutable input provided to plugin
2. **Execution** — Plugin computes outputs locally
3. **Envelope** — Plugin returns proposed outputs
4. **Commit** — Main interpreter validates and commits

This enables isolated parallel execution on Python 3.14 subinterpreters.

---

## Execution Flow

```
┌─────────────────────────────────────────────────────────────┐
│                     Main Interpreter                         │
│  ┌─────────────────────────────────────────────────────┐    │
│  │                  Pipeline State                      │    │
│  │  - Committed published data                          │    │
│  │  - Consume resolution                                │    │
│  │  - Stage-local invalidation                          │    │
│  └─────────────────────────────────────────────────────┘    │
│         │                                    ▲               │
│         │ 1. Build Snapshot                  │ 4. Commit     │
│         ▼                                    │               │
│  ┌─────────────────────────────────────────────────────┐    │
│  │              PluginInputSnapshot                     │    │
│  │  - Resolved consumes payloads                        │    │
│  │  - Plugin config                                     │    │
│  │  - Stage/phase identity                              │    │
│  │  - ctx.objects, ctx.config (snapshot)                │    │
│  └─────────────────────────────────────────────────────┘    │
│         │                                    ▲               │
│         │ 2. Dispatch                        │ 3. Return     │
│         ▼                                    │               │
├─────────────────────────────────────────────────────────────┤
│                   Worker (Subinterpreter)                    │
│  ┌─────────────────────────────────────────────────────┐    │
│  │              Plugin Execution                        │    │
│  │  - Read snapshot inputs                              │    │
│  │  - Local computation                                 │    │
│  │  - Append to local outbox (publish/emit)             │    │
│  └─────────────────────────────────────────────────────┘    │
│         │                                                    │
│         ▼                                                    │
│  ┌─────────────────────────────────────────────────────┐    │
│  │            PluginExecutionEnvelope                   │    │
│  │  - PluginResult (status, diagnostics)                │    │
│  │  - Published messages (proposed)                     │    │
│  │  - Emitted events (proposed)                         │    │
│  └─────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

---

## Execution Modes

### `subinterpreter` (Default)

Isolated parallel execution on Python 3.14 subinterpreters.

**Requirements:**
- Plugin receives immutable snapshot
- Plugin writes only to local outbox
- No direct context field mutation
- No shared mutable state access

**Benefits:**
- True parallelism (no GIL contention)
- Isolation (failure doesn't corrupt state)
- Deterministic (same input → same output)

**Current fleet:** 74 plugins (88.1%)

### `main_interpreter`

Sequential execution in main interpreter with envelope semantics.

**When required:**
- Plugin mutates `ctx` fields directly
- Plugin accesses `ctx.config.get("plugin_registry")`
- Plugin uses dynamic module loading

**Current fleet:** 10 plugins (11.9%)

### `thread_legacy` (Deprecated)

Legacy compatibility mode with context merge-back.

**Status:** Deprecated. Do not use for new plugins.

**Current fleet:** 0 plugins

---

## Plugin Implementation Patterns

### Compatible Pattern (Subinterpreter)

```python
def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
    # 1. Read from snapshot inputs
    config_value = ctx.config.get("some_config")
    consumed_data = ctx.subscribe("source_topic")
    objects = ctx.objects  # snapshot

    # 2. Local computation (no shared state)
    result = self._process(consumed_data, config_value)

    # 3. Write to local outbox
    ctx.publish("output_topic", result)

    return PluginResult.success(
        plugin_id=self.id,
        api_version=self.api_version,
        diagnostics=[],
    )
```

### Incompatible Pattern (Requires main_interpreter)

```python
def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
    # INCOMPATIBLE: Direct context mutation
    ctx.model_lock = loaded_payload  # ❌ Mutates ctx field

    # INCOMPATIBLE: Registry access
    registry = ctx.config.get("plugin_registry")  # ❌ Accesses registry

    # INCOMPATIBLE: Dynamic loading
    module = importlib.util.module_from_spec(spec)  # ❌ Dynamic import

    return PluginResult.success(...)
```

---

## Compatibility Checklist

Use this checklist to determine if your plugin can use `subinterpreter` mode:

### Input Patterns

| Pattern | Compatible | Notes |
|---------|------------|-------|
| `ctx.config.get("key")` | ✅ | Read-only config access |
| `ctx.subscribe("topic")` | ✅ | Resolved by scheduler |
| `ctx.objects` | ✅ | Snapshot input |
| `ctx.raw_yaml` | ✅ | Snapshot input |
| `ctx.compiled_json` | ✅ | Snapshot input |

### Output Patterns

| Pattern | Compatible | Notes |
|---------|------------|-------|
| `ctx.publish("topic", data)` | ✅ | Local outbox append |
| `ctx.emit(event)` | ✅ | Local outbox append |
| `return PluginResult.success()` | ✅ | Standard return |

### Incompatible Patterns

| Pattern | Compatible | Reason |
|---------|------------|--------|
| `ctx.model_lock = value` | ❌ | Direct field mutation |
| `ctx.workspace_root = path` | ❌ | Direct field mutation |
| `ctx.config["key"] = value` | ❌ | Config mutation |
| `ctx.config.get("plugin_registry")` | ❌ | Registry access |
| `importlib.util.module_from_spec()` | ❌ | Dynamic loading |
| `ctx.changed_input_scopes = value` | ❌ | Direct field mutation |

---

## Manifest Declaration

### Subinterpreter Mode (Default for New Plugins)

```yaml
- id: my.plugin.example
  kind: compiler
  execution_mode: subinterpreter
  consumes:
    - topic: input_data
      from_plugin: upstream.plugin
  produces:
    - topic: output_data
```

### Main Interpreter Mode (When Required)

```yaml
- id: my.plugin.context_mutator
  kind: assembler
  execution_mode: main_interpreter  # Required: mutates ctx fields
  consumes:
    - topic: assembled_files
  produces:
    - topic: workspace_ready
```

---

## Migration Guide

### From Legacy to Envelope

1. **Audit context usage:**
   - List all `ctx.field = value` assignments
   - List all `ctx.config.get("plugin_registry")` calls
   - List all `importlib` usage

2. **Refactor if possible:**
   - Replace direct mutation with `ctx.publish()`
   - Move registry access to manifest `consumes`
   - Replace dynamic loading with static imports

3. **Set execution mode:**
   - If all patterns are compatible: `execution_mode: subinterpreter`
   - If any incompatible patterns remain: `execution_mode: main_interpreter`

4. **Test:**
   ```bash
   # Compile with plugin in subinterpreter mode
   V5_SECRETS_MODE=passthrough .venv/bin/python topology-tools/compile-topology.py
   ```

### Incompatible Plugin Documentation

If your plugin must remain in `main_interpreter` mode, document the reason:

```yaml
- id: my.plugin.context_mutator
  kind: assembler
  execution_mode: main_interpreter
  # ADR 0097 incompatibility: mutates ctx.workspace_root
```

---

## Current Fleet Status

| Execution Mode | Count | Percentage |
|----------------|-------|------------|
| `subinterpreter` | 74 | 88.1% |
| `main_interpreter` | 10 | 11.9% |
| `thread_legacy` | 0 | 0% |

### Incompatible Plugins (main_interpreter required)

| Plugin ID | Reason |
|-----------|--------|
| `base.discover.manifest_loader` | Mutates ctx.config |
| `base.compiler.model_lock_loader` | Mutates ctx.model_lock |
| `base.assembler.changed_scopes` | Mutates ctx.changed_input_scopes |
| `base.assembler.workspace` | Mutates ctx.workspace_root |
| `base.assembler.manifest` | Mutates ctx.assembly_manifest |
| `base.assembler.deploy_bundle` | Dynamic module loading |
| `base.assembler.artifact_contract_guard` | Registry access |
| `base.builder.bundle` | Mutates ctx.dist_root |
| `base.builder.sbom` | Mutates ctx.sbom_output_dir |
| `base.builder.artifact_family_summary` | Registry access |

---

## Technical References

- **ADR 0097:** `adr/0097-subinterpreter-parallel-plugin-execution.md`
- **Implementation:** `topology-tools/kernel/plugin_registry.py`
- **Data classes:** `topology-tools/kernel/plugin_base.py`
  - `PluginInputSnapshot`
  - `PluginExecutionEnvelope`
  - `SubscriptionValue`
  - `PublishedMessage`
  - `EmittedEvent`
- **Migration evidence:** `adr/0097-analysis/`

---

## FAQ

### Q: Can file I/O be used in subinterpreter mode?

**A:** Yes. File reads and writes work in Python 3.14 subinterpreters. Common patterns like `yaml.safe_load()`, `json.dump()`, and Jinja2 template rendering are compatible.

### Q: What about logging?

**A:** Standard Python logging works in subinterpreters. Logs are collected and routed by the main interpreter.

### Q: How do I know if my plugin is compatible?

**A:** Run the compatibility checklist above. If all patterns are compatible, your plugin can use `subinterpreter` mode.

### Q: What happens if I set wrong execution mode?

**A:** If you use `subinterpreter` mode for an incompatible plugin:
- Context mutations will not propagate to pipeline state
- Registry access will fail
- Dynamic loading may fail

The scheduler will not catch these errors automatically. Test thoroughly.

### Q: Is `thread_legacy` still supported?

**A:** Yes, but deprecated. It exists only for migration compatibility. Do not use for new plugins. Zero plugins currently use this mode.
