# ADR 0097 — Wave 4 Implementation Plan

**Date**: 2026-04-15
**Status**: Complete
**Wave**: Lock Removal & Simplification
**Depends on**: Wave 3 (Complete)

---

## Objectives

Wave 4 optimizes the lock architecture for subinterpreter execution:

1. Add `NoOpLock` class to avoid unnecessary lock overhead in subinterpreter mode
2. Mark `PluginContext` instances with `subinterpreter_mode` flag
3. Use `NoOpLock` when context is created via `SerializablePluginContext.to_plugin_context()`
4. Document the architectural simplification

**Goal**: Eliminate lock overhead in subinterpreter mode while preserving ThreadPoolExecutor safety.

---

## Current Architecture Analysis

### Lock Usage in PluginContext

The `_published_data_lock` is used in 9 methods:

| Method | Purpose |
|--------|---------|
| `publish()` | Write to `_published_data` |
| `subscribe()` | Read from `_published_data` |
| `get_published_keys()` | List keys for a plugin |
| `get_published_data()` | Get full published data map |
| `_get_publish_event_count()` | Count publish events |
| `_get_subscribe_event_count()` | Count subscribe events |
| `_get_publish_events_since()` | Get events since index |
| `_get_subscribe_events_since()` | Get events since index |
| `invalidate_stage_local_data()` | Remove stage-local data |

### Why Locks Are Unnecessary in Subinterpreter Mode

1. Each subinterpreter gets a NEW `PluginContext` via `to_plugin_context()`
2. That context has its own `_published_data` dict (not shared)
3. Only ONE thread accesses that context within the subinterpreter
4. No concurrent access = no need for locks

### ThreadPoolExecutor Mode

In thread mode, multiple plugins share the SAME `PluginContext`:
- Lock is REQUIRED for thread safety
- Must be preserved for fallback compatibility

---

## Implementation Tasks

### T1: Add NoOpLock Class

Add a lock-like class that does nothing but satisfies the context manager protocol.

```python
class NoOpLock:
    """No-operation lock for single-threaded subinterpreter contexts."""

    def acquire(self, blocking: bool = True, timeout: float = -1) -> bool:
        return True

    def release(self) -> None:
        pass

    def __enter__(self) -> bool:
        return True

    def __exit__(self, *args: Any) -> None:
        pass
```

### T2: Add subinterpreter_mode Flag to PluginContext

```python
@dataclass
class PluginContext:
    ...
    # Subinterpreter optimization (ADR 0097 Wave 4)
    _subinterpreter_mode: bool = field(default=False, repr=False)
    _published_data_lock: Lock | NoOpLock = field(default_factory=Lock, repr=False)
```

### T3: Update SerializablePluginContext.to_plugin_context()

```python
def to_plugin_context(self) -> PluginContext:
    ctx = PluginContext(
        ...
        _subinterpreter_mode=True,  # Mark as subinterpreter context
    )
    # Replace lock with NoOpLock
    ctx._published_data_lock = NoOpLock()
    return ctx
```

### T4: Update Documentation

1. Update ADR 0097 status
2. Document Wave 4 evidence

---

## Exit Criteria

| Criterion | Status |
|-----------|--------|
| `NoOpLock` class implemented | PASS |
| `_subinterpreter_mode` flag added to PluginContext | PASS |
| `to_plugin_context()` uses NoOpLock | PASS |
| Parity tests pass | PASS (11/11, 1 skipped) |
| No regressions in validation pipeline | PASS |
| Documentation updated | PASS |

---

## Risk Assessment

**Low Risk**: This is a performance optimization, not a behavioral change.

- In subinterpreter mode, locks were already non-contended
- The change eliminates unnecessary lock object creation overhead
- ThreadPoolExecutor fallback is unchanged

---

## Next Wave

After Wave 4 completion, proceed to **Wave 5: Default Promotion**:

1. Make `--use-subinterpreters` default on Python 3.14+
2. Add `--no-subinterpreters` for fallback
3. Deprecate ThreadPoolExecutor for new plugins
4. Performance benchmarks published

**Gate**: Subinterpreters are production default.

---

**Document Owner**: Infrastructure Team
**Last Updated**: 2026-04-15
