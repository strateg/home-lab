# ADR 0097 Implementation Plan — Direct Envelope-Model Cutover

Status: Active plan
Date: 2026-04-17

## Baseline already completed

1. ADR 0097 updated to actor-style ownership model.
2. ADR 0099 updated to align tests with snapshot/envelope/pipeline-state semantics.
3. ADR consistency validation is passing.
4. SWOT and current-state findings confirm that legacy context semantics are still dominant in code.

## Decision for implementation strategy

The project will **cut over directly to the envelope model as the primary execution path**.

This means:

- no new runtime work should deepen shared mutable `PluginContext` semantics;
- no new primary execution path should depend on worker merge-back into shared `_published_data`;
- compatibility code may exist temporarily, but the implementation target is immediate main-path ownership correction.

## Workstream A — Introduce direct transport contracts

### Target files
- `topology-tools/kernel/plugin_base.py`

### Tasks
1. Add runtime value objects:
   - `PluginInputSnapshot`
   - `SubscriptionValue`
   - `PublishedMessage`
   - `EmittedEvent`
   - `PluginExecutionEnvelope`
2. Keep `PluginResult` as semantic plugin result, not transport envelope.
3. Add local-outbox semantics to `PluginContext`:
   - `publish()` appends `PublishedMessage`
   - `emit()` appends `EmittedEvent`
   - `subscribe()` reads from snapshot-provided resolved subscriptions only
4. Mark `SerializablePluginContext` as legacy transport and stop using it in the primary path.

### Exit gate
- direct execution path can run a plugin from snapshot and produce an envelope without shared bus mutation.

## Workstream B — Introduce main-interpreter `PipelineState`

### Target files
- new: `topology-tools/kernel/pipeline_runtime.py`
- callers in `topology-tools/kernel/plugin_registry.py`

### Tasks
1. Introduce `PipelineState` with ownership of:
   - committed published values
   - consume resolution
   - stage-local invalidation
   - schema validation for produced payloads
   - `commit_envelope()`
2. Move stage-local cleanup responsibility out of `PluginContext` runtime core.
3. Centralize commit-time validation in main interpreter.

### Exit gate
- published data becomes pipeline-visible only through `PipelineState.commit_envelope()`.

## Workstream C — Replace merge-back scheduler flow

### Target files
- `topology-tools/kernel/plugin_registry.py`
- new: `topology-tools/kernel/plugin_runner.py`

### Tasks
1. Implement `run_plugin_once(snapshot, plugin_spec) -> PluginExecutionEnvelope`.
2. Change `_execute_plugin_isolated()` to return envelope only.
3. Change `_execute_phase_parallel()` flow to:
   - resolve consumes
   - build snapshot
   - dispatch worker
   - receive envelope
   - validate envelope
   - commit via `PipelineState`
4. Remove main-path merge-back into `ctx._published_data`.
5. Keep crash isolation: failed worker => no envelope commit.

### Exit gate
- `_execute_phase_parallel()` no longer merges worker-owned `_published_data` into shared context as runtime authority.

## Workstream D — Representative plugin cutover

### Priority order
1. `topology-tools/plugins/compilers/module_loader_compiler.py`
2. `topology-tools/plugins/compilers/effective_model_compiler.py`
3. `topology-tools/plugins/compilers/instance_rows_compiler.py`
4. one representative validator
5. one representative generator

### Tasks

#### D1. `module_loader`
- stop treating `ctx.classes` and `ctx.objects` mutation as authoritative runtime state;
- publish candidate payloads for commit instead.

#### D2. `effective_model`
- keep candidate construction local;
- publish `effective_model_candidate` only;
- move authoritative `compiled_json` assignment into main-interpreter commit logic.

#### D3. `instance_rows`
Split at minimum into:
- annotation/secret resolution
- row normalization
- semantic/shape validation

#### D4. Representative validator
- choose one declarative validator and migrate it fully to snapshot-only inputs and envelope-only outputs.

#### D5. Representative generator
- choose one generator path and remove reliance on ambient shared registry semantics where possible.

### Exit gate
- at least one compiler path, one validator, and one generator prove the end-to-end snapshot/envelope/commit model.

## Workstream E — Manifest contract cutover

### Target files
- `topology-tools/plugins/plugins.yaml`
- manifest schema definitions and loaders
- `topology-tools/kernel/plugin_registry.py`

### Tasks
1. Promote `execution_mode` as the primary routing contract:
   - `subinterpreter`
   - `main_interpreter`
   - `thread_legacy`
2. Treat `subinterpreter_compatible` as transitional compatibility metadata only.
3. Introduce `input_view` only after representative plugin cutovers show where snapshot minimization matters.

### Exit gate
- runtime routing logic uses `execution_mode` as canonical contract.

## Test backlog aligned to ADR 0099

### New primary tests
1. `tests/runtime/worker_runner/`
   - snapshot serialization/deserialization
   - envelope serialization/deserialization
   - plugin crash => failed envelope / no commit
2. `tests/runtime/pipeline_state/`
   - `commit_envelope()`
   - stage-local visibility
   - stage-local invalidation
   - produced-payload validation
3. `tests/runtime/scheduler/`
   - consumes resolved before dispatch
   - execution-mode routing
   - no merge-back semantics in primary path
4. `tests/runtime/parity/`
   - serial vs subinterpreter committed-output parity
   - parity of statuses and diagnostics
5. `tests/plugins/unit/`
   - plugin returns envelope-consumable outputs from snapshot inputs

### Transitional tests
- existing context-heavy registry tests remain as compatibility coverage only until cutover is complete.

## Immediate architectural backlog by file

### `topology-tools/kernel/plugin_base.py`
- add snapshot/envelope contracts
- add local outbox fields
- stop growing shared data/event bus semantics
- reduce event plane to envelope-level emit model for main path

### `topology-tools/kernel/plugin_registry.py`
- stop using `ctx.get_published_data()` as primary runtime registry
- stop merging `wavefront_published_data` into shared context as authoritative state
- use `PipelineState` and snapshot builder

### `topology-tools/kernel/plugin_runner.py` (new)
- serial runner
- subinterpreter runner
- `run_plugin_once()`

### `topology-tools/kernel/pipeline_runtime.py` (new)
- `PipelineState`
- snapshot builder
- consume resolution
- commit logic
- stage-local invalidation

## Hard stop rules during implementation

Do not add new plugins or new runtime code that:
- directly mutates `ctx.classes`, `ctx.objects`, or `ctx.compiled_json` as authoritative state;
- depends on `ctx.get_published_data()` as live runtime registry;
- depends on worker-side event polling as stable architecture.

## Completion criteria

This plan is complete when:

1. the primary execution path is snapshot/envelope-native;
2. main interpreter alone owns commit into pipeline-visible state;
3. worker merge-back is removed from the primary runtime path;
4. representative plugin cutovers prove the model on critical paths;
5. ADR 0099 primary tests validate the new runtime directly;
6. legacy context tests are no longer the main source of truth for runtime behavior.
