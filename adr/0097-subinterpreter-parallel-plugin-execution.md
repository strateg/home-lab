# ADR 0097: Actor-Style Dataflow Execution for Plugins on Python 3.14 Subinterpreters

- Status: In Progress
- Date: 2026-04-15
- Revised: 2026-04-20
- Depends on: ADR 0063, ADR 0080, ADR 0086, ADR 0098
- Follow-up: ADR 0099 (test architecture migration for snapshot/envelope/pipeline-state runtime)

## Implementation Progress

| Phase | Status | Evidence |
|-------|--------|----------|
| **Infrastructure Waves 1-5** | ✅ COMPLETE | `adr/0097-analysis/evidence/WAVE-*-EVIDENCE.md` |
| **PR1** Contracts + Envelope Path | ✅ COMPLETE | `adr/0097-analysis/PR1-EXECUTION-CHECKLIST.md` |
| **PR2** Scheduler Cutover | ⏳ NOT STARTED | — |
| **PR3** Representative Plugin Migrations | ⏳ NOT STARTED | — |
| **PR4+** Fleet Migration | ⏳ NOT STARTED | — |

### Completed Components

- `PluginInputSnapshot`, `PluginExecutionEnvelope` dataclasses
- `SubscriptionValue`, `PublishedMessage`, `EmittedEvent` dataclasses
- `PluginContext.from_snapshot()` local-facade constructor
- `run_plugin_once()` worker runner
- `PipelineState` with `commit_envelope()`, `resolve_subscription()`, `invalidate_stage_local_data()`
- `_build_input_snapshot()` helper in registry
- Test coverage: dataclasses, commit, visibility, runner

### Next Steps

1. **PR2**: Scheduler cutover — route all plugins through envelope/commit flow
2. **PR2**: Introduce `execution_mode` manifest field
3. **PR3**: Migrate representative plugins (module_loader, effective_model)
4. **PR4+**: Fleet migration and legacy cleanup

## Context

The project uses a plugin-based microkernel pipeline with staged execution:
`discover -> compile -> validate -> generate -> assemble -> build`.

The runtime is migrating to Python 3.14 subinterpreters for isolated parallel execution. This surfaced a deeper mismatch:

- subinterpreters assume isolation and message passing;
- current plugin semantics are still centered around a mutable shared `PluginContext`.

Current context usage mixes responsibilities that should be separated:

- plugin execution input;
- runtime-local helper API;
- pipeline-visible publish/subscribe state;
- event-plane state;
- partial orchestration concerns.

This weakens ownership boundaries, increases reasoning complexity, and complicates deterministic behavior under isolation.

At the time of this revision, the codebase still materially reflects the legacy model:

- `PluginContext` still owns pipeline-visible data-plane and event-plane structures;
- `SerializablePluginContext` still transports context-shaped runtime state into isolated execution;
- parallel execution still merges worker-published payloads back into a shared main-interpreter context;
- manifest routing is still primarily expressed through `subinterpreter_compatible` rather than `execution_mode`;
- the test suite is still dominated by legacy context-oriented runtime assertions.

ADR 0097 therefore defines both the target architecture and the migration boundary that existing compatibility code must converge toward.

## Decision

The runtime standard is changed to an **actor-style dataflow model**.

### D1. Ownership model

**Main interpreter is the sole owner of pipeline-global state**, including:

- plugin scheduling;
- dependency resolution;
- stage/phase orchestration;
- consume resolution;
- schema validation of produced payloads;
- commit of produced messages;
- stage-local invalidation;
- execution tracing, retries, metrics, and failure handling.

**Worker interpreters own only per-invocation local execution**, including:

- plugin code execution;
- local plugin state;
- local diagnostics accumulation;
- local outbox construction.

Workers must not directly mutate pipeline-global state.

### D2. Invocation runtime model

Each plugin invocation follows:

`input snapshot -> local execution -> execution envelope -> scheduler validation -> commit`

### D3. Input contract

Plugins receive an immutable `PluginInputSnapshot` containing only:

- plugin-visible input data;
- resolved consumes payloads;
- stage and phase identity;
- plugin config;
- required execution metadata.

Snapshot does not include mutable pipeline-owned publish/subscribe stores.

### D4. Output contract

Plugins return `PluginExecutionEnvelope` containing:

- `PluginResult`;
- local published messages;
- local emitted events;
- optional execution metadata.

Envelope is a **proposal**, not a commit.

### D5. Publish/subscribe semantics

- `subscribe` is resolved by the scheduler before dispatch.
- plugin reads only snapshot-resolved inputs.
- `publish` appends to worker-local outbox.
- published data becomes pipeline-visible only after scheduler validation and commit.

### D6. Event semantics

Event plane is retained only as envelope-level emitted events.

Worker-side event queues/subscriptions/runtime buses are not part of the stable execution model.
Routing/buffering/fan-out/logging of events is main-interpreter-owned.

### D7. Execution modes

Plugins must declare execution mode explicitly:

- `subinterpreter`
- `main_interpreter`
- `thread_legacy`

`thread_legacy` is migration-only and must not be treated as long-term default.
Scheduler routing is mode + policy driven.

### D8. PluginContext semantics

`PluginContext` remains author-facing API surface, but only as a local facade over:

- immutable input snapshot;
- local publish outbox;
- local event outbox.

`PluginContext` is no longer owner of pipeline-global mutable state.

### D9. Serialization boundary

Cross-interpreter transport is defined by:

- serializable `PluginInputSnapshot`;
- serializable `PluginExecutionEnvelope`.

Runtime must not serialize/restore mutable pipeline bus state into worker interpreters.

### D10. Runtime module decomposition

Runtime implementation is decomposed into three responsibilities:

1. `plugin_registry.py` — manifest loading, spec validation, dependency graph, plugin entry loading.
2. `pipeline_runtime.py` — `PipelineState`, snapshot builder, consume resolution, envelope commit, stage-local invalidation.
3. `plugin_runner.py` — `run_plugin_once(snapshot, plugin_spec) -> envelope`, with serial and subinterpreter runners.

### D11. Plugin implementation style contract

New and migrated plugins must follow:

- one explicit snapshot input;
- local computation and local indexes only;
- no direct mutation of shared runtime state;
- output via `PluginResult` + outbox-driven envelope.

The following patterns are disallowed in the target model:

- direct mutation of `ctx.classes`, `ctx.objects`, `ctx.compiled_json`;
- event-plane polling logic inside worker execution;
- reliance on `ctx.get_published_data()` as live pipeline registry.

### D12. Manifest/runtime contract evolution

Manifest execution routing contract is normalized around `execution_mode` (`subinterpreter`, `main_interpreter`, `thread_legacy`).

`consumes` and `produces` remain first-class runtime contracts.

An optional `input_view` contract may be introduced to reduce snapshot payload size for plugins requiring partial views.

### D13. Compatibility boundary for legacy runtime APIs

Legacy context-owned data-plane and event-plane mechanics may remain temporarily as migration shims, but they are **compatibility-only**.

They must not be extended as the architectural source of truth for the new runtime model. In particular:

- new primary execution paths must not depend on shared mutable context bus semantics;
- worker-side event routing must remain envelope-level until main-interpreter ownership is fully established;
- merge-back of worker-owned mutable bus state is transitional technical debt, not accepted target design.

### D14. Migration anchors and representative cutovers

Migration success is not measured only by runtime scaffolding. It also requires representative plugin cutovers that prove the model on critical paths.

The following plugin categories are migration anchors:

- one representative module-loading/compiler path;
- `EffectiveModelCompiler` as the authoritative compiled-model boundary case;
- `InstanceRowsCompiler` as the central high-complexity compiler path;
- at least one representative validator;
- at least one representative generator.

## Consequences

### Positive

- execution model aligns with Python 3.14 subinterpreter isolation;
- publish/subscribe ownership is explicit;
- deterministic reasoning improves;
- worker failure cannot partially mutate pipeline-visible state;
- serial and subinterpreter execution are easier to parity-test;
- future replay/caching become easier.

### Negative

- plugin runtime contracts require refactoring;
- `PluginContext` semantics change even if API surface remains similar;
- tests assuming shared mutable context need migration;
- some plugins may temporarily remain outside subinterpreters.

## Alternatives Considered

### A1. Keep shared mutable context and only switch executor

Rejected. Preserves incorrect ownership model and ambiguous runtime semantics.

### A2. Keep current `PluginContext` and merge worker state back after execution

Rejected. Keeps hidden shared-state mental model and requires state reconstruction post-isolation.

### A3. Use multiprocessing as primary runtime

Not selected. Provides isolation but does not solve ownership/pub-sub semantics by itself and is heavier for current architecture.

### A4. Introduce queue-based streaming immediately

Deferred. May be useful later for selected workloads, but not required for first stable actor-style runtime.

## Implementation Notes

### Phase 1: Runtime contracts

In `plugin_base.py`, introduce transport/value objects:

- `PluginInputSnapshot`
- `SubscriptionValue`
- `PublishedMessage`
- `EmittedEvent`
- `PluginExecutionEnvelope`

`PluginResult` remains semantic plugin result, but not transport envelope.

### Phase 2: Local context facade

Refactor `PluginContext` to snapshot + local outboxes.

- `publish()` no longer commits.
- `subscribe()` no longer reads pipeline-global mutable state.
- `emit()` appends only to local event outbox.

Context-owned pipeline bus internals are removed from the architecture core.

### Phase 3: Main-interpreter `PipelineState`

Introduce scheduler-owned `PipelineState` responsible for:

- committed published data;
- consume resolution;
- schema validation;
- stage-local invalidation;
- `commit_envelope()`.

### Phase 4: Runner split and scheduler flow

Scheduler flow becomes:

1. resolve consumes;
2. build `PluginInputSnapshot`;
3. dispatch worker runner;
4. collect `PluginExecutionEnvelope`;
5. validate produced payloads/contracts;
6. commit to `PipelineState`.

No worker-side merge-back of mutable pipeline bus state.

### Phase 5: Plugin migration priorities

1. Keep declarative validators that already behave as deterministic, resolved-input processors as migration references (for style and SDK usage).
2. Refactor `EffectiveModelCompiler` so it publishes candidate model payloads; authoritative `compiled_json` assignment is performed by scheduler commit logic.
3. Decompose `InstanceRowsCompiler` at minimum into:
   - annotation/secret resolution;
   - row normalization;
   - semantic/shape validation.

### Phase 6: Manifest contract cutover

- promote `execution_mode` as primary execution routing field;
- treat `thread_legacy` as temporary migration mode;
- optionally introduce `input_view` for snapshot minimization where justified.

### Phase 7: Legacy-runtime decommissioning gates

- stop extending `SerializablePluginContext` as primary transport;
- remove worker merge-back of `_published_data` from the primary execution path;
- demote context-owned event bus features to compatibility-only support unless explicitly re-adopted by a future ADR.
- ensure primary runtime tests validate `PipelineState`/envelope semantics rather than legacy context internals.

## Acceptance Criteria

This ADR is implemented when all conditions are true:

1. plugins execute against immutable input snapshots;
2. workers cannot directly mutate pipeline-global publish/subscribe state;
3. `publish()` appends only to local outbox;
4. `subscribe()` resolves only against scheduler-provided inputs;
5. scheduler validates and commits published messages;
6. stage-local data is invalidated by main-interpreter-owned pipeline state;
7. compatible plugins run in parallel via subinterpreters on Python 3.14;
8. serial and subinterpreter execution are parity-tested for supported plugins;
9. worker failure does not leak partial published state;
10. `execution_mode` governs runtime routing;
11. authoritative compiled model state is committed in main interpreter, not mutated inside worker plugins;
12. the primary execution path no longer depends on worker merge-back into shared `PluginContext._published_data`;
13. legacy context-owned data/event bus APIs are compatibility-only and are not extended as primary runtime architecture;
14. representative compiler, validator, and generator paths execute through snapshot/envelope/commit flow without ambient shared-state mutation.

## Summary

The project standardizes plugin runtime on actor-style dataflow ownership.

**Architectural rule:**

- workers compute and propose outputs;
- only the main interpreter validates and commits them.

This replaces shared mutable context semantics with explicit snapshot/envelope ownership aligned with Python 3.14 subinterpreters.
