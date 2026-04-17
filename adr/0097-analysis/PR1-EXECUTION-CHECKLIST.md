# ADR 0097 PR1 Execution Checklist — Contracts and Primary Envelope Path Skeleton

Date: 2026-04-17
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

- [ ] Confirm working tree excludes unrelated local artifacts from this PR (`.coverage`, `.state/**`, coverage XML files).
- [ ] Re-read current ADR guardrails:
  - `adr/0097-subinterpreter-parallel-plugin-execution.md`
  - `adr/0099-refactor-test-architecture-for-snapshot-envelope-pipeline-runtime.md`
- [ ] Keep `generated/` untouched.
- [ ] Plan tests before code changes.

---

## B. `plugin_base.py` — new contracts

### B1. Add new dataclasses / value objects

- [ ] Add `SubscriptionValue`
- [ ] Add `PublishedMessage`
- [ ] Add `EmittedEvent`
- [ ] Add `PluginInputSnapshot`
- [ ] Add `PluginExecutionEnvelope`

### B2. Define minimum fields

#### `SubscriptionValue`
- [ ] `from_plugin: str`
- [ ] `key: str`
- [ ] `value: Any`
- [ ] `scope: str | None`
- [ ] stage/phase metadata only if actually required for validation/debugging

#### `PublishedMessage`
- [ ] `plugin_id: str`
- [ ] `key: str`
- [ ] `value: Any`
- [ ] `scope: str` (`pipeline_shared` / `stage_local`)
- [ ] `stage: Stage`
- [ ] `phase: Phase`

#### `EmittedEvent`
- [ ] `plugin_id: str`
- [ ] `topic: str`
- [ ] `payload: Any`
- [ ] `stage: Stage`
- [ ] `phase: Phase`

#### `PluginInputSnapshot`
- [ ] plugin-visible input payloads only
- [ ] resolved subscriptions map / list
- [ ] stage
- [ ] phase
- [ ] plugin config
- [ ] required execution metadata
- [ ] optional snapshot views for topology/model slices if needed now

#### `PluginExecutionEnvelope`
- [ ] `result: PluginResult`
- [ ] `published_messages: list[PublishedMessage]`
- [ ] `emitted_events: list[EmittedEvent]`
- [ ] optional execution metadata

### B3. Keep `PluginResult` semantic-only
- [ ] Do not overload `PluginResult` with transport responsibilities.
- [ ] Keep envelope as the worker transport object.

---

## C. `PluginContext` — local facade mode

### C1. Add local-only state for new path
- [ ] add snapshot reference (`_snapshot` or equivalent)
- [ ] add local publish outbox
- [ ] add local event outbox

### C2. Implement facade semantics for new path
- [ ] `subscribe(plugin_id, key)` reads from snapshot-resolved subscriptions only
- [ ] `publish(key, value)` appends `PublishedMessage`
- [ ] `emit(topic, payload)` appends `EmittedEvent`

### C3. Fence legacy semantics
- [ ] Do not remove legacy APIs yet
- [ ] Do not extend `_published_data` semantics for the new path
- [ ] Do not extend worker-side event bus for the new path
- [ ] Add comments/docstrings marking legacy bus/event APIs as compatibility-only

### C4. Avoid accidental ambiguity
- [ ] New path must not require `get_published_data()`
- [ ] New path must not require `_set_execution_context()`

---

## D. `plugin_runner.py` — new file

### D1. Create runner entrypoint
- [ ] Add `run_plugin_once(...) -> PluginExecutionEnvelope`

### D2. Choose concrete signature
- [ ] Prefer explicit args, e.g.:
  - `snapshot: PluginInputSnapshot`
  - `plugin: PluginBase`
  - `plugin_spec: PluginSpec`
- [ ] Keep signature easy to call from both serial and isolated paths

### D3. Runner responsibilities
- [ ] build local-facade `PluginContext` from snapshot
- [ ] execute correct phase hook / phase-aware method
- [ ] collect `PluginResult`
- [ ] collect publish outbox
- [ ] collect event outbox
- [ ] return `PluginExecutionEnvelope`

### D4. Error behavior
- [ ] runner should convert plugin crash into failed envelope or raise a clearly bounded error for caller wrapping
- [ ] do not partially commit anything in runner

---

## E. `pipeline_runtime.py` — new file

### E1. Create `PipelineState`
- [ ] committed published data storage
- [ ] published metadata storage
- [ ] stage-local visibility helpers
- [ ] stage-local invalidation helper

### E2. Add `commit_envelope()`
- [ ] validate envelope shape
- [ ] validate produced keys against plugin manifest contract
- [ ] validate payload schemas where current runtime already supports this
- [ ] commit published messages atomically
- [ ] reject partial commit on invalid envelope

### E3. Add read helpers for later scheduler use
- [ ] helper to resolve committed payload by `(plugin_id, key)`
- [ ] helper to build subscription values for snapshot building

---

## F. `plugin_registry.py` — minimal PR1 bridge only

### F1. Avoid full scheduler rewrite in PR1
- [ ] no full `_execute_phase_parallel()` replacement yet
- [ ] no broad plugin cutovers yet

### F2. Add minimal integration seam
- [ ] add snapshot-builder helper for a single plugin execution path
- [ ] add serial bridge path using `run_plugin_once()` for targeted tests / non-parallel path if feasible
- [ ] keep old path functional for compatibility during PR1

### F3. Explicit non-goals for PR1
- [ ] do not keep designing around `SerializablePluginContext`
- [ ] do not introduce new merge-back behavior
- [ ] do not deepen `subinterpreter_compatible` logic yet

---

## G. Test files to add in PR1

### G1. Dataclass / contract tests
- [ ] `tests/plugin_api/test_snapshot_envelope_dataclasses.py`
  - [ ] construction
  - [ ] defaults
  - [ ] basic serialization-friendly structure

### G2. Worker runner tests
- [ ] `tests/runtime/worker_runner/test_run_plugin_once.py`
  - [ ] snapshot in -> envelope out
  - [ ] publish goes to outbox
  - [ ] emit goes to event outbox
  - [ ] crash path handled correctly

### G3. Pipeline state tests
- [ ] `tests/runtime/pipeline_state/test_commit_envelope.py`
  - [ ] valid envelope commits messages
  - [ ] invalid envelope commits nothing
  - [ ] undeclared produce rejected
- [ ] `tests/runtime/pipeline_state/test_stage_local_visibility.py`
  - [ ] stage_local visible in allowed stage
  - [ ] stage_local hidden across stage boundary
  - [ ] invalidation removes stage-local data

### G4. Transitional compatibility stance
- [ ] Do not mass-rewrite legacy tests in PR1
- [ ] Only adapt legacy tests if PR1 breaks them mechanically and adaptation is minimal

---

## H. Validation commands for PR1

### Minimum before commit
- [ ] targeted pytest for new files
- [ ] targeted pytest for touched plugin API/runtime tests
- [ ] `task validate:adr-consistency`

### Strongly recommended
- [ ] targeted plugin contract tests if any manifest/runtime contract helpers are touched
- [ ] `task test:plugin-contract` if PR1 crosses contract-validation boundaries

---

## I. PR1 review checklist

- [ ] New primary path is snapshot/envelope-based
- [ ] No primary-path dependency on shared `_published_data`
- [ ] No primary-path dependency on `get_published_data()`
- [ ] No primary-path dependency on `_set_execution_context()`
- [ ] `PipelineState` is the only place where pipeline-visible publication begins to become authoritative
- [ ] Legacy APIs remain compatibility-only, not expanded
- [ ] New tests exercise envelope model directly

---

## J. Definition of done

PR1 is done when:

- [ ] runtime contracts exist
- [ ] local-facade context exists for new path
- [ ] `run_plugin_once()` returns `PluginExecutionEnvelope`
- [ ] `PipelineState.commit_envelope()` exists and is tested
- [ ] new tests pass
- [ ] ADR consistency still passes
- [ ] project is ready for PR2 scheduler cutover
