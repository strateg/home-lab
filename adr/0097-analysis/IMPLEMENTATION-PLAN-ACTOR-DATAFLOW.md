# ADR 0097 Implementation Plan — Actor-Style Dataflow Runtime

Status: Active plan (post-ADR alignment)
Date: 2026-04-17

## Baseline already completed

1. ADR 0097 updated to actor-style ownership model (`snapshot -> execute -> envelope -> validate -> commit`).
2. ADR 0099 added as canonical test-architecture follow-up.
3. ADR register consistency debt (0098 mismatch) resolved.
4. `task validate:adr-consistency` passes.

## Non-negotiable architecture rule

- workers compute and propose (`PluginExecutionEnvelope`);
- only main interpreter validates and commits into pipeline-visible state (`PipelineState`).

## Practical rollout plan (execution waves)

### Wave 1 — Introduce compatible contracts and new execution path

Scope:

- introduce runtime contracts in `topology-tools/kernel/plugin_base.py`:
  - `PluginInputSnapshot`
  - `SubscriptionValue`
  - `PublishedMessage`
  - `EmittedEvent`
  - `PluginExecutionEnvelope`
- implement `PluginContext(snapshot)` as local facade (`subscribe/publish/emit` local-only semantics);
- add `run_plugin_once()` returning envelope;
- introduce `PipelineState.commit_envelope()` in main interpreter path;
- keep legacy context mechanics as transitional compatibility, but **new execution path must not depend on shared context bus**.

Validation gate:

- contract tests for snapshot/envelope;
- unit tests for `run_plugin_once()`;
- pipeline-state commit tests;
- initial compatibility tests still passing.

### Wave 2 — Runtime cutover to envelope commit flow

Scope:

- `_execute_plugin_isolated()` returns envelope (not `(result, published_data)` style tuples);
- `_execute_phase_parallel()` stops merging `ctx._published_data` as runtime authority;
- consumes are resolved before dispatch;
- commit is performed only in main interpreter (`PipelineState`).

Validation gate:

- scheduler integration tests;
- worker failure isolation tests (`plugin crash -> nothing committed`);
- stage-local visibility + cleanup tests.

### Wave 3 — Migrate key plugins (thin-worker style)

Priority targets:

1. `module_loader`
2. `instance_rows`
3. `effective_model`
4. one representative validator
5. one representative generator

Plugin migration rules:

- treat plugin as transaction over snapshot;
- no ambient context mutation (`ctx.classes/objects/compiled_json`);
- no worker-side event bus polling;
- outputs via envelope/outboxes only.

Specific targets:

- `EffectiveModelCompiler`: publish candidate model; authoritative compiled model assignment only at main-interpreter commit step.
- `InstanceRowsCompiler`: split at least into:
  - annotation/secret resolution,
  - row normalization,
  - semantic/shape validation.

Validation gate:

- plugin unit tests on envelope outputs;
- serial vs subinterpreter parity on committed outputs/statuses/diagnostics;
- no regressions on manifest consumes/produces contracts.

## Next contract evolution (after Wave 3 stability)

1. Promote manifest `execution_mode` (`subinterpreter | main_interpreter | thread_legacy`) as routing contract.
2. Keep backward-compat bridge for `subinterpreter_compatible` only during migration window.
3. Add optional `input_view` where snapshot minimization materially reduces payload/serialization cost.

## Test policy during migration

Primary truth layer (new architecture):

- `tests/plugins/unit/`
- `tests/runtime/worker_runner/`
- `tests/runtime/pipeline_state/`
- `tests/runtime/scheduler/`
- `tests/runtime/parity/`

Transitional layer:

- legacy tests tied to context internals remain temporarily in compatibility coverage and must be explicitly tagged as transitional.

## Exit criteria for this plan

Plan is considered complete when:

1. worker execution path is snapshot/envelope-native;
2. pipeline-visible state is committed only in main interpreter;
3. key plugins are migrated off shared-mutation behavior;
4. parity/failure-isolation/stage-local invariants are enforced in runtime tests;
5. legacy context-internal tests are no longer primary validation for runtime behavior.
