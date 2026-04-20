# ADR 0097 PR1 Execution Checklist — Contracts and Primary Envelope Path Skeleton

Date: 2026-04-17
Updated: 2026-04-20
Status: **COMPLETE**
Purpose: Concrete implementation checklist for the first code PR of the ADR 0097 envelope-model cutover.

## PR1 objective

Introduce the minimum runtime primitives required for the new primary execution path:

- `PluginInputSnapshot`
- `PluginExecutionEnvelope`
- `PipelineState.commit_envelope()`
- `run_plugin_once()`
- `PluginContext` local-facade semantics for the new path

PR1 does **not** complete full scheduler cutover and does **not** yet migrate representative plugins.

---

## A. Pre-change safety checks

- [x] Confirm working tree excludes unrelated local artifacts from this PR (`.coverage`, `.state/**`, coverage XML files).
- [x] Re-read current ADR guardrails:
  - `adr/0097-subinterpreter-parallel-plugin-execution.md`
  - `adr/0099-refactor-test-architecture-for-snapshot-envelope-pipeline-runtime.md`
- [x] Keep `generated/` untouched.
- [x] Plan tests before code changes.

---

## B. `plugin_base.py` — new contracts

### B1. Add new dataclasses / value objects

- [x] Add `SubscriptionValue` (lines 131-140)
- [x] Add `PublishedMessage` (lines 143-152)
- [x] Add `EmittedEvent` (lines 155-163)
- [x] Add `PluginInputSnapshot` (lines 371-402)
- [x] Add `PluginExecutionEnvelope` (lines 406-412)

### B2. Define minimum fields

#### `SubscriptionValue`
- [x] `from_plugin: str`
- [x] `key: str`
- [x] `value: Any`
- [x] `scope: str | None`
- [x] stage/phase metadata only if actually required for validation/debugging

#### `PublishedMessage`
- [x] `plugin_id: str`
- [x] `key: str`
- [x] `value: Any`
- [x] `scope: str` (`pipeline_shared` / `stage_local`)
- [x] `stage: Stage`
- [x] `phase: Phase`

#### `EmittedEvent`
- [x] `plugin_id: str`
- [x] `topic: str`
- [x] `payload: Any`
- [x] `stage: Stage`
- [x] `phase: Phase`

#### `PluginInputSnapshot`
- [x] plugin-visible input payloads only
- [x] resolved subscriptions map / list
- [x] stage
- [x] phase
- [x] plugin config
- [x] required execution metadata
- [x] optional snapshot views for topology/model slices if needed now

#### `PluginExecutionEnvelope`
- [x] `result: PluginResult`
- [x] `published_messages: list[PublishedMessage]`
- [x] `emitted_events: list[EmittedEvent]`
- [x] optional execution metadata

### B3. Keep `PluginResult` semantic-only
- [x] Do not overload `PluginResult` with transport responsibilities.
- [x] Keep envelope as the worker transport object.

---

## C. `PluginContext` — local facade mode

### C1. Add local-only state for new path
- [x] add snapshot reference (`_snapshot`) — line 539
- [x] add local publish outbox (`_outbox`) — line 540
- [x] add local event outbox (`_event_outbox`) — line 541

### C2. Implement facade semantics for new path
- [x] `subscribe(plugin_id, key)` reads from snapshot-resolved subscriptions only — lines 683-699
- [x] `publish(key, value)` appends `PublishedMessage` — lines 628-642
- [x] `emit(topic, payload)` appends `EmittedEvent` — lines 770-779

### C3. Fence legacy semantics
- [x] Do not remove legacy APIs yet
- [x] Do not extend `_published_data` semantics for the new path
- [x] Do not extend worker-side event bus for the new path
- [x] Add comments/docstrings marking legacy bus/event APIs as compatibility-only

### C4. Avoid accidental ambiguity
- [x] New path must not require `get_published_data()`
- [x] New path must not require `_set_execution_context()`

---

## D. `plugin_runner.py` — new file

### D1. Create runner entrypoint
- [x] Add `run_plugin_once(...) -> PluginExecutionEnvelope` — lines 25-73

### D2. Choose concrete signature
- [x] Prefer explicit args, e.g.:
  - `snapshot: PluginInputSnapshot`
  - `plugin: PluginBase`
  - `plugin_spec: PluginSpec`
- [x] Keep signature easy to call from both serial and isolated paths

### D3. Runner responsibilities
- [x] build local-facade `PluginContext` from snapshot — line 27
- [x] execute correct phase hook / phase-aware method — line 39
- [x] collect `PluginResult` — line 41
- [x] collect publish outbox — line 43
- [x] collect event outbox — line 44
- [x] return `PluginExecutionEnvelope` — lines 41-45

### D4. Error behavior
- [x] runner should convert plugin crash into failed envelope or raise a clearly bounded error for caller wrapping — lines 46-71
- [x] do not partially commit anything in runner

---

## E. `pipeline_runtime.py` — new file

### E1. Create `PipelineState`
- [x] committed published data storage (`committed_data`) — line 23
- [x] published metadata storage (`published_meta`) — line 24
- [x] stage-local visibility helpers — lines 80-100
- [x] stage-local invalidation helper (`invalidate_stage_local_data`) — lines 102-115

### E2. Add `commit_envelope()`
- [x] validate envelope shape — lines 46-54
- [x] validate produced keys against plugin manifest contract — lines 51-54
- [x] validate payload schemas where current runtime already supports this
- [x] commit published messages atomically — lines 71-78
- [x] reject partial commit on invalid envelope — raises `PluginDataExchangeError`

### E3. Add read helpers for later scheduler use
- [x] helper to resolve committed payload by `(plugin_id, key)` — `resolve_subscription()` lines 80-100
- [x] helper to build subscription values for snapshot building

---

## F. `plugin_registry.py` — minimal PR1 bridge only

### F1. Avoid full scheduler rewrite in PR1
- [x] no full `_execute_phase_parallel()` replacement yet
- [x] no broad plugin cutovers yet

### F2. Add minimal integration seam
- [x] add snapshot-builder helper for a single plugin execution path — `_build_input_snapshot()` lines 722-787
- [x] add serial bridge path using `run_plugin_once()` for targeted tests / non-parallel path if feasible
- [x] keep old path functional for compatibility during PR1

### F3. Explicit non-goals for PR1
- [x] do not keep designing around `SerializablePluginContext`
- [x] do not introduce new merge-back behavior
- [x] do not deepen `subinterpreter_compatible` logic yet

---

## G. Test files to add in PR1

### G1. Dataclass / contract tests
- [x] `tests/plugin_api/test_snapshot_envelope_dataclasses.py`
  - [x] construction
  - [x] defaults
  - [x] basic serialization-friendly structure

### G2. Worker runner tests
- [x] `tests/runtime/worker_runner/test_run_plugin_once.py`
  - [x] snapshot in -> envelope out
  - [x] publish goes to outbox
  - [x] emit goes to event outbox
  - [x] crash path handled correctly

### G3. Pipeline state tests
- [x] `tests/runtime/pipeline_state/test_commit_envelope.py`
  - [x] valid envelope commits messages
  - [x] invalid envelope commits nothing
  - [x] undeclared produce rejected
- [x] `tests/runtime/pipeline_state/test_stage_local_visibility.py`
  - [x] stage_local visible in allowed stage
  - [x] stage_local hidden across stage boundary
  - [x] invalidation removes stage-local data

### G4. Transitional compatibility stance
- [x] Do not mass-rewrite legacy tests in PR1
- [x] Only adapt legacy tests if PR1 breaks them mechanically and adaptation is minimal

---

## H. Validation commands for PR1

### Minimum before commit
- [x] targeted pytest for new files
- [x] targeted pytest for touched plugin API/runtime tests
- [x] `task validate:adr-consistency`

### Strongly recommended
- [x] targeted plugin contract tests if any manifest/runtime contract helpers are touched
- [x] `task test:plugin-contract` if PR1 crosses contract-validation boundaries

---

## I. PR1 review checklist

- [x] New primary path is snapshot/envelope-based
- [x] No primary-path dependency on shared `_published_data`
- [x] No primary-path dependency on `get_published_data()`
- [x] No primary-path dependency on `_set_execution_context()`
- [x] `PipelineState` is the only place where pipeline-visible publication begins to become authoritative
- [x] Legacy APIs remain compatibility-only, not expanded
- [x] New tests exercise envelope model directly

---

## J. Definition of done

PR1 is done when:

- [x] runtime contracts exist
- [x] local-facade context exists for new path
- [x] `run_plugin_once()` returns `PluginExecutionEnvelope`
- [x] `PipelineState.commit_envelope()` exists and is tested
- [x] new tests pass
- [x] ADR consistency still passes
- [x] project is ready for PR2 scheduler cutover

---

## Implementation Evidence

| Component | File | Lines | Status |
|-----------|------|-------|--------|
| `SubscriptionValue` | `plugin_base.py` | 131-140 | DONE |
| `PublishedMessage` | `plugin_base.py` | 143-152 | DONE |
| `EmittedEvent` | `plugin_base.py` | 155-163 | DONE |
| `PluginInputSnapshot` | `plugin_base.py` | 371-402 | DONE |
| `PluginExecutionEnvelope` | `plugin_base.py` | 406-412 | DONE |
| `PluginContext.from_snapshot()` | `plugin_base.py` | 563-591 | DONE |
| `PluginContext._snapshot` | `plugin_base.py` | 539 | DONE |
| `PluginContext._outbox` | `plugin_base.py` | 540 | DONE |
| `PluginContext._event_outbox` | `plugin_base.py` | 541 | DONE |
| `PluginContext.drain_outbox()` | `plugin_base.py` | 963-967 | DONE |
| `PluginContext.drain_event_outbox()` | `plugin_base.py` | 969-973 | DONE |
| `run_plugin_once()` | `plugin_runner.py` | 25-73 | DONE |
| `PipelineState` | `pipeline_runtime.py` | 19-115 | DONE |
| `PipelineState.commit_envelope()` | `pipeline_runtime.py` | 27-78 | DONE |
| `PipelineState.resolve_subscription()` | `pipeline_runtime.py` | 80-100 | DONE |
| `PipelineState.invalidate_stage_local_data()` | `pipeline_runtime.py` | 102-115 | DONE |
| `_build_input_snapshot()` | `plugin_registry.py` | 722-787 | DONE |

### Test Coverage

| Test File | Location | Status |
|-----------|----------|--------|
| `test_snapshot_envelope_dataclasses.py` | `tests/plugin_api/` | DONE |
| `test_run_plugin_once.py` | `tests/runtime/worker_runner/` | DONE |
| `test_commit_envelope.py` | `tests/runtime/pipeline_state/` | DONE |
| `test_stage_local_visibility.py` | `tests/runtime/pipeline_state/` | DONE |

---

**PR1 Status: COMPLETE** — Ready to proceed with PR2 scheduler cutover.
