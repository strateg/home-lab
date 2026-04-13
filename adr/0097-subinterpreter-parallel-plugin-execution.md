# ADR 0097: Subinterpreter-Based Parallel Plugin Execution

- Status: Proposed
- Date: 2026-04-13
- Depends on: ADR 0063, ADR 0080, ADR 0086
- Target Python: 3.14+

## Context

### Current State

The plugin runtime (ADR 0080) implements parallel execution using `ThreadPoolExecutor` with
extensive thread-safety measures:

1. `PluginExecutionScope` + `contextvars.ContextVar` for thread-local state
2. `threading.Lock` for `_published_data` and `_instances_lock`
3. `compiled_json_owner` validation for mutation safety
4. Deterministic result ordering post-execution

This architecture works correctly but has inherent complexity:
- 9 lock acquisition points in `plugin_base.py`
- Race condition prevention requires careful code review
- Future plugins must understand threading constraints
- Debugging concurrent issues is challenging

### Python 3.14 Opportunity

Python 3.14 (expected October 2025) introduces official subinterpreter support:

- **PEP 734**: `concurrent.interpreters` module for subinterpreter management
- **PEP 684**: Per-interpreter GIL (implemented in Python 3.12+)
- **`InterpreterPoolExecutor`**: Drop-in replacement for `ThreadPoolExecutor`

Key insight: Subinterpreters provide **isolation by design** — shared mutable state
is impossible, eliminating race conditions architecturally rather than through locks.

### Growth Trajectory

Current plugin inventory: 57 plugins across 7 manifests.
Expected growth: 100+ plugins as generator/validator coverage expands.

Early migration is cheaper than retrofitting after ecosystem expansion.

## Decision

### D1. Adopt `InterpreterPoolExecutor` as Primary Parallel Executor

Replace `ThreadPoolExecutor` with `InterpreterPoolExecutor` for plugin wavefront execution
when running on Python 3.14+.

```python
# Current implementation (ThreadPoolExecutor)
from concurrent.futures import ThreadPoolExecutor

with ThreadPoolExecutor(max_workers=8) as pool:
    futures = [pool.submit(self.execute_plugin, plugin_id, ctx, ...) for plugin_id in wavefront]

# Target implementation (InterpreterPoolExecutor)
from concurrent.futures import InterpreterPoolExecutor

with InterpreterPoolExecutor(max_workers=8) as pool:
    futures = [pool.submit(execute_plugin_isolated, plugin_id, serialized_ctx) for plugin_id in wavefront]
```

### D2. Implement Context Serialization Protocol

Since subinterpreters have isolated memory, `PluginContext` must be serialized for transfer:

```python
@dataclass
class SerializablePluginContext:
    """Minimal context for cross-interpreter plugin execution."""
    topology_path: str
    profile: str
    compiled_json: bytes  # JSON-serialized
    plugin_config: bytes  # JSON-serialized
    output_dir: str
    # ... minimal required fields
```

Serialization boundary:
- **Input**: `compiled_json`, `plugin_config`, paths
- **Output**: `PluginResult` with diagnostics and published data
- **NOT serialized**: File handles, locks, mutable state (not needed)

### D3. Retain ThreadPoolExecutor Fallback

Maintain dual-executor architecture for:
- Python < 3.14 compatibility
- Extension modules without subinterpreter support
- Debugging/development mode

```python
def _get_parallel_executor(self, max_workers: int) -> Executor:
    if sys.version_info >= (3, 14) and self._subinterpreters_enabled:
        return InterpreterPoolExecutor(max_workers=max_workers)
    return ThreadPoolExecutor(max_workers=max_workers)
```

### D4. Simplify Lock Architecture (Post-Migration)

After subinterpreter adoption, the following become unnecessary for parallel execution:

| Component | Current Purpose | Post-Migration |
|-----------|----------------|----------------|
| `_published_data_lock` | Thread-safe publish/subscribe | Remove (isolated memory) |
| `PluginExecutionScope` | Thread-local state | Simplify (natural isolation) |
| `contextvars.copy_context()` | Context propagation | Remove (serialize instead) |
| `compiled_json_owner` validation | Mutation prevention | Retain (compile-stage safety) |

### D5. Extension Compatibility Gate

Before enabling subinterpreters for a plugin, validate its dependencies:

```yaml
# plugins.yaml extension
- id: base.validator.json_schema
  kind: validator_json
  subinterpreter_compatible: true  # Explicit opt-in after testing

- id: vendor.generator.legacy
  kind: generator
  subinterpreter_compatible: false  # Requires ThreadPoolExecutor
```

## Architecture Comparison

### Race Condition Elimination

| Scenario | ThreadPoolExecutor | InterpreterPoolExecutor |
|----------|-------------------|------------------------|
| Shared `_published_data` | Lock required | Impossible (isolated) |
| `ctx.compiled_json` mutation | Owner validation | Impossible (copied) |
| Config bleed | `PluginExecutionScope` | Impossible (isolated) |
| Instance cache race | Lock required | Impossible (per-interpreter) |

### Performance Characteristics

| Aspect | ThreadPoolExecutor | InterpreterPoolExecutor |
|--------|-------------------|------------------------|
| Startup overhead | ~1ms per thread | ~10-50ms per interpreter |
| Memory per worker | ~1MB (stack) | ~10-20MB (interpreter state) |
| GIL contention | Shared GIL | Per-interpreter GIL |
| Serialization | None (shared memory) | JSON encode/decode |
| True parallelism | I/O-bound only | CPU + I/O |

### Break-Even Analysis

For I/O-bound plugins (current workload):
- Serialization overhead: ~1-5ms per plugin invocation
- Interpreter startup: ~50ms (amortized across wavefront)
- Lock contention saved: ~0.5-2ms per lock acquisition

**Recommendation**: Enable for wavefronts with ≥4 plugins where parallelism benefit exceeds overhead.

## Migration Plan

### Wave 1: Infrastructure (Python 3.14 Release + 2 months)

1. Add `InterpreterPoolExecutor` conditional import
2. Implement `SerializablePluginContext` protocol
3. Add `--use-subinterpreters` CLI flag (opt-in)
4. Add `subinterpreter_compatible` manifest field
5. Create compatibility test suite

**Gate**: Parity tests pass for both executors

### Wave 2: Validator Migration (Wave 1 + 1 month)

1. Audit validator dependencies for subinterpreter compatibility
2. Mark compatible validators with `subinterpreter_compatible: true`
3. Enable subinterpreters for validate stage by default
4. Monitor performance metrics

**Gate**: All validators pass with subinterpreters; no regressions

### Wave 3: Generator Migration (Wave 2 + 1 month)

1. Audit generator dependencies (Jinja2, YAML)
2. Mark compatible generators
3. Enable for generate stage
4. Benchmark file I/O parallelism improvement

**Gate**: Generators produce identical output; I/O parallelism measurable

### Wave 4: Lock Removal (Wave 3 + 1 month)

1. Remove `_published_data_lock` (subinterpreter mode)
2. Simplify `PluginExecutionScope` to minimal form
3. Remove `contextvars` complexity
4. Update documentation

**Gate**: Codebase simplified; ThreadPoolExecutor fallback still works

### Wave 5: Default Promotion (Wave 4 + 1 month)

1. Make `--use-subinterpreters` default on Python 3.14+
2. Add `--no-subinterpreters` for fallback
3. Deprecate ThreadPoolExecutor for new plugins
4. Performance benchmarks published

**Gate**: Subinterpreters are production default

## Dependency Compatibility Matrix

| Dependency | Subinterpreter Ready | Notes |
|------------|---------------------|-------|
| `json` (stdlib) | Yes | Pure Python |
| `pathlib` (stdlib) | Yes | Pure Python |
| `yaml` (PyYAML) | Testing Required | C extension, needs verification |
| `jinja2` | Likely Yes | Pure Python core |
| `jsonschema` | Yes | Pure Python |
| Internal `kernel.*` | Yes | Pure Python |

## Risks and Mitigations

### R1: PyYAML Subinterpreter Compatibility

**Risk**: PyYAML uses C extension that may not support subinterpreters.

**Mitigation**:
- Test with `yaml.CSafeLoader` vs `yaml.SafeLoader`
- Fall back to pure Python loader if needed
- Monitor PyYAML project for subinterpreter updates

### R2: Serialization Overhead

**Risk**: JSON serialization of `compiled_json` (~500KB-2MB) adds latency.

**Mitigation**:
- Serialize once per wavefront, not per plugin
- Use `orjson` for faster serialization
- Consider `memoryview` for large payloads (Python 3.14 supports this)

### R3: Interpreter Startup Cost

**Risk**: Creating interpreters is slower than threads.

**Mitigation**:
- Pool interpreters across wavefronts (persistent pool)
- Only use for wavefronts with ≥4 plugins
- Pre-warm interpreters during discovery stage

### R4: Debugging Complexity

**Risk**: Errors in subinterpreters harder to trace.

**Mitigation**:
- Capture full traceback in serialized result
- Add interpreter ID to diagnostics
- Provide `--no-subinterpreters` escape hatch

## Acceptance Criteria

1. `InterpreterPoolExecutor` works on Python 3.14+ for plugin execution
2. `SerializablePluginContext` protocol implemented and tested
3. All current plugins pass with subinterpreter execution
4. Parity tests verify identical output (ThreadPool vs InterpreterPool)
5. `subinterpreter_compatible` manifest field enforced
6. Lock removal demonstrated in subinterpreter mode
7. Performance benchmarks show improvement for ≥4 plugin wavefronts
8. ThreadPoolExecutor fallback works on Python < 3.14
9. Documentation updated for plugin authors

## References

- [PEP 554 – Multiple Interpreters in the Stdlib](https://peps.python.org/pep-0554/)
- [PEP 684 – A Per-Interpreter GIL](https://peps.python.org/pep-0684/)
- [Python 3.14 What's New](https://docs.python.org/3/whatsnew/3.14.html)
- [Real Python: Python 3.12 Subinterpreters](https://realpython.com/python312-subinterpreters/)
- [Running Python Parallel Applications with Sub Interpreters](https://tonybaloney.github.io/posts/sub-interpreter-web-workers.html)
- ADR 0063: Plugin Microkernel Architecture
- ADR 0080: Unified Build Pipeline (Section 9: Parallel Execution)
- ADR 0086: Flatten Plugin Hierarchy
