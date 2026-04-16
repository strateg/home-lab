# ADR 0099: Refactor Test Architecture for Snapshot/Envelope Pipeline Runtime

- Status: Proposed
- Date: 2026-04-15
- Revised: 2026-04-17
- Depends on: ADR 0097
- Scope note: This ADR is the canonical follow-up for test architecture migration under the actor-style plugin runtime model.

## Context

The plugin runtime is moving from shared mutable `PluginContext` semantics to an actor-style dataflow model based on:

- immutable input snapshots;
- local worker execution;
- execution envelopes;
- scheduler-owned pipeline state and commit.

The existing test suite was designed for the previous runtime model and still contains tests tied to legacy internals, including:

- manual `_set_execution_context()` / `_clear_execution_context()` handling;
- direct `ctx.publish()` assumptions against shared runtime state;
- direct `ctx.get_published_data()` inspection as if context owns pipeline bus state;
- stage-local cleanup via mutable context-owned stores;
- execution assumptions where plugin runtime and pipeline state are treated as one object.

As a result, significant parts of the current tests validate obsolete mechanics rather than the new runtime architecture.

## Decision

The test architecture is refactored to align with ADR 0097 runtime contracts.

Primary testing layers:

1. plugin unit tests;
2. worker runner tests;
3. pipeline state tests;
4. scheduler/runtime integration tests;
5. serial vs subinterpreter parity tests.

Legacy context-internal tests may remain temporarily, but are transitional and not the source of truth for runtime behavior.

## Test Architecture

### 1) Plugin unit tests

Purpose: validate plugin business logic against stable author-facing contracts.

Characteristics:

- construct `PluginInputSnapshot`;
- execute plugin via `run_plugin_once()` (or equivalent local runner);
- assert on returned `PluginExecutionEnvelope`;
- avoid direct inspection of internal pipeline stores.

Verifies:

- diagnostics;
- declared published outputs;
- local emitted events;
- deterministic behavior for fixed inputs.

### 2) Worker runner tests

Purpose: validate isolated execution mechanics.

Characteristics:

- cover serial worker path;
- cover subinterpreter worker path;
- verify snapshot serialization/deserialization;
- verify envelope serialization/deserialization.

Verifies:

- worker startup correctness;
- timeout behavior;
- crash isolation;
- envelope production.

### 3) Pipeline state tests

Purpose: validate main-interpreter-owned state and commit semantics.

Characteristics:

- operate directly on `PipelineState`;
- feed committed values and envelopes into commit paths;
- verify consume resolution and stage-local invalidation.

Verifies:

- commit rules;
- schema validation for produced payloads;
- stage-local visibility rules;
- no partial commit on invalid envelope.

### 4) Scheduler/runtime integration tests

Purpose: validate orchestration across stages/phases/dependencies/execution modes.

Characteristics:

- load manifests;
- resolve dependencies;
- build snapshots;
- dispatch plugins;
- commit envelopes;
- inspect committed pipeline state and final results.

Verifies:

- stage/phase ordering;
- dependency-respecting wavefront execution;
- execution mode routing;
- fail-fast and finalize semantics;
- trace and metrics behavior.

### 5) Serial vs subinterpreter parity tests

Purpose: guarantee runtime equivalence for supported plugins.

Characteristics:

- run same manifest/pipeline in serial and subinterpreter modes;
- compare committed outputs and result surfaces.

Verifies:

- same committed published values;
- same statuses;
- same diagnostics (excluding allowed timing/runtime metadata deltas).

## Required Test Invariants

- **Determinism invariant**: supported plugins produce equivalent committed results in serial and subinterpreter execution.
- **Isolation invariant**: worker outbox data is not pipeline-visible unless commit succeeds.
- **Ownership invariant**: tests do not treat worker-local context as owner of pipeline-visible state.
- **Visibility invariant**: `stage_local` visibility and cleanup are enforced by pipeline state, not worker-side context mutation.
- **Contract invariant**: consumed payloads are resolved before dispatch and validated against manifest/runtime contract rules.

## Migration Strategy

### Step 1: Introduce canonical test helpers

Add helpers for:

- building `PluginInputSnapshot`;
- executing `run_plugin_once()`;
- constructing `PluginExecutionEnvelope`;
- asserting committed `PipelineState`.

### Step 2: Reclassify existing tests

Split existing tests into:

- keep as integration tests when they validate real orchestration behavior;
- rewrite when they depend on private mutable-context internals;
- delete when they only verify obsolete mechanics.

### Step 3: Add parity suite early

Introduce parity coverage before broad plugin migration to catch runtime regressions early.

### Step 4: Demote legacy context tests

Mark tests depending on `_set_execution_context()` and direct context-owned bus inspection as transitional compatibility coverage.

### Step 5: Remove obsolete tests

Delete tests that validate removed ownership semantics once runtime migration stabilizes.

## Test Directory Guidance

Recommended layout:

```text
tests/
  plugins/
    unit/
  runtime/
    worker_runner/
    pipeline_state/
    scheduler/
    parity/
  integration/
  compatibility_legacy/
```

Intent:

- `plugins/unit/` — plugin logic only;
- `runtime/worker_runner/` — isolated execution;
- `runtime/pipeline_state/` — commit/visibility/invalidation;
- `runtime/scheduler/` — orchestration and stage flow;
- `runtime/parity/` — serial vs subinterpreter equivalence;
- `compatibility_legacy/` — temporary compatibility shim tests only.

## Consequences

### Positive

- tests align with architecture rather than legacy internals;
- runtime ownership boundaries become easier to preserve;
- migration to snapshot/envelope model becomes safer;
- subinterpreter parity becomes first-class;
- failures become easier to localize by layer.

### Negative

- substantial test rewrite is required;
- test helpers and fixtures must be rebuilt;
- short-term duplication exists while compatibility coverage remains.

## Alternatives Considered

### A1. Keep existing tests and adapt implementation to satisfy them

Rejected. Preserves outdated ownership semantics and blocks architecture cleanup.

### A2. Rewrite all tests at once

Not selected. Too disruptive; incremental migration with compatibility coverage is safer.

### A3. Keep only end-to-end tests

Rejected. E2E-only coverage is insufficient for worker isolation, commit semantics, and parity invariants.

## Acceptance Criteria

This ADR is implemented when all are true:

1. runtime tests exist for snapshot, envelope, pipeline state, and scheduler layers;
2. plugin unit tests assert on envelopes, not context-owned global state;
3. parity tests exist for supported plugins in serial and subinterpreter execution;
4. worker failure isolation is explicitly tested;
5. stage-local visibility and invalidation are explicitly tested in pipeline-state tests;
6. legacy context-internal tests are moved to transitional compatibility coverage or removed;
7. new primary runtime validation no longer requires direct `_set_execution_context()` usage.

## Summary

Core testing rule:

- plugin tests validate local computation and proposed outputs;
- runtime tests validate scheduling, commit, and visibility;
- parity tests validate equivalence across execution modes.

This keeps test coverage aligned with the actor-style runtime defined by ADR 0097.
