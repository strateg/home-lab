# Plugin Architecture Simplification Analysis

**Date:** 2026-05-31
**Status:** Complete
**Scope:** Plugin Kernel Architecture (kernel/, registry/, scheduler/)

---

## Implementation Status

| Item | Status | Commit |
|------|--------|--------|
| QW1: Remove `subinterpreter_compatible` | ✅ Complete | c4325e10 |
| QW2: Remove Event Plane API | ✅ Complete | 2adcffeb |
| QW3: Consolidate `_declared_produced_scopes` | ✅ Complete | 9fadd233 |
| Extract `_validate_envelope_for_commit` | ✅ Complete | 64aca9f3 |
| ME1: Complete ExecutionPlanner delegation | ✅ Complete | d5ea713a |

**Total LOC reduction:** ~330 lines removed from plugin_registry.py (2,455 → 2,328)
**Documentation removed:** 438 lines (PLUGIN-EVENT-PATTERNS.md)

---

## Executive Summary

This analysis examines the v5 plugin system architecture to identify simplification opportunities. The current architecture spans **5,877 LOC** across 15 kernel modules, with the main `plugin_registry.py` at 2,455 LOC being the primary complexity concern.

**Key Findings:**
- **Partial decomposition complete:** Registry and scheduler submodules extracted, but integration layer in `plugin_registry.py` retains significant duplication
- **Dead/underused features:** Event plane (0% usage), `when` predicates (0% usage), `requires_capabilities` (0% manifest usage), `model_versions` (0% manifest usage)
- **Deprecated field still supported:** `subinterpreter_compatible` (146 references, mostly in test/documentation)
- **Duplication opportunities:** 3 methods duplicated across modules

**Recommendations prioritized by impact/effort:**
1. **Quick Win:** Remove deprecated `subinterpreter_compatible` field (Effort: Low, Impact: Medium)
2. **Quick Win:** Remove unused event plane API (Effort: Low, Impact: Medium)
3. **Medium Effort:** Complete delegation pattern - eliminate duplicated methods (Effort: Medium, Impact: High)
4. **Larger Effort:** Consider removing/simplifying underused features after stakeholder review

---

## 1. Current State Analysis

### 1.1 LOC Breakdown by Module

| Module | LOC | Responsibility | Notes |
|--------|-----|----------------|-------|
| `plugin_registry.py` | 2,455 | Main facade, execution orchestration | **Primary target for reduction** |
| `plugin_base.py` | 1,272 | Base classes, enums, context, snapshot | Well-structured data types |
| `scheduler/snapshot_builder.py` | 258 | Build input snapshots | Clean extraction |
| `scheduler/parallel_executor.py` | 256 | Parallel execution, wavefronts | Clean extraction |
| `scheduler/execution_planner.py` | 232 | Execution order, filtering | **Duplicates logic in registry** |
| `registry/spec_validator.py` | 228 | Spec validation, constants | Clean extraction |
| `registry/dependency_resolver.py` | 213 | Dependency graph resolution | Clean extraction |
| `registry/config_validator.py` | 213 | Config schema validation | Clean extraction |
| `registry/manifest_loader.py` | 196 | Manifest loading/parsing | Clean extraction |
| `registry/plugin_loader.py` | 173 | Plugin class loading | Clean extraction |
| `pipeline_runtime.py` | 113 | Pipeline state management | Clean, focused |
| `plugin_runner.py` | 73 | Single-plugin envelope execution | Clean, minimal |
| **Total** | **5,877** | | |

### 1.2 Complexity Metrics (from SWOT Analysis)

| Metric | Value | Target | Status |
|--------|-------|--------|--------|
| Max dependency depth | 19 | <=6 | **Exceeds target** |
| Max dependents (instance_rows) | 37 | N/A | Intentional bottleneck |
| Subinterpreter coverage | 88.1% (74/84) | >95% | Approaching target |
| `when` field usage | 0% | N/A | **Unused feature** |
| Event plane usage | 0% | N/A | **Unused feature** |

---

## 2. Dead Code and Unused Features

### 2.1 Completely Unused Features (0% adoption)

| Feature | Location | LOC Est. | Evidence | Recommendation |
|---------|----------|----------|----------|----------------|
| **Event Plane API** | `plugin_base.py:841-959` | ~120 | No plugins call `emit()`, `subscribe_topic()`, or `poll_events()` | Remove or mark experimental |
| **`when` predicates** | `plugin_registry.py`, `execution_planner.py` | ~80 | No manifests use `when:` block | Keep but document as opt-in |
| **`requires_capabilities`** | `plugin_registry.py:2356-2403` | ~50 | No manifests declare it | Keep minimal validation |
| **`model_versions`** | `plugin_registry.py:2281-2354` | ~75 | No manifests declare it | Keep minimal validation |

### 2.2 Deprecated Features Still Supported

| Feature | Location | References | Recommendation |
|---------|----------|------------|----------------|
| `subinterpreter_compatible` | `plugin_registry.py:147,176,254-281` | 146 (mostly test/docs) | **Remove in next major version** |

### 2.3 Underused Features

| Feature | Location | Usage | Recommendation |
|---------|----------|-------|----------------|
| `compiled_json_owner` | `plugin_registry.py:170,674-677` | 1 plugin | Keep - critical for owner contract |
| `input_view` | `plugin_registry.py:149,182-252` | 3 plugins | Keep - supports snapshot optimization |
| `capabilities` | Various | 6 files use | Keep - actively expanding |

---

## 3. Duplication Analysis

### 3.1 Duplicated Methods Between plugin_registry.py and Submodules

| Method | Duplicated In | Duplication Type | LOC Wasted |
|--------|---------------|------------------|------------|
| `_declared_produced_scopes()` | `snapshot_builder.py`, `dependency_resolver.py`, `plugin_registry.py` | Full duplicate | ~40 |
| `_when_predicates_allow()` | `execution_planner.py`, `plugin_registry.py` | Full duplicate | ~35 |
| `get_execution_order()` | `execution_planner.py`, `plugin_registry.py` | Partial overlap | ~50 |
| `_topological_order()` / `_topological_sort()` | `execution_planner.py`, `dependency_resolver.py` | Semantic duplicate | ~40 |

**Total estimated duplicate LOC:** ~165

### 3.2 Delegation Pattern Analysis

The decomposition to submodules is **partially complete**. Several methods in `plugin_registry.py` delegate to submodules with thin wrappers:

```python
# Current pattern (good - thin delegation):
def _declared_produced_scopes(spec: PluginSpec) -> dict[str, str]:
    return SnapshotBuilder._declared_produced_scopes(spec)

# But then also used directly:
declared_produces = {key for key in self._declared_produced_scopes(spec)}  # line 767
declared_produces = {key for key in self._declared_produced_scopes(spec)}  # line 1164
produced_key_scopes = self._declared_produced_scopes(spec)  # line 1805
```

**Issue:** The delegation exists but the facade still contains substantial inline logic that could be pushed to submodules.

---

## 4. Simplification Opportunities

### 4.1 Ranked by Impact/Effort

| # | Opportunity | Impact | Effort | LOC Saved | Risk |
|---|-------------|--------|--------|-----------|------|
| 1 | Remove deprecated `subinterpreter_compatible` field | Medium | Low | ~30 | Low (deprecation path exists) |
| 2 | Remove/hide event plane API | Medium | Low | ~120 | Low (0% usage) |
| 3 | Complete delegation - move `_when_predicates_allow` usage to `ExecutionPlanner` | High | Medium | ~60 | Medium |
| 4 | Complete delegation - move `get_execution_order` implementation to `ExecutionPlanner` | High | Medium | ~50 | Medium |
| 5 | Extract `_execute_phase_parallel` to `ParallelExecutor` | High | High | ~350 | High (complex state) |
| 6 | Extract `_execute_stage` orchestration to separate orchestrator | High | High | ~200 | High |
| 7 | Remove `_validate_model_versions` if never used | Low | Low | ~75 | Low |
| 8 | Remove `_validate_required_capabilities` if never used in manifests | Low | Low | ~50 | Low |

### 4.2 Quick Wins (Low Effort, Immediate Value)

#### QW1: Remove Deprecated `subinterpreter_compatible` Field ✅ COMPLETE

**Status:** Completed in commit c4325e10

- Removed field from `PluginSpec` dataclass
- Removed `_resolve_execution_mode` fallback logic
- Updated tests to use `execution_mode` directly
- Updated manifest YAML files

**Actual savings:** ~30 LOC

#### QW2: Remove Event Plane API ✅ COMPLETE

**Status:** Completed in commit 2adcffeb

- Removed `EventMessage` and `EmittedEvent` dataclasses from `plugin_base.py`
- Removed `emit()`, `subscribe_topic()`, `poll_events()`, `get_event_history()`, `drain_event_outbox()` methods
- Removed event-related fields from `PluginContext` and `PluginExecutionEnvelope`
- Updated `PipelineState` to remove event handling
- Deleted `docs/guides/PLUGIN-EVENT-PATTERNS.md` (438 LOC)

**Actual savings:** ~120 LOC core + 438 LOC documentation

#### QW3: Consolidate `_declared_produced_scopes` ✅ COMPLETE

**Status:** Completed in commit 9fadd233

- Added `declared_produced_scopes()` method to `PluginSpec` dataclass
- Removed duplicate implementations from `dependency_resolver.py`, `snapshot_builder.py`, and `plugin_registry.py`
- Updated all call sites to use `spec.declared_produced_scopes()`

**Actual savings:** ~40 LOC, eliminated divergence risk

### 4.3 Medium Effort Improvements

#### ME1: Complete ExecutionPlanner Integration ✅ COMPLETE

**Status:** Completed in commit d5ea713a

- Initialized `_execution_planner` in `PluginRegistry.__init__`
- Delegated `_when_predicates_allow()` to ExecutionPlanner
- Delegated `_active_changed_input_scopes()` to ExecutionPlanner
- Delegated `_profile_allows_spec()` to ExecutionPlanner
- Delegated `get_execution_order()` to ExecutionPlanner
- Delegated `_plugin_sort_key()` to ExecutionPlanner

**Actual savings:** ~90 LOC removed from plugin_registry.py

#### ME2: Extract Parallel Execution Coordination

**Current state:**
- `_execute_phase_parallel()` is 335 lines (lines 1378-1712)
- Mixes concerns: wavefront computation, snapshot building, executor management, result handling

**Action:**
1. Move wavefront computation to `ParallelExecutor.compute_wavefronts()` (partially done)
2. Extract result handling to separate method
3. Create `PhaseExecutionCoordinator` class or equivalent

**Estimated savings:** 150-200 LOC in registry, cleaner separation

### 4.4 Larger Refactoring (Not Recommended Short-Term)

These require significant effort and have higher risk:

| Opportunity | Effort | Risk | Recommendation |
|-------------|--------|------|----------------|
| Full registry decomposition | Very High | High | Defer - current structure works |
| Remove `when` field support | Low | Medium | Keep - may become useful |
| Rewrite parallel execution | Very High | Very High | Defer - current works |

---

## 5. Architectural Observations

### 5.1 What Works Well

1. **Plugin base classes** (`plugin_base.py`) - Clean, well-typed, minimal
2. **Extracted modules** - Each focuses on single responsibility
3. **Pipeline state** (`pipeline_runtime.py`) - Clean commit/resolve semantics
4. **Snapshot/envelope model** - Well-designed actor semantics

### 5.2 What Could Be Improved

1. **Facade complexity** - `plugin_registry.py` still too large (2,455 LOC)
2. **Incomplete delegation** - Submodules exist but facade retains duplicate logic
3. **Feature creep** - Event plane, input_view added but not adopted
4. **Test-driven deprecation debt** - Old fields kept for test compatibility

### 5.3 Root Cause Analysis

The high LOC in `plugin_registry.py` stems from:
1. **Execution orchestration logic** (~800 LOC) - `execute_stage`, `_execute_phase_parallel`
2. **Contract validation** (~400 LOC) - produces/consumes schema validation
3. **Backward compatibility** (~200 LOC) - Legacy paths, deprecated fields
4. **Delegation overhead** (~150 LOC) - Thin wrappers to submodules
5. **Inline utilities** (~100 LOC) - Could be extracted

---

## 6. Recommendations

### 6.1 Immediate Actions (This Sprint)

| # | Action | Effort | Status |
|---|--------|--------|--------|
| 1 | Remove deprecated `subinterpreter_compatible` field | 4h | ✅ Complete (c4325e10) |
| 2 | Remove unused Event Plane API | 4h | ✅ Complete (2adcffeb) |
| 3 | Consolidate `_declared_produced_scopes` to single source | 4h | ✅ Complete (9fadd233) |

### 6.2 Short-Term (Next 2 Weeks)

| # | Action | Effort | Status |
|---|--------|--------|--------|
| 1 | Complete `ExecutionPlanner` delegation | 8h | Pending |
| 2 | Remove deprecated `subinterpreter_compatible` in next version | 4h | ✅ Complete (c4325e10) |
| 3 | Extract `_validate_envelope_for_commit` to separate validator class | 4h | ✅ Complete (64aca9f3) |

### 6.3 Medium-Term (Next Month)

| # | Action | Effort | Owner |
|---|--------|--------|-------|
| 1 | Extract `_execute_phase_parallel` orchestration to `ParallelExecutor` | 16h | - |
| 2 | Review unused features (`when`, `model_versions`) with stakeholders | 4h | - |
| 3 | Create architectural lint preventing new duplication | 8h | - |

### 6.4 NOT Recommended

| Action | Reason |
|--------|--------|
| Full rewrite of plugin_registry.py | Too risky, current works |
| Remove `when` field support | May become useful for conditional execution |
| Remove event plane entirely | May become useful for async patterns |
| Aggressive LOC reduction targets | Quality > metrics |

---

## 7. Risks and Considerations

### 7.1 Risks of Action

| Risk | Mitigation |
|------|------------|
| Breaking existing tests | Run full test suite after each change |
| Breaking manifest compatibility | Schema validation catches issues |
| Performance regression | Benchmark parallel execution |
| Developer confusion | Update documentation alongside changes |

### 7.2 Risks of Inaction

| Risk | Impact |
|------|--------|
| Continued complexity growth | Harder maintenance |
| Feature divergence (duplicate methods) | Subtle bugs |
| Dead code accumulation | Cognitive overhead |
| Onboarding difficulty | Slower contributor ramp |

---

## 8. Validation Steps

After any simplification:

1. **Run full test suite:**
   ```bash
   python -m pytest tests/ -q
   ```

2. **Run compilation:**
   ```bash
   python topology-tools/compile-topology.py
   ```

3. **Check parallel execution parity:**
   ```bash
   python topology-tools/compile-topology.py --no-parallel-plugins
   # Compare output
   ```

4. **Verify deprecation warnings:**
   ```bash
   python -W error::DeprecationWarning topology-tools/compile-topology.py
   ```

---

## Appendix A: File References

| File | Path |
|------|------|
| plugin_registry.py | `/home/nixos/workspaces/home-lab/topology-tools/kernel/plugin_registry.py` |
| plugin_base.py | `/home/nixos/workspaces/home-lab/topology-tools/kernel/plugin_base.py` |
| plugin_runner.py | `/home/nixos/workspaces/home-lab/topology-tools/kernel/plugin_runner.py` |
| pipeline_runtime.py | `/home/nixos/workspaces/home-lab/topology-tools/kernel/pipeline_runtime.py` |
| registry/__init__.py | `/home/nixos/workspaces/home-lab/topology-tools/kernel/registry/__init__.py` |
| registry/spec_validator.py | `/home/nixos/workspaces/home-lab/topology-tools/kernel/registry/spec_validator.py` |
| registry/dependency_resolver.py | `/home/nixos/workspaces/home-lab/topology-tools/kernel/registry/dependency_resolver.py` |
| registry/config_validator.py | `/home/nixos/workspaces/home-lab/topology-tools/kernel/registry/config_validator.py` |
| registry/envelope_validator.py | `/home/nixos/workspaces/home-lab/topology-tools/kernel/registry/envelope_validator.py` |
| registry/manifest_loader.py | `/home/nixos/workspaces/home-lab/topology-tools/kernel/registry/manifest_loader.py` |
| registry/plugin_loader.py | `/home/nixos/workspaces/home-lab/topology-tools/kernel/registry/plugin_loader.py` |
| scheduler/__init__.py | `/home/nixos/workspaces/home-lab/topology-tools/kernel/scheduler/__init__.py` |
| scheduler/execution_planner.py | `/home/nixos/workspaces/home-lab/topology-tools/kernel/scheduler/execution_planner.py` |
| scheduler/parallel_executor.py | `/home/nixos/workspaces/home-lab/topology-tools/kernel/scheduler/parallel_executor.py` |
| scheduler/snapshot_builder.py | `/home/nixos/workspaces/home-lab/topology-tools/kernel/scheduler/snapshot_builder.py` |

## Appendix B: Related ADRs

| ADR | Title | Relevance |
|-----|-------|-----------|
| ADR 0063 | Plugin Microkernel | Core architecture |
| ADR 0086 | Flatten Plugin Hierarchy | Level boundaries |
| ADR 0097 | Subinterpreter Execution | Execution mode routing |
| ADR 0099 | Test Architecture Refactor | Snapshot/envelope testing |

---

*Analysis conducted 2026-05-31. ADR: not required (analysis document, no architectural decision).*
