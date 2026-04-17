# ADR 0097 PR1 API Design Sketch

Date: 2026-04-17
Purpose: Freeze concrete runtime APIs and integration seams before starting code changes for PR1.

## Design goal

Introduce the envelope-model foundation with the smallest possible set of new APIs that:

- do not deepen legacy shared-context semantics;
- can coexist temporarily with compatibility code;
- are sufficient to support PR2 scheduler cutover.

---

## 1. New dataclasses in `plugin_base.py`

### `SubscriptionValue`

```python
@dataclass(frozen=True)
class SubscriptionValue:
    from_plugin: str
    key: str
    value: Any
    scope: str = "pipeline_shared"
    stage: Stage | None = None
    phase: Phase | None = None
```

### `PublishedMessage`

```python
@dataclass(frozen=True)
class PublishedMessage:
    plugin_id: str
    key: str
    value: Any
    scope: str
    stage: Stage
    phase: Phase
```

### `EmittedEvent`

```python
@dataclass(frozen=True)
class EmittedEvent:
    plugin_id: str
    topic: str
    payload: Any
    stage: Stage
    phase: Phase
```

### `PluginInputSnapshot`

```python
@dataclass(frozen=True)
class PluginInputSnapshot:
    plugin_id: str
    stage: Stage
    phase: Phase
    topology_path: str
    profile: str
    config: dict[str, Any] = field(default_factory=dict)
    model_lock: dict[str, Any] = field(default_factory=dict)
    raw_yaml: dict[str, Any] = field(default_factory=dict)
    instance_bindings: dict[str, Any] = field(default_factory=dict)
    compiled_json: dict[str, Any] = field(default_factory=dict)
    classes: dict[str, Any] = field(default_factory=dict)
    objects: dict[str, Any] = field(default_factory=dict)
    capability_catalog: dict[str, Any] = field(default_factory=dict)
    effective_capabilities: dict[str, list[str]] = field(default_factory=dict)
    effective_software: dict[str, dict[str, Any]] = field(default_factory=dict)
    output_dir: str = ""
    workspace_root: str = ""
    dist_root: str = ""
    assembly_manifest: dict[str, Any] = field(default_factory=dict)
    changed_input_scopes: list[str] | None = None
    signing_backend: str = ""
    release_tag: str = ""
    sbom_output_dir: str = ""
    error_catalog: dict[str, Any] = field(default_factory=dict)
    source_file: str = ""
    compiled_file: str = ""
    subscriptions: dict[tuple[str, str], SubscriptionValue] = field(default_factory=dict)
    allowed_dependencies: frozenset[str] = field(default_factory=frozenset)
    produced_key_scopes: dict[str, str] = field(default_factory=dict)
```

### `PluginExecutionEnvelope`

```python
@dataclass(frozen=True)
class PluginExecutionEnvelope:
    result: PluginResult
    published_messages: list[PublishedMessage] = field(default_factory=list)
    emitted_events: list[EmittedEvent] = field(default_factory=list)
    execution_metadata: dict[str, Any] | None = None
```

---

## 2. `PluginContext` PR1 semantics

PR1 keeps the public class name `PluginContext`, but introduces a snapshot-backed mode.

### New internal fields

```python
_snapshot: PluginInputSnapshot | None = field(default=None, repr=False)
_outbox: list[PublishedMessage] = field(default_factory=list, repr=False)
_event_outbox: list[EmittedEvent] = field(default_factory=list, repr=False)
```

### Construction helper

```python
@classmethod
 def from_snapshot(cls, snapshot: PluginInputSnapshot) -> "PluginContext": ...
```

### New-path behavior rules

- `publish()`:
  - if `_snapshot is not None`, append to `_outbox`
  - else use legacy compatibility behavior
- `subscribe()`:
  - if `_snapshot is not None`, resolve via `snapshot.subscriptions[(plugin_id, key)]`
  - else use legacy compatibility behavior
- `emit()`:
  - if `_snapshot is not None`, append to `_event_outbox`
  - else use legacy compatibility behavior

### Access helpers

```python
def drain_outbox(self) -> list[PublishedMessage]: ...
def drain_event_outbox(self) -> list[EmittedEvent]: ...
```

PR1 intent: the new execution path uses only snapshot-backed behavior; legacy paths remain untouched except for compatibility.

---

## 3. `plugin_runner.py` API

### Primary runner

```python
def run_plugin_once(
    *,
    snapshot: PluginInputSnapshot,
    plugin: PluginBase,
) -> PluginExecutionEnvelope:
    ...
```

### Responsibilities

1. Build `PluginContext.from_snapshot(snapshot)`
2. Execute plugin phase hook based on `snapshot.stage` / `snapshot.phase`
3. Collect:
   - `PluginResult`
   - `ctx.drain_outbox()`
   - `ctx.drain_event_outbox()`
4. Return envelope

### Error policy

If plugin raises unexpectedly:
- either wrap into failed `PluginResult` inside returned envelope, or
- raise to caller wrapper that converts it consistently

Preferred for PR1: return failed envelope from runner utility so tests stay simple.

---

## 4. `pipeline_runtime.py` API

### `PipelineState`

```python
@dataclass
class PipelineState:
    committed_data: dict[str, dict[str, Any]] = field(default_factory=dict)
    published_meta: dict[tuple[str, str], PublishedDataMeta] = field(default_factory=dict)
    emitted_events: list[EmittedEvent] = field(default_factory=list)
```

### Methods

```python
def commit_envelope(
    self,
    *,
    plugin_id: str,
    stage: Stage,
    phase: Phase,
    produces: list[dict[str, Any]],
    envelope: PluginExecutionEnvelope,
) -> None:
    ...
```

```python
def resolve_subscription(
    self,
    *,
    from_plugin: str,
    key: str,
    stage: Stage,
) -> SubscriptionValue:
    ...
```

```python
def invalidate_stage_local_data(self, stage: Stage) -> list[str]:
    ...
```

### PR1 validation scope inside `commit_envelope()`

- ensure every envelope published key is declared in `produces`
- infer scope from declared produce entry
- reject undeclared publish
- enforce stage-local visibility metadata
- append emitted events to event log
- commit atomically (validate first, then mutate)

---

## 5. `plugin_registry.py` PR1 integration seam

### Minimal helper to add

```python
def _build_input_snapshot(
    self,
    *,
    plugin_id: str,
    stage: Stage,
    phase: Phase,
    ctx: PluginContext,
    pipeline_state: PipelineState | None = None,
) -> PluginInputSnapshot:
    ...
```

### PR1 policy

- helper may still source data from current context for bootstrap convenience;
- but resulting object must be a `PluginInputSnapshot`;
- the new runner must consume the snapshot only.

### Optional targeted bridge

Add a non-primary helper such as:

```python
def execute_plugin_with_envelope_path(...): ...
```

Use only in PR1 tests or limited serial integration.

---

## 6. Test API targets for PR1

### `tests/plugin_api/test_snapshot_envelope_dataclasses.py`

Must cover:
- dataclass creation
- default values
- frozen/value-object expectations where relevant

### `tests/runtime/worker_runner/test_run_plugin_once.py`

Create tiny fake plugins to validate:
- publish -> outbox
- emit -> event outbox
- subscribe -> snapshot resolution
- crash -> failed result path

### `tests/runtime/pipeline_state/test_commit_envelope.py`

Must cover:
- declared produce commit
- undeclared produce rejection
- atomic no-partial-commit behavior

### `tests/runtime/pipeline_state/test_stage_local_visibility.py`

Must cover:
- stage-local data resolution in same stage
- cross-stage denial
- invalidation removal

---

## 7. Non-goals for PR1

- no full replacement of `_execute_phase_parallel()`
- no complete manifest schema cutover to `execution_mode`
- no removal of legacy event bus APIs yet
- no representative plugin behavior rewrites yet

---

## 8. Review focus for PR1

Reviewers should specifically check:

1. new path depends on snapshot, not on live shared registry;
2. envelope is the sole worker output contract;
3. `PipelineState` is the only new commit owner;
4. compatibility code is not accidentally expanded;
5. new tests validate the future architecture, not legacy internals.
