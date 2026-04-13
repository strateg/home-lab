# ADR 0080 Remediation Plan

**Date:** 2026-04-13
**ADR:** 0080 - Unified Build Pipeline, Stage-Phase Lifecycle, and Contractual Plugin Data Bus
**Current Status**: Partially Implemented (mislabeled as "Accepted")
**Remediation Goal**: Complete implementation of 6-stage + universal phase model

---

## Executive Summary

ADR 0080 defines a comprehensive 6-stage pipeline (`discover -> compile -> validate -> generate -> assemble -> build`) with universal phase model (`init -> pre -> run -> post -> verify -> finalize`). However, current runtime only implements 3 stages (`compile`, `validate`, `generate`) with DAG/order-based scheduling, **not phase-aware execution**.

This plan outlines 6 remediation waves to complete the implementation.

---

## Gap Summary (Cross-Reference: ADR 0080 GAP-ANALYSIS.md)

| Gap ID | Component | Status | Blocks |
|--------|-----------|--------|--------|
| **G1** | Discover stage plugins | Not implemented | Plugin-owned discovery lifecycle |
| **G2** | PluginContext extensions | Missing fields | Assemble/build plugin implementation |
| **G3** | Phase-aware executor | Not implemented | Universal phase model |
| **G4** | `when` predicate evaluation | Declarative only | Smart plugin model |
| **G5** | Diagnostic code ranges | Not allocated | Typed diagnostics for new stages |
| **G6** | `base.generator.artifact_manifest` | Not implemented | Generate->assemble contract |
| **G19-G24** | Parallel execution safety | Race conditions | Production reliability |

**Total Implementation Debt**: 20+ components across 6 waves

---

## Remediation Waves

### Wave 1: Phase-Aware Executor (CRITICAL)

**Goal**: Implement runtime execution of universal phase lifecycle

**Scope**:
1. Extend `compiler_runtime.py` to execute phases within each stage
2. Modify plugin execution order: stage → phase → DAG → order
3. Ensure `finalize` phase runs even on stage failure
4. Update `PluginSpec` to include actual `phase` assignment (not just schema)
5. Add phase transition logging and diagnostics

**Deliverables**:
- [ ] `topology-tools/kernel/phase_executor.py` - Phase lifecycle runtime
- [ ] `topology-tools/compiler_runtime.py` - Integration with stage executor
- [ ] `tests/unit/test_phase_executor.py` - Unit tests for phase transitions
- [ ] `tests/integration/test_phase_lifecycle.py` - Integration tests with real plugins

**Acceptance Criteria**:
- Plugin manifest `phase: run` is respected during execution
- Plugins in `init` phase run before `run` phase
- `finalize` phase runs even if `run` phase fails
- Phase transition logged in diagnostics

**Estimated Effort**: 3-5 days

**Risks**:
- Backward compatibility with plugins not declaring `phase` (default to `run`)
- Performance impact of additional executor layer

**Dependencies**: None (can start immediately)

---

### Wave 2: PluginContext Extensions for Assemble/Build (HIGH)

**Goal**: Extend `PluginContext` to support assemble and build stage plugins

**Scope**:
1. Add `workspace_root: Path` - `.work/native/` root for assemble plugins
2. Add `dist_root: Path` - `dist/` root for build plugins
3. Add `assembly_manifest: dict[str, Any]` - output from `assemble.finalize`
4. Add `signing_backend: str | None` - for build stage integrity checks
5. Add `release_tag: str | None` - for build stage versioning
6. Add `sbom_output_dir: Path | None` - SBOM generation path

**Deliverables**:
- [ ] `topology-tools/kernel/plugin_base.py` - PluginContext field additions
- [ ] `topology-tools/compiler_runtime.py` - Context population during assemble/build
- [ ] `tests/unit/test_plugin_context.py` - Context field validation
- [ ] Migration guide for existing plugins (none currently use these fields)

**Acceptance Criteria**:
- `ctx.workspace_root` available in assemble plugins
- `ctx.dist_root` available in build plugins
- `ctx.assembly_manifest` populated by assemble.finalize, consumed by build.init
- All fields documented in plugin development guide

**Estimated Effort**: 2-3 days

**Risks**:
- Context object growing too large (consider splitting into stage-specific contexts)

**Dependencies**: None (can run parallel with Wave 1)

---

### Wave 3: Discover Stage Plugin Implementation (MEDIUM)

**Goal**: Move procedural discovery logic into plugin-based lifecycle

**Scope**:
1. Create `base.discoverer.framework_manifest` - load framework context
2. Create `base.discoverer.project_manifest` - load project manifest
3. Create `base.discoverer.plugin_manifests` - discover and validate plugin manifests
4. Create `base.discoverer.capability_preflight` - capability compatibility checks
5. Publish discovery outputs to data bus for compile stage consumption
6. Remove procedural `discover_plugin_manifests()` function

**Deliverables**:
- [ ] `topology-tools/plugins/discoverers/framework_manifest.py`
- [ ] `topology-tools/plugins/discoverers/project_manifest.py`
- [ ] `topology-tools/plugins/discoverers/plugin_manifests.py`
- [ ] `topology-tools/plugins/discoverers/capability_preflight.py`
- [ ] `topology-tools/plugins/plugins.yaml` - discover stage manifest entries
- [ ] `tests/plugin_integration/test_discover_stage.py`

**Acceptance Criteria**:
- `discover` stage executes before `compile` stage
- Framework/project manifests loaded via plugins, not procedural code
- Plugin discovery output published to data bus
- Capability preflight failures block pipeline startup

**Estimated Effort**: 4-6 days

**Risks**:
- Circular dependency: discovery needs base manifest to find discoverers
- Bootstrap problem requires base manifest to be seeded outside plugin lifecycle (acceptable)

**Dependencies**: Wave 1 (phase executor) must be complete

---

### Wave 4: Parallel Execution Safety (CRITICAL)

**Goal**: Fix race conditions in parallel plugin execution

**Scope**:
1. Add thread-safe data bus with per-invocation isolation
2. Replace shared `_published_data` dict with `threading.Lock` or immutable structure
3. Fix plugin instance cache TOCTOU window in `plugin_registry.py`
4. Isolate `_current_plugin_id` and `_allowed_dependencies` per worker thread
5. Ensure diagnostic ordering is deterministic (sort by plugin order after collection)
6. Add parallel execution stress tests

**Deliverables**:
- [ ] `topology-tools/kernel/thread_safe_data_bus.py` - Thread-safe publish/subscribe
- [ ] `topology-tools/kernel/plugin_registry.py` - Fix instance cache race
- [ ] `topology-tools/compiler_runtime.py` - Per-thread plugin identity isolation
- [ ] `tests/stress/test_parallel_execution.py` - Stress test with 100+ concurrent plugins

**Acceptance Criteria**:
- No race conditions detected in parallel stress test (1000 runs)
- Diagnostic output ordering is deterministic
- Plugin instance cache has no TOCTOU window
- Published data isolated per plugin execution context

**Estimated Effort**: 5-7 days

**Risks**:
- Performance degradation from locking overhead
- Backward compatibility if plugins rely on shared state (should not, but verify)

**Dependencies**: None (critical path, start after Wave 1)

---

### Wave 5: Smart Plugin Predicates (MEDIUM)

**Goal**: Implement runtime evaluation of `when` predicates

**Scope**:
1. Parse `when.profiles` and match against active profiles
2. Parse `when.pipeline_modes` and match against runtime mode
3. Parse `when.capabilities` and match against capability catalog
4. Parse `when.changed_input_scopes` and match against changed files (future)
5. Skip plugin execution if predicate evaluates to false
6. Log predicate evaluation in diagnostics

**Deliverables**:
- [ ] `topology-tools/kernel/plugin_predicates.py` - Predicate evaluation logic
- [ ] `topology-tools/compiler_runtime.py` - Integrate predicate check before execution
- [ ] `tests/unit/test_plugin_predicates.py` - Predicate parsing and evaluation
- [ ] `tests/integration/test_conditional_plugins.py` - End-to-end predicate tests

**Acceptance Criteria**:
- Plugin with `when.profiles: [dev]` skipped when `--profile prod`
- Plugin with `when.capabilities: [wireguard]` skipped if capability not in catalog
- Skipped plugins logged with reason in diagnostics
- Predicate evaluation adds <1% overhead to execution time

**Estimated Effort**: 3-4 days

**Risks**:
- Complex predicate logic (AND/OR combinations) requires careful design
- Performance impact if predicates evaluated inefficiently

**Dependencies**: Wave 1 (phase executor) recommended but not strictly required

---

### Wave 6: Finalization (LOW)

**Goal**: Complete remaining ADR 0080 components

**Scope**:
1. Allocate diagnostic code ranges for discover/assemble/build (E80xx)
2. Implement `base.generator.artifact_manifest` plugin
3. Update ADR 0080 status to "Implemented"
4. Update plugin order range documentation for all 6 stages
5. Remove legacy TODOs and ADR 0080 GAP-ANALYSIS.md warnings

**Deliverables**:
- [ ] `topology-tools/data/error-catalog.yaml` - E80xx range allocation
- [ ] `topology-tools/plugins/generators/artifact_manifest.py`
- [ ] `adr/0080-unified-build-pipeline-stage-phase-and-plugin-data-bus.md` - Status update
- [ ] `docs/plugin-development/STAGE-ORDER-RANGES.md` - Order range reference

**Acceptance Criteria**:
- All 6 stages have documented order ranges
- Artifact manifest plugin generates `generated/home-lab/ARTIFACT-MANIFEST.json`
- ADR 0080 marked "Implemented" with completion date
- No open TODOs referencing ADR 0080 gaps

**Estimated Effort**: 2-3 days

**Risks**: None (cleanup wave)

**Dependencies**: Waves 1-5 complete

---

## Implementation Roadmap

### Phase 1: Critical Safety (Weeks 1-2)
- **Wave 1**: Phase-aware executor (3-5 days)
- **Wave 4**: Parallel execution safety (5-7 days)
- **Validation**: Integration tests, parallel stress tests

### Phase 2: Stage Expansion (Weeks 3-4)
- **Wave 2**: PluginContext extensions (2-3 days)
- **Wave 3**: Discover stage plugins (4-6 days)
- **Validation**: Plugin contract tests, discovery integration tests

### Phase 3: Smart Features (Week 5)
- **Wave 5**: Smart plugin predicates (3-4 days)
- **Validation**: Conditional execution tests

### Phase 4: Completion (Week 6)
- **Wave 6**: Finalization (2-3 days)
- **Documentation**: Update guides, migration notes
- **Validation**: Full CI suite, acceptance TUC

**Total Timeline**: 6 weeks (30 working days)

---

## Validation Strategy

### Per-Wave Validation
- Unit tests for new components (>80% coverage)
- Integration tests with real plugins
- Plugin contract validation (manifest compliance)
- Regression tests for existing functionality

### Integration Validation
- Full compile-topology run with all 6 stages
- Parallel execution stress test (1000 iterations)
- Golden snapshot comparison for generated artifacts
- Acceptance TUC for end-to-end pipeline

### Production Readiness Gates
1. All Wave 1-6 acceptance criteria met
2. CI passes on main branch
3. No open ADR 0080 TODOs in codebase
4. Plugin development guide updated
5. Operator runbook includes new stages

---

## Rollback Plan

If remediation causes breaking changes:

1. **Feature Flag**: Add `V5_ENABLE_PHASE_LIFECYCLE=false` environment variable
2. **Legacy Mode**: Fall back to DAG/order execution if flag disabled
3. **Gradual Rollout**: Enable phase lifecycle only for new plugins initially
4. **Monitoring**: Track execution time, diagnostic volume, failure rates
5. **Cutover Gate**: Require 2 weeks of stable CI before removing legacy mode

---

## Risk Mitigation

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Backward compatibility breakage | Medium | High | Feature flag, legacy mode |
| Performance regression | Low | Medium | Benchmark before/after, optimize hot paths |
| Parallel race conditions persist | Low | Critical | Stress testing, thread sanitizer |
| Phase executor complexity | Medium | Medium | Incremental rollout, extensive testing |
| Timeline slippage | Medium | Low | Prioritize Wave 1+4, defer Wave 5 if needed |

---

## Dependencies and Constraints

### Hard Dependencies
- Wave 3 requires Wave 1 (discover stage needs phase executor)
- Wave 6 requires Waves 1-5 (finalization)

### Optional Dependencies
- Wave 5 can run independently (nice-to-have, not critical)
- Wave 2 can run parallel with Wave 1

### External Constraints
- Must maintain backward compatibility with existing 47 plugins
- Must not break current SOHO deployment workflows
- Must preserve golden snapshot parity (generator outputs)

---

## Success Metrics

### Technical Metrics
- All 6 stages executable in runtime
- Universal phase model operational
- Parallel execution deterministic (1000+ iterations)
- Zero race condition detections in stress tests
- Plugin contract validation passing for all manifests

### Operational Metrics
- CI execution time < 10min (no regression)
- Plugin development guide complete
- Operator runbook updated
- ADR 0080 status updated to "Implemented"

### Quality Metrics
- Test coverage >80% for new components
- Zero ADR 0080-related TODOs in codebase
- Acceptance TUC passing for full pipeline

---

## Next Actions

1. **Immediate (Week 1)**:
   - Create `adr/0080-remediation/WAVE-1-PHASE-EXECUTOR.md` with detailed implementation spec
   - Create `adr/0080-remediation/WAVE-4-PARALLEL-SAFETY.md` with race condition fixes
   - Update ADR 0080 status from "Accepted" to "Partially Implemented"
   - Add remediation tracking to project board

2. **Short-term (Week 2)**:
   - Begin Wave 1 implementation (phase executor)
   - Set up parallel execution stress test harness
   - Document phase lifecycle in plugin development guide

3. **Medium-term (Weeks 3-6)**:
   - Complete Waves 2-6 according to roadmap
   - Integration testing with SOHO deployment
   - Prepare cutover checklist

---

**Remediation Owner**: TBD (assign to lead developer)
**Review Cadence**: Weekly status updates
**Completion Target**: 6 weeks from start date
