# ADR 0097 — Wave 1 Implementation Plan

**Date**: 2026-04-14
**Status**: Planning
**Wave**: Infrastructure (Conditional Executor)
**Depends on**: ADR 0098 (Python 3.14) ✅ Complete

---

## Objectives

Wave 1 establishes the foundational infrastructure for subinterpreter-based parallel plugin execution:

1. Add conditional `InterpreterPoolExecutor` import (Python 3.14+)
2. Implement `SerializablePluginContext` protocol for cross-interpreter data transfer
3. Add `--use-subinterpreters` CLI flag (opt-in mode)
4. Extend plugin manifest with `subinterpreter_compatible` field
5. Create parity test suite (ThreadPool vs InterpreterPool)

**Goal**: Dual-executor architecture with feature parity validation.

---

## Success Criteria

| Criterion | Measurement |
|-----------|-------------|
| Conditional import works | Python 3.14: imports `InterpreterPoolExecutor`, Python <3.14: fallback to `ThreadPoolExecutor` |
| Context serialization | `SerializablePluginContext` serializes/deserializes without data loss |
| CLI flag functional | `--use-subinterpreters` enables subinterpreter mode on Python 3.14+ |
| Manifest field recognized | `subinterpreter_compatible: true` plugins execute in InterpreterPool |
| Parity tests pass | Both executors produce identical plugin results and diagnostics |
| No regressions | All existing tests pass with both executors |

---

## Implementation Tasks

### T1: Conditional Executor Import

**File**: `topology-tools/kernel/plugin_registry.py`

**Changes:**

```python
# Line 16: Add conditional import
import sys
import concurrent.futures
if sys.version_info >= (3, 14):
    try:
        from concurrent.futures import InterpreterPoolExecutor
        HAS_INTERPRETER_POOL = True
    except ImportError:
        HAS_INTERPRETER_POOL = False
else:
    HAS_INTERPRETER_POOL = False
```

**Acceptance:**
- ✅ Python 3.14: `HAS_INTERPRETER_POOL == True`
- ✅ Python 3.13: `HAS_INTERPRETER_POOL == False`
- ✅ No import errors on any Python version

---

### T2: SerializablePluginContext Protocol

**File**: `topology-tools/kernel/plugin_base.py` (new dataclass)

**Changes:**

```python
@dataclass
class SerializablePluginContext:
    """Minimal context for cross-interpreter plugin execution (ADR 0097).

    Serialization boundary:
    - Input: compiled_json (bytes), plugin_config (bytes), paths (str)
    - Output: PluginResult with diagnostics and published data
    - NOT serialized: locks, file handles, mutable state (not needed in isolated interpreter)
    """
    topology_path: str
    profile: str
    compiled_json_bytes: bytes  # JSON-serialized compiled_json
    plugin_config_bytes: bytes  # JSON-serialized plugin-specific config
    output_dir: str
    project_root: str
    changed_input_scopes: list[str] | None
    model_lock: dict[str, Any] | None
    capability_catalog: dict[str, Any] | None

    @classmethod
    def from_plugin_context(cls, ctx: PluginContext) -> SerializablePluginContext:
        """Serialize PluginContext for cross-interpreter transfer."""
        import json
        return cls(
            topology_path=ctx.topology_path,
            profile=ctx.profile,
            compiled_json_bytes=json.dumps(ctx.compiled_json).encode('utf-8'),
            plugin_config_bytes=json.dumps(ctx.config).encode('utf-8'),
            output_dir=ctx.output_dir,
            project_root=ctx.project_root,
            changed_input_scopes=ctx.changed_input_scopes,
            model_lock=ctx.model_lock,
            capability_catalog=ctx.capability_catalog,
        )

    def to_plugin_context(self) -> PluginContext:
        """Deserialize to PluginContext in target interpreter."""
        import json
        return PluginContext(
            topology_path=self.topology_path,
            profile=self.profile,
            compiled_json=json.loads(self.compiled_json_bytes.decode('utf-8')),
            config=json.loads(self.plugin_config_bytes.decode('utf-8')),
            output_dir=self.output_dir,
            project_root=self.project_root,
            changed_input_scopes=self.changed_input_scopes,
            model_lock=self.model_lock,
            capability_catalog=self.capability_catalog,
        )
```

**Acceptance:**
- ✅ Round-trip serialization preserves all data
- ✅ No pickle dependency (uses JSON only)
- ✅ Unit tests pass

---

### T3: Executor Selection Method

**File**: `topology-tools/kernel/plugin_registry.py`

**Changes:**

```python
class PluginRegistry:
    def __init__(self, base_path: Path) -> None:
        # ... existing __init__ code ...
        self._use_subinterpreters: bool = False  # Opt-in mode for Wave 1

    def enable_subinterpreters(self, enabled: bool = True) -> None:
        """Enable/disable subinterpreter execution mode."""
        self._use_subinterpreters = enabled

    def _get_parallel_executor(
        self,
        max_workers: int,
        *,
        stage: Stage,
        plugin_ids: list[str],
    ) -> concurrent.futures.Executor:
        """Select executor based on Python version and user configuration.

        Returns InterpreterPoolExecutor if:
        1. Python >= 3.14
        2. InterpreterPoolExecutor available
        3. User enabled --use-subinterpreters
        4. All plugins in wavefront are subinterpreter_compatible

        Otherwise returns ThreadPoolExecutor.
        """
        if not self._use_subinterpreters:
            return concurrent.futures.ThreadPoolExecutor(max_workers=max_workers)

        if not HAS_INTERPRETER_POOL:
            # Fallback to ThreadPoolExecutor on Python <3.14
            return concurrent.futures.ThreadPoolExecutor(max_workers=max_workers)

        # Check if all plugins in wavefront are subinterpreter-compatible
        for plugin_id in plugin_ids:
            spec = self.specs.get(plugin_id)
            if spec is None:
                continue
            if not spec.subinterpreter_compatible:
                # Mixed compatibility: use ThreadPoolExecutor
                return concurrent.futures.ThreadPoolExecutor(max_workers=max_workers)

        # All checks passed: use InterpreterPoolExecutor
        return InterpreterPoolExecutor(max_workers=max_workers)
```

**Acceptance:**
- ✅ Returns `InterpreterPoolExecutor` when conditions met
- ✅ Returns `ThreadPoolExecutor` when fallback needed
- ✅ Unit tests cover all selection paths

---

### T4: Manifest Field Extension

**File**: `topology-tools/kernel/plugin_registry.py` (PluginSpec dataclass)

**Changes:**

```python
@dataclass
class PluginSpec:
    # ... existing fields ...
    timeout: float = DEFAULT_PLUGIN_TIMEOUT
    subinterpreter_compatible: bool = False  # ADR 0097 Wave 1

    @classmethod
    def from_dict(cls, data: dict[str, Any], manifest_path: str = "") -> PluginSpec:
        """Create PluginSpec from manifest dictionary."""
        return cls(
            # ... existing field mappings ...
            timeout=data.get("timeout", DEFAULT_PLUGIN_TIMEOUT),
            subinterpreter_compatible=bool(data.get("subinterpreter_compatible", False)),
        )
```

**Schema Update**: `schemas/plugin-manifest.schema.json`

```json
{
  "properties": {
    "subinterpreter_compatible": {
      "type": "boolean",
      "description": "Whether this plugin supports execution in Python 3.14+ subinterpreters (ADR 0097)",
      "default": false
    }
  }
}
```

**Acceptance:**
- ✅ `subinterpreter_compatible` field parsed from manifest
- ✅ Defaults to `false` for backward compatibility
- ✅ Schema validation passes

---

### T5: CLI Flag Support

**File**: `topology-tools/compile-topology.py`

**Changes:**

```python
parser.add_argument(
    "--use-subinterpreters",
    action="store_true",
    help="Enable subinterpreter-based parallel execution (Python 3.14+, ADR 0097)",
)

# In main():
if args.use_subinterpreters:
    registry.enable_subinterpreters(True)
    if not HAS_INTERPRETER_POOL:
        print("Warning: --use-subinterpreters requires Python 3.14+, falling back to threads", file=sys.stderr)
```

**Acceptance:**
- ✅ `--use-subinterpreters` flag recognized
- ✅ Warning emitted on Python <3.14
- ✅ Flag properly propagates to `PluginRegistry`

---

### T6: Isolated Plugin Execution Function

**File**: `topology-tools/kernel/plugin_registry.py`

**Changes:**

```python
def _execute_plugin_isolated(
    serialized_ctx: SerializablePluginContext,
    plugin_id: str,
    stage: Stage,
    phase: Phase,
    base_path: str,
    manifest_path: str,
    spec_dict: dict[str, Any],
) -> PluginResult:
    """Execute plugin in isolated subinterpreter.

    This function is submitted to InterpreterPoolExecutor. It:
    1. Deserializes context
    2. Loads plugin class
    3. Executes plugin
    4. Serializes result

    All arguments must be picklable for cross-interpreter transfer.
    """
    import sys
    from pathlib import Path

    # Reconstruct registry in this interpreter
    sys.path.insert(0, base_path)
    from kernel.plugin_registry import PluginRegistry, PluginSpec
    from kernel.plugin_base import Stage, Phase

    registry = PluginRegistry(Path(base_path))
    registry.specs[plugin_id] = PluginSpec.from_dict(spec_dict, manifest_path)

    # Deserialize context
    ctx = serialized_ctx.to_plugin_context()

    # Execute plugin
    plugin = registry.load_plugin(plugin_id)
    result = plugin.execute_phase(ctx, Stage(stage), Phase(phase))

    return result
```

**Acceptance:**
- ✅ Function serializable for `InterpreterPoolExecutor.submit()`
- ✅ Plugin executes correctly in isolated interpreter
- ✅ Result properly returned to main interpreter

---

### T7: Update Parallel Execution Logic

**File**: `topology-tools/kernel/plugin_registry.py` (method `_execute_phase_parallel`)

**Changes:**

```python
def _execute_phase_parallel(
    self,
    *,
    stage: Stage,
    phase: Phase,
    ctx: PluginContext,
    plugin_ids: list[str],
    trace_execution: bool = False,
    contract_warnings: bool = False,
    contract_errors: bool = False,
) -> list[PluginResult]:
    """Execute one phase in dependency-respecting wavefronts."""
    if not plugin_ids:
        return []

    # ... existing dependency graph setup ...

    results_by_plugin: dict[str, PluginResult] = {}
    max_workers = min(8, max(1, len(plugin_ids)))

    # CHANGE: Use dynamic executor selection
    executor = self._get_parallel_executor(max_workers, stage=stage, plugin_ids=plugin_ids)

    with executor:
        while ready:
            wavefront: list[str] = []
            while ready:
                _, plugin_id = heapq.heappop(ready)
                wavefront.append(plugin_id)

            futures: dict[concurrent.futures.Future[PluginResult], str] = {}
            for plugin_id in wavefront:
                if trace_execution:
                    self._trace_event(event="plugin_start", stage=stage, phase=phase, plugin_id=plugin_id)

                # CHANGE: Use InterpreterPoolExecutor if available
                if isinstance(executor, InterpreterPoolExecutor):
                    spec = self.specs[plugin_id]
                    serialized_ctx = SerializablePluginContext.from_plugin_context(ctx)
                    future = executor.submit(
                        _execute_plugin_isolated,
                        serialized_ctx,
                        plugin_id,
                        stage.value,
                        phase.value,
                        str(self.base_path),
                        spec.manifest_path,
                        spec.__dict__,  # Serialize spec as dict
                    )
                else:
                    # ThreadPoolExecutor: existing code
                    future = executor.submit(
                        self.execute_plugin,
                        plugin_id,
                        ctx,
                        stage,
                        phase,
                        None,
                        record_result=False,
                        contract_warnings=contract_warnings,
                        contract_errors=contract_errors,
                    )
                futures[future] = plugin_id

            # ... existing result collection code ...

    # ... existing code ...
```

**Acceptance:**
- ✅ Uses `InterpreterPoolExecutor` when conditions met
- ✅ Falls back to `ThreadPoolExecutor` when needed
- ✅ Both execution paths produce valid results

---

### T8: Parity Test Suite

**File**: `tests/test_adr0097_parity.py` (new)

**Tests:**

1. `test_executor_selection_python_14`
   - Python 3.14 + flag: `InterpreterPoolExecutor`
   - Python 3.14 + no flag: `ThreadPoolExecutor`

2. `test_executor_selection_python_13`
   - Python 3.13: always `ThreadPoolExecutor`

3. `test_context_serialization_roundtrip`
   - Serialize → deserialize → verify equality

4. `test_parallel_execution_parity`
   - Run same wavefront with ThreadPool and InterpreterPool
   - Assert identical: plugin results, diagnostics, published data

5. `test_mixed_compatibility_fallback`
   - Wavefront with `subinterpreter_compatible: false` plugin
   - Assert uses `ThreadPoolExecutor`

**Acceptance:**
- ✅ All parity tests pass
- ✅ Coverage ≥80% for new code

---

## Implementation Phases

### Phase 1: Foundation (Day 1)

1. Create `SerializablePluginContext` dataclass
2. Add conditional `InterpreterPoolExecutor` import
3. Add `subinterpreter_compatible` field to `PluginSpec`
4. Update JSON schema

**Gate**: Schema validation passes, no import errors

---

### Phase 2: Executor Logic (Day 2)

1. Implement `_get_parallel_executor()` method
2. Implement `_execute_plugin_isolated()` function
3. Add `enable_subinterpreters()` API
4. Update `_execute_phase_parallel()` to use dynamic executor

**Gate**: Code compiles, type checking passes

---

### Phase 3: CLI Integration (Day 3)

1. Add `--use-subinterpreters` flag to `compile-topology.py`
2. Wire flag to `registry.enable_subinterpreters()`
3. Add warning for Python <3.14

**Gate**: CLI help shows flag, manual execution works

---

### Phase 4: Testing (Day 4)

1. Write parity test suite
2. Run tests on Python 3.14 (both executors)
3. Run tests on Python 3.13 (ThreadPool only)
4. Fix any discovered issues

**Gate**: All tests pass, coverage ≥80%

---

### Phase 5: Documentation (Day 5)

1. Update ADR 0097 status to "Wave 1 Complete"
2. Document Wave 1 evidence in `WAVE-1-EVIDENCE.md`
3. Create operator guide for `--use-subinterpreters` flag

**Gate**: Documentation complete, ready for Wave 2

---

## Exit Criteria

**Wave 1 is complete when:**

| Criterion | Status |
|-----------|--------|
| `InterpreterPoolExecutor` conditional import works | ✅ |
| `SerializablePluginContext` serializes/deserializes correctly | ✅ |
| `--use-subinterpreters` CLI flag functional | ✅ |
| `subinterpreter_compatible` manifest field recognized | ✅ |
| Parity tests pass (ThreadPool vs InterpreterPool) | ✅ |
| No regressions in existing tests | ✅ |
| Documentation updated | ✅ |

---

## Risks and Mitigations

### R1: InterpreterPoolExecutor API Unstable

**Risk**: Python 3.14 API may change before official release.

**Mitigation**:
- Use conditional import with try/except
- Fallback to ThreadPoolExecutor if import fails
- Monitor Python 3.14 beta releases

---

### R2: Serialization Overhead

**Risk**: JSON serialization of `compiled_json` (~500KB-2MB) may add latency.

**Mitigation**:
- Benchmark serialization overhead in parity tests
- Accept +5-10ms overhead for Wave 1 (optimization deferred to Wave 3)
- Use `orjson` if standard library JSON is too slow

---

### R3: Extension Module Incompatibility

**Risk**: PyYAML or other C extensions may not support subinterpreters.

**Mitigation**:
- Test with all current dependencies in parity suite
- Use `subinterpreter_compatible: false` for incompatible plugins
- Document known incompatibilities

---

## Dependencies

| Dependency | Status | Notes |
|------------|--------|-------|
| ADR 0098 (Python 3.14) | ✅ Complete | Python 3.14.4 installed on dev workstation |
| Plugin manifest schema | ✅ Available | `schemas/plugin-manifest.schema.json` |
| Existing test suite | ✅ Passing | 1334 tests, 79% coverage |

---

## Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Parity test pass rate | 100% | All parity tests green |
| Existing test regressions | 0 | No failures introduced |
| Performance overhead | <10ms | Serialization benchmark |
| Code coverage (new code) | ≥80% | pytest-cov |
| Implementation time | ≤5 days | Phase completion dates |

---

## Next Wave

After Wave 1 completion, proceed to **Wave 2: Validator Migration**:

1. Audit all validator dependencies for subinterpreter compatibility
2. Mark compatible validators with `subinterpreter_compatible: true`
3. Enable subinterpreters for validate stage by default
4. Monitor performance metrics

**Gate**: All validators pass with subinterpreters; no regressions.

---

**Document Owner**: Infrastructure Team
**Last Updated**: 2026-04-14
**Next Review**: After Wave 1 completion
