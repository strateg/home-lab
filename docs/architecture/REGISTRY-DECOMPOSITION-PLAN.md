# Plugin Registry Decomposition Plan

**Date:** 2026-05-29
**Source:** Phase 3 Plugin System Development Plan (P3.1)
**Status:** In Progress

---

## Overview

Decompose `plugin_registry.py` (2860 LOC) into focused submodules (<500 LOC each).

---

## Current State

```
topology-tools/kernel/
├── plugin_registry.py     # 2860 LOC (monolith)
├── plugin_base.py         # ~600 LOC (keep as-is)
├── plugin_runner.py       # ~200 LOC (keep as-is)
├── pipeline_runtime.py    # ~300 LOC (keep as-is)
├── registry/              # NEW - stub created
│   └── __init__.py
└── scheduler/             # NEW - stub created
    └── __init__.py
```

---

## Target Structure

```
topology-tools/kernel/
├── plugin_registry.py          # ~300 LOC (facade only)
├── plugin_base.py              # ~600 LOC (unchanged)
├── plugin_runner.py            # ~200 LOC (unchanged)
├── pipeline_runtime.py         # ~300 LOC (unchanged)
├── registry/
│   ├── __init__.py
│   ├── manifest_loader.py      # ~300 LOC
│   ├── spec_validator.py       # ~400 LOC
│   ├── dependency_resolver.py  # ~300 LOC
│   ├── plugin_loader.py        # ~400 LOC
│   └── config_validator.py     # ~200 LOC
└── scheduler/
    ├── __init__.py
    ├── execution_planner.py    # ~300 LOC
    ├── parallel_executor.py    # ~400 LOC
    └── snapshot_builder.py     # ~300 LOC
```

---

## Extraction Phases

### Phase A: Registry Modules

| Module | Lines | Methods to Extract | Status |
|--------|-------|-------------------|--------|
| manifest_loader.py | ~300 | `_get_manifest_schema`, `_validate_manifest_payload`, `load_manifest`, `load_manifests_from_dir` | Pending |
| spec_validator.py | ~400 | `_validate_spec`, `_is_api_compatible`, `_extract_entry_plugin_family`, `_entry_uses_plugins_prefix_without_family` | Pending |
| dependency_resolver.py | ~300 | `resolve_dependencies`, `_validate_declared_data_bus_contracts`, `_is_stage_local_consumption_valid`, `get_execution_order`, `_plugin_sort_key` | Pending |
| plugin_loader.py | ~400 | `load_plugin`, `_load_entry_point`, `_preload_plugins`, `_ensure_import_path` | Pending |
| config_validator.py | ~200 | `validate_plugin_config`, `_resolve_payload_schema_path`, `_load_payload_schema`, `_schema_ref_by_produced_key`, `_schema_ref_by_consumed_key` | Pending |

### Phase B: Scheduler Modules

| Module | Lines | Methods to Extract | Status |
|--------|-------|-------------------|--------|
| execution_planner.py | ~300 | `_when_predicates_allow`, `_profile_allows_spec`, `_stage_rank`, `_phase_rank`, `_string_list`, `_active_changed_input_scopes`, `_declared_produced_scopes`, `_declared_consumes` | Pending |
| parallel_executor.py | ~400 | `_execute_phase_parallel`, `_get_parallel_executor`, `_execute_plugin_envelope_local`, `_is_cross_interpreter_shareability_error` | Pending |
| snapshot_builder.py | ~300 | `_build_input_snapshot`, `_compatibility_producer_ids`, `_ensure_pipeline_state`, `_mirror_context_into_pipeline_state`, `_sync_pipeline_state_to_context` | Pending |

### Phase C: Facade Refactor

| Task | Status |
|------|--------|
| Refactor PluginRegistry to facade | Pending |
| Update all imports | Pending |
| Verify backwards compatibility | Pending |
| Update tests | Pending |

---

## Migration Strategy

### Step 1: Create Module with Duplicate Code
```python
# registry/manifest_loader.py
class ManifestLoader:
    # Copy methods from PluginRegistry
```

### Step 2: Add Delegation in PluginRegistry
```python
# plugin_registry.py
class PluginRegistry:
    def __init__(self, ...):
        self._manifest_loader = ManifestLoader(...)

    def load_manifest(self, path):
        return self._manifest_loader.load_manifest(path)
```

### Step 3: Update External Imports
```python
# Before
from kernel.plugin_registry import PluginRegistry

# After (optional, both work)
from kernel.registry import ManifestLoader
```

### Step 4: Remove Duplicate Code
After all consumers updated, remove original methods from PluginRegistry.

---

## Acceptance Criteria

- [ ] Each module <500 LOC
- [ ] All existing tests pass
- [ ] No public API changes
- [ ] Import compatibility maintained
- [ ] Type hints preserved
- [ ] Documentation updated

---

## Risk Mitigation

1. **Backwards Compatibility**: Keep facade in plugin_registry.py
2. **Incremental Migration**: Extract one module at a time
3. **Test Coverage**: Parity tests verify behavior unchanged
4. **Rollback Plan**: Git revert if issues discovered

---

## Dependencies

- Phase 2 complete (parity tests available)
- CI pipeline passing
- No active feature branches modifying registry

---

## Next Steps

1. Extract `manifest_loader.py` (safest, most isolated)
2. Verify tests pass
3. Proceed with `spec_validator.py`
4. Continue until all modules extracted
5. Refactor PluginRegistry to pure facade

---

## Related Documents

- [ADR 0063: Plugin Microkernel](../../adr/0063-plugin-microkernel-for-compiler-validators-generators.md)
- [PLUGIN-DEPENDENCY-REVIEW.md](./PLUGIN-DEPENDENCY-REVIEW.md)
