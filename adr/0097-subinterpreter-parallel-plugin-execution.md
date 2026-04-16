# ADR 0097: Actor-Style Dataflow Execution for Plugins on Python 3.14 Subinterpreters

- Status: Proposed
- Date: 2026-04-15
- Revised: 2026-04-17
- Depends on: ADR 0063, ADR 0080, ADR 0086, ADR 0098
- Follow-up: ADR 0099 (runtime + test architecture migration for snapshot/envelope/pipeline-state model)

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

Introduce:

- `PluginInputSnapshot`
- `SubscriptionValue`
- `PublishedMessage`
- `EmittedEvent`
- `PluginExecutionEnvelope`

### Phase 2: Local context facade

Refactor `PluginContext` to snapshot + local outboxes.

- `publish()` no longer commits.
- `subscribe()` no longer reads pipeline-global mutable state.

### Phase 3: Pipeline state ownership

Introduce scheduler-owned `PipelineState` responsible for:

- committed published data;
- consume resolution;
- schema validation;
- stage-local invalidation;
- envelope commit.

### Phase 4: Runner split

Separate:

- registry/manifest loading;
- worker plugin runner;
- pipeline runtime and state commit.

### Phase 5: Plugin migration

Migrate core plugins to snapshot/envelope execution, prioritizing plugins that currently mix publication with context mutation.

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
9. worker failure does not leak partial published state.

## Summary

The project standardizes plugin runtime on actor-style dataflow ownership.

**Architectural rule:**

- workers compute and propose outputs;
- only the main interpreter validates and commits them.

This replaces shared mutable context semantics with explicit snapshot/envelope ownership aligned with Python 3.14 subinterpreters.
