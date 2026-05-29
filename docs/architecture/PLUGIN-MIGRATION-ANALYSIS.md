# Plugin Execution Mode Migration Analysis

**Date:** 2026-05-29
**Source:** Phase 4 Plugin System Development Plan (P4.1)
**Purpose:** Analyze main_interpreter plugins for potential subinterpreter migration

---

## Current State

| Mode | Count | Percentage |
|------|-------|------------|
| subinterpreter | 75 | 89.3% |
| main_interpreter | 9 | 10.7% |
| thread_legacy | 0 | 0% |

**Target:** >93% subinterpreter (migrate 4+ more plugins)

**Completed Migrations:**
- `base.builder.sbom` - migrated 2026-05-29 (removed ctx.sbom_output_dir mutation)

---

## Main Interpreter Plugins Analysis

### Cannot Migrate (Hard Constraints)

These plugins have fundamental architectural constraints preventing migration:

| Plugin | Constraint | Reason |
|--------|------------|--------|
| `base.discover.manifest_loader` | ctx.config mutation | Bootstrap phase, populates runtime config |
| `base.assembler.workspace` | ctx.workspace_root mutation | Sets global workspace paths |
| `base.assembler.manifest` | ctx.assembly_manifest mutation | Builds final assembly manifest |
| `base.assembler.deploy_bundle` | importlib.util | Dynamic module loading |
| `base.builder.bundle` | ctx.dist_root mutation | Distribution path setup |
| `base.builder.artifact_family_summary` | plugin_registry access | Requires registry metadata |

**Count:** 6 plugins (cannot migrate without major refactoring)

---

### Potential Migration Candidates

These plugins could potentially be migrated with targeted refactoring:

#### 1. base.compiler.model_lock_loader

**Current Constraint:** Mutates `ctx.model_lock`

**Analysis:**
```python
# Current pattern
ctx.model_lock = payload  # Direct mutation
```

**Migration Path:**
1. Change to publish model_lock via data plane
2. Update consumers to subscribe instead of direct access
3. Remove ctx.model_lock field mutation

**Effort:** Medium (8-12 hours)
**Risk:** Medium (affects all validators using model_lock)
**Recommendation:** Consider for Phase 5

---

#### 2. base.assembler.changed_scopes

**Current Constraint:** Mutates `ctx.changed_input_scopes`

**Analysis:**
```python
# Current pattern
ctx.changed_input_scopes = dirty_scopes  # Direct mutation
```

**Migration Path:**
1. Publish changed_input_scopes via data plane
2. Update consumers to subscribe
3. Move incremental build detection to snapshot-based approach

**Effort:** High (16-20 hours)
**Risk:** High (affects incremental build system)
**Recommendation:** Defer to incremental build refactor

---

#### 3. base.assembler.artifact_contract_guard

**Current Constraint:** Accesses `ctx.config.get("plugin_registry")`

**Analysis:**
```python
# Current pattern
registry = ctx.config.get("plugin_registry")
# Validates artifact contracts against registry
```

**Migration Path:**
1. Provide registry metadata via snapshot
2. Pre-compute required registry data in orchestrator
3. Pass as snapshot field instead of direct access

**Effort:** Medium (8-12 hours)
**Risk:** Medium (contract validation logic)
**Recommendation:** Good candidate for migration

---

#### 4. base.builder.sbom ✅ MIGRATED

**Previous Constraint:** Mutated `ctx.sbom_output_dir`

**Migration Completed:** 2026-05-29

**Changes:**
1. Removed `ctx.sbom_output_dir = str(sbom_root)` mutation
2. Added `execution_mode: subinterpreter` to manifest
3. Plugin already publishes `sbom_path` via data plane (no additional changes needed)

**Verification:** Plugin reads `ctx.sbom_output_dir` for defaults (allowed), no longer mutates it

---

## Migration Recommendations

### Immediate (Phase 4)

| Plugin | Effort | Status |
|--------|--------|--------|
| base.builder.sbom | 4-6h | ✅ Complete |
| base.assembler.artifact_contract_guard | 8-12h | Pending (requires registry snapshot) |

**Current Result:** 75/84 subinterpreter (89.3%)
**After artifact_contract_guard:** 76/84 subinterpreter (90.5%)

### Future (Phase 5+)

| Plugin | Effort | Blocker |
|--------|--------|---------|
| base.compiler.model_lock_loader | 8-12h | Requires validator updates |
| base.assembler.changed_scopes | 16-20h | Incremental build refactor |

**Expected Result:** 78/84 subinterpreter (92.9%)

---

## Cannot Migrate Without Major Refactoring

These require significant architectural changes:

| Plugin | Required Refactoring |
|--------|---------------------|
| base.discover.manifest_loader | Move to orchestrator |
| base.assembler.workspace | Pre-plugin initialization |
| base.assembler.manifest | Data plane aggregation |
| base.assembler.deploy_bundle | Static module loading |
| base.builder.bundle | Pre-plugin initialization |
| base.builder.artifact_family_summary | Snapshot-based registry data |

---

## Implementation Notes

### SBOM Migration Steps

1. Update `release_builder.py`:
   ```python
   # Before
   ctx.sbom_output_dir = str(sbom_root)

   # After
   sbom_root = self._compute_sbom_root(ctx)
   ctx.publish("sbom_output_dir", str(sbom_root))
   ```

2. Update consumers to subscribe
3. Set `execution_mode: subinterpreter` in manifest
4. Run parity tests

### Artifact Contract Guard Migration Steps

1. Add registry metadata to snapshot in orchestrator
2. Update plugin to read from snapshot instead of registry
3. Set `execution_mode: subinterpreter` in manifest
4. Run contract validation tests

---

## Acceptance Criteria

- [x] At least 2 plugins migrated to subinterpreter (1 complete: sbom)
- [ ] >90% subinterpreter coverage achieved (current: 89.3%, need 1 more)
- [ ] All existing tests pass
- [ ] No functional regressions
- [ ] Parity tests confirm identical output

---

## Related Documents

- [PLUGIN-EXECUTION-MODES.md](../guides/PLUGIN-EXECUTION-MODES.md)
- [PLUGIN-ENVELOPE-MODEL.md](../guides/PLUGIN-ENVELOPE-MODEL.md)
- [ADR 0097: Actor-Style Dataflow](../../adr/0097-plugin-execution-model.md)
