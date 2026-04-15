# ADR 0097 — Wave 4 Evidence

**Date**: 2026-04-15
**Status**: Complete
**Wave**: Lock Removal & Simplification

---

## Summary

Wave 4 implemented lock optimization for subinterpreter execution mode:

1. Added `NoOpLock` class to eliminate lock overhead in isolated contexts
2. Added `_subinterpreter_mode` flag to `PluginContext`
3. Updated `SerializablePluginContext.to_plugin_context()` to use `NoOpLock`
4. Added comprehensive tests for the new functionality

---

## Changes Made

### plugin_base.py

**Added NoOpLock class:**

```python
class NoOpLock:
    """No-operation lock for single-threaded subinterpreter contexts (ADR 0097 Wave 4)."""

    def acquire(self, blocking: bool = True, timeout: float = -1) -> bool:
        return True

    def release(self) -> None:
        pass

    def __enter__(self) -> bool:
        return True

    def __exit__(self, *args: Any) -> None:
        pass
```

**Added _subinterpreter_mode flag to PluginContext:**

```python
@dataclass
class PluginContext:
    ...
    _published_data_lock: Union[Lock, NoOpLock] = field(default_factory=Lock, repr=False)
    _subinterpreter_mode: bool = field(default=False, repr=False)
```

**Updated to_plugin_context() to use NoOpLock:**

```python
def to_plugin_context(self) -> PluginContext:
    ctx = PluginContext(
        ...
        _subinterpreter_mode=True,
        _published_data_lock=NoOpLock(),
    )
    return ctx
```

### test_adr0097_parity.py

Added new test class `TestNoOpLockWave4` with 5 tests:

| Test | Description |
|------|-------------|
| `test_nooplock_context_manager` | Verify NoOpLock works as context manager |
| `test_nooplock_acquire_release` | Verify acquire/release methods |
| `test_regular_context_uses_real_lock` | Verify regular PluginContext uses Lock |
| `test_deserialized_context_uses_nooplock` | Verify deserialized context uses NoOpLock |
| `test_deserialized_context_publish_works` | Verify publish() works with NoOpLock |

---

## Test Results

### Parity Tests

```
tests/test_adr0097_parity.py::TestSerializablePluginContext::test_roundtrip_serialization PASSED
tests/test_adr0097_parity.py::TestSerializablePluginContext::test_serialization_with_minimal_context PASSED
tests/test_adr0097_parity.py::TestExecutorSelection::test_executor_selection_subinterpreters_disabled PASSED
tests/test_adr0097_parity.py::TestExecutorSelection::test_executor_selection_all_compatible SKIPPED (Python 3.14)
tests/test_adr0097_parity.py::TestExecutorSelection::test_executor_selection_mixed_compatibility PASSED
tests/test_adr0097_parity.py::TestPluginManifestSchema::test_manifest_parsing_compatible_true PASSED
tests/test_adr0097_parity.py::TestPluginManifestSchema::test_manifest_parsing_default_value PASSED
tests/test_adr0097_parity.py::TestNoOpLockWave4::test_nooplock_context_manager PASSED
tests/test_adr0097_parity.py::TestNoOpLockWave4::test_nooplock_acquire_release PASSED
tests/test_adr0097_parity.py::TestNoOpLockWave4::test_regular_context_uses_real_lock PASSED
tests/test_adr0097_parity.py::TestNoOpLockWave4::test_deserialized_context_uses_nooplock PASSED
tests/test_adr0097_parity.py::TestNoOpLockWave4::test_deserialized_context_publish_works PASSED

Result: 11 passed, 1 skipped
```

### Validation Pipeline

```
v5 layer contract: PASS
v5 scaffold validation: PASS
Capability contract check: OK (errors=0 warnings=0)
Compile summary: total=91 errors=0 warnings=0 infos=91
[adr0088-governance] PASS
```

---

## Exit Criteria Verification

| Criterion | Status |
|-----------|--------|
| `NoOpLock` class implemented | PASS |
| `_subinterpreter_mode` flag added to PluginContext | PASS |
| `to_plugin_context()` uses NoOpLock | PASS |
| Parity tests pass | PASS (11/11, 1 skipped) |
| No regressions in validation pipeline | PASS |
| Documentation updated | PASS |

---

## Performance Impact

**In subinterpreter mode:**
- Eliminates `threading.Lock` object creation overhead
- Each `PluginContext` in subinterpreter uses lightweight `NoOpLock`
- No synchronization overhead (NoOpLock methods are no-ops)

**In ThreadPoolExecutor mode:**
- Unchanged: regular `threading.Lock` is used
- Full thread-safety preserved for parallel plugin execution

---

## Architectural Notes

### Why NoOpLock is Safe in Subinterpreter Mode

1. Each subinterpreter has isolated memory (PEP 684)
2. `SerializablePluginContext.to_plugin_context()` creates a NEW `PluginContext`
3. That context's `_published_data` is not shared with other interpreters
4. Only ONE thread accesses the context within each subinterpreter
5. No concurrent access = no need for synchronization

### ThreadPoolExecutor Fallback

The `threading.Lock` is preserved for:
- Python < 3.14 (no InterpreterPoolExecutor)
- Plugins marked `subinterpreter_compatible: false`
- Mixed compatibility wavefronts
- Debugging/development mode

---

## Next Steps

Proceed to **Wave 5: Default Promotion**:

1. Make `--use-subinterpreters` default on Python 3.14+
2. Add `--no-subinterpreters` for fallback
3. Deprecate ThreadPoolExecutor for new plugins
4. Performance benchmarks published

**Gate**: Subinterpreters are production default.

---

**Document Owner**: Infrastructure Team
**Last Updated**: 2026-04-15
