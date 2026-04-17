# ADR 0097 — Top 10 Architectural Findings Against Current Codebase

Date: 2026-04-17
Status: Findings for direct envelope-model cutover

## 1. `PluginContext` is still the effective owner of pipeline-visible state

File: `topology-tools/kernel/plugin_base.py`

Current state:
- `_published_data`
- `_published_meta`
- `_publish_events`
- `_subscribe_events`
- `_event_subscriptions`
- `_event_queues`
- `_event_history`

Impact:
Worker-side context still owns data-plane and event-plane behavior that ADR 0097 assigns to the main interpreter and `PipelineState`.

## 2. `SerializablePluginContext` preserves the wrong transport boundary

File: `topology-tools/kernel/plugin_base.py`

Current state:
- transports `compiled_json_bytes`
- transports `plugin_config_bytes`
- transports `published_data_bytes`

Impact:
The runtime still serializes a live context-shaped object instead of a snapshot-shaped input contract.

## 3. `_execute_plugin_isolated()` still returns merge-back payloads

File: `topology-tools/kernel/plugin_registry.py`

Current state:
- returns `(PluginResult, published_data)`

Impact:
Worker output is still shaped around legacy published-data recovery rather than `PluginExecutionEnvelope`.

## 4. `_execute_phase_parallel()` still reconstructs shared state after worker execution

File: `topology-tools/kernel/plugin_registry.py`

Current state:
- collects `wavefront_published_data`
- merges it back into `ctx._published_data`

Impact:
This is the clearest remaining violation of the target ownership model.

## 5. Manifest routing is still mostly legacy

Files:
- `topology-tools/kernel/plugin_registry.py`
- `topology-tools/plugins/plugins.yaml`

Current state:
- `subinterpreter_compatible` dominates
- `execution_mode` is rare
- `input_view` is absent

Impact:
The manifest layer is not yet expressing the runtime contract that ADR 0097 defines.

## 6. `module_loader` still mutates ambient topology maps in context

File: `topology-tools/plugins/compilers/module_loader_compiler.py`

Current state:
- writes `ctx.classes = ...`
- writes `ctx.objects = ...`

Impact:
This keeps authoritative model assembly inside worker-owned mutable context rather than main-interpreter commit.

## 7. `EffectiveModelCompiler` still mixes proposal and authority

File: `topology-tools/plugins/compilers/effective_model_compiler.py`

Current state:
- `ctx.publish("effective_model_candidate", candidate)`
- `ctx.compiled_json = candidate`

Impact:
The plugin both proposes and authoritatively mutates compiled-model state, violating ADR 0097.

## 8. `InstanceRowsCompiler` is still a migration bottleneck

File: `topology-tools/plugins/compilers/instance_rows_compiler.py`

Current state:
- central compiler
- performs multiple policy, normalization, annotation, and validation responsibilities
- publishes `normalized_rows`, heavily consumed downstream

Impact:
This is the highest-value candidate for decomposition before the new model can become easy to reason about.

## 9. Event-plane API is richer than the target architecture currently needs

File: `topology-tools/kernel/plugin_base.py`

Current state:
- `emit()`
- `subscribe_topic()`
- `poll_events()`
- event history and per-plugin queues

Impact:
ADR 0097 only needs envelope-level emitted events in the first stable model. The current worker-side event bus is a complexity amplifier.

## 10. Tests still validate legacy mechanics more than new ownership semantics

Files: `tests/**`

Observed project-level signals:
- `_set_execution_context(...)`: 142 matches in 49 test files
- `get_published_data(...)`: 7 matches in 6 test files
- no references yet to `PipelineState`, `PluginExecutionEnvelope`, `PluginInputSnapshot`, or `run_plugin_once()` in tests

Impact:
The safety net is strong, but the primary validation surface is still aimed at the legacy context model.

## Finding Summary

The current project is not blocked by missing ideas. It is blocked by the fact that:

- transport is still context-shaped;
- scheduler still performs merge-back recovery;
- key plugins still mutate ambient state;
- tests still primarily protect the old model.

This confirms that the correct next move is a direct primary-path cutover to envelope-model execution rather than prolonged coexistence of two semantic models.
