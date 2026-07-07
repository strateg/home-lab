# Plugin Registry Decomposition Plan (H2.1 / N1)

**Date:** 2026-07-07
**Status:** Approved (execution started 2026-07-07)
**Scope:** `topology-tools/kernel/plugin_registry.py` (2383 LOC) decomposition into `kernel/registry/` + `kernel/scheduler/` with frozen facade API
**Source:** tech-lead-architect architectural review; implements item H2.1 of [ARCHITECTURE-IMPROVEMENT-PLAN-2026-07-07.md](ARCHITECTURE-IMPROVEMENT-PLAN-2026-07-07.md) (finding N1)
**Related ADR:** 0063 (plugin microkernel), 0097 (subinterpreter execution, D10/D13), 0080 (6-stage pipeline)

---

## 1. Diagnosis

`plugin_registry.py` is a **half-decomposed** god class: ~40% of methods are thin
delegates into `kernel/registry/` and `kernel/scheduler/`, but all *execution*
logic (~1300 LOC: phase/stage orchestration, envelope commit, legacy thread
path, preflight gates) remains in the monolith.

Key facts:

1. **ADR 0097 D10 violation.** D10 normatively requires `plugin_registry.py`
   to contain only manifest loading, spec validation, dependency graph, and
   entry loading. The current state violates an accepted ADR; this refactoring
   is *completion* of D10, not new architecture.
2. **Dead duplicates:** `ParallelExecutor` class (wavefronts re-implemented
   inline in `_execute_phase_parallel`), `ManifestLoader.load_manifest`,
   `PluginLoader.load` + instance cache, and a duplicate `PluginManifest`
   dataclass that shadows the imported one.
3. **Dependency inversion:** all submodules type `PluginSpec` via
   `TYPE_CHECKING` import *from the facade* — packages depend on the monolith
   for a data type. This blocks clean decomposition and must be fixed first.
4. **Tests are facade-clean:** `tests/test_plugin_registry.py` (2494 LOC,
   53 tests) touches no private methods — it is already a facade contract
   test. Private access lives only in `tests/runtime/scheduler/` +
   `tests/test_adr0097_execution_model.py` (4 methods:
   `_execute_phase_parallel`, `_get_parallel_executor`,
   `_commit_envelope_result`, `_apply_authoritative_commit_side_effects`).

### 1.1 Responsibility cluster map (line refs at analysis time)

| # | Cluster | Lines | LOC | Status |
|---|---------|-------|-----|--------|
| — | Imports + BC re-exports | 1–120 | 120 | facade concern |
| — | `PluginSpec` dataclass | 122–317 | 196 | leaf type (misplaced) |
| — | `PluginManifest` dataclass | 320–351 | 32 | **duplicate** of `registry/manifest_loader.py:38` |
| 1 | Init + delegate wiring | 376–403 | 28 | facade concern |
| 2 | `_get_parallel_executor` | 404–416 | 13 | duplicates `ParallelExecutor.get_executor` |
| 3 | Trace `_trace_event` + lock | 418–450 | 33 | own |
| 4 | Manifest loading (`load_manifest` :472, includes, duplicate-ID) | 452–525 | 74 | partially own; `ManifestLoader.load_manifest` unused |
| 5 | Spec-validation delegates | 527–565 | 39 | thin delegates → `SpecValidator` |
| 6 | Planning delegates | 567–577 | 11 | thin delegates → `ExecutionPlanner` |
| 7 | Snapshot + migration metadata | 579–639 | 61 | delegate + own metadata injection |
| 8 | PipelineState↔Context bridge | 641–716 | 76 | own; D13 compatibility shim |
| 9 | Envelope execution + commit | 718–967 | 250 | own (D2 flow core) |
| 10 | Schema-ref payload validation + data-bus contract diag | 969–1246 | 278 | own; mostly legacy-path |
| 11 | Public config/deps/planning API | 1248–1306 | 59 | delegates with error conversion |
| 12 | `_execute_phase_parallel` | 1308–1641 | 334 | own; inline wavefronts duplicate `compute_wavefronts` |
| 13 | `load_plugin` + entry-point delegate | 1643–1688 | 46 | own instance cache duplicates `PluginLoader` |
| 14 | `execute_plugin` (legacy thread path) | 1690–1883 | 194 | own; D13 compatibility-only |
| 15 | `execute_stage` | 1885–2173 | 289 | own; FINALIZE/fail-fast/invalidation invariants |
| 16 | Model-version validation | 2175–2282 | 108 | own (E4011/E4012) |
| 17 | Capability validation | 2284–2331 | 48 | own (E4010) |
| 18 | Introspection API | 2333–2383 | 51 | facade concern |

Non-delegated logic ≈ 1640 LOC; execution/commit (8, 9, 12, 14, 15) ≈ 1143 LOC.

### 1.2 Existing package inventory

`kernel/registry/` (1082 LOC): `manifest_loader.py` (190, partially dead),
`spec_validator.py` (225, fully delegated), `dependency_resolver.py` (224,
delegated), `plugin_loader.py` (169, mostly dead duplicate),
`config_validator.py` (204, delegated), `envelope_validator.py` (189,
delegated).

`kernel/scheduler/` (710 LOC): `execution_planner.py` (215, delegated),
`parallel_executor.py` (254 — only `execute_plugin_isolated` used; the
`ParallelExecutor` class is dead), `snapshot_builder.py` (206, delegated).

Adjacent: `pipeline_runtime.py` (102, `PipelineState`), `plugin_runner.py`
(71, `run_plugin_once`).

---

## 2. Frozen public API (contract)

Production callers: `compile-topology.py` (V5Compiler), 4 plugins duck-typing
`.specs` via `ctx.config["plugin_registry"]`, `kernel/__init__.py` re-exports,
`scripts/validation/validate_plugin_manifests.py`, `multi_project_runner.py`.

Frozen surface:

- Constructor `(base_path)`; attributes `specs` (**dict identity preserved** —
  live references held by sub-components and plugins), `instances`,
  `manifests`.
- Methods: `load_manifest`, `load_manifests_from_dir`, `load_plugin`,
  `validate_plugin_config`, `resolve_dependencies`, `get_execution_order`,
  `execute_plugin`, `execute_stage`, `get_load_errors` (**append order is
  observable** — `compile-topology.py` reads slices), `get_all_results`,
  `get_execution_trace`, `reset_execution_trace`, `get_stats`,
  `get_kernel_info`.
- Re-exports from `kernel.plugin_registry`: `PluginSpec`, `PluginManifest`,
  `SerializablePluginSpec`, `STAGE_ORDER`, exception types, kernel constants.

---

## 3. Target architecture

```
kernel/
├── specs.py                      # NEW ~380 LOC: PluginSpec, PluginManifest (single),
│                                 #   kernel constants. Leaf: depends only on plugin_base
├── registry/                     # loading + static validation (does NOT depend on scheduler)
│   ├── manifest_loader.py        # + includes traversal, duplicate-ID detection (~280)
│   ├── spec_validator.py         # unchanged (225)
│   ├── dependency_resolver.py    # unchanged (224)
│   ├── plugin_loader.py          # single instance cache + kind checks (~200)
│   ├── config_validator.py       # unchanged (204)
│   └── envelope_validator.py     # + schema-ref payload / required-consumes validation (~380)
├── scheduler/                    # execution (depends on registry, pipeline_runtime, plugin_runner)
│   ├── execution_planner.py      # unchanged (215)
│   ├── snapshot_builder.py       # unchanged (206)
│   ├── parallel_executor.py      # worker + pool; absorbs _get_parallel_executor;
│   │                             #   compute_wavefronts = the ONLY wavefront impl (~300)
│   ├── envelope_pipeline.py      # NEW ~330: envelope exec local, commit, failure keys, status
│   ├── context_bridge.py         # NEW ~100: pipeline_state mirror/sync + authoritative
│   │                             #   commit side effects (D13 shim, marked)
│   ├── phase_executor.py         # NEW ~300: _execute_phase_parallel on compute_wavefronts
│   ├── stage_executor.py         # NEW ~300: execute_stage + failure ctx + trace hooks
│   ├── preflight.py              # NEW ~180: model-version + capability gates (E4010/11/12)
│   ├── legacy_executor.py        # NEW ~480: execute_plugin thread path + data-bus contract
│   │                             #   diagnostics (D13 quarantine, delete with thread_legacy)
│   └── trace.py                  # NEW ~60: ExecutionTracer
├── pipeline_runtime.py           # unchanged
├── plugin_runner.py              # unchanged
└── plugin_registry.py            # FACADE ~350–420 LOC
```

Dependency direction (invariant):

```
plugin_base ← specs ← registry ← {pipeline_runtime, plugin_runner} ← scheduler ← plugin_registry (facade)
```

- `registry` never imports `scheduler`/`pipeline_runtime`.
- `scheduler` never imports the facade.
- Subinterpreter worker (`execute_plugin_isolated`) already imports only
  `plugin_base`, `snapshot_builder`, `plugin_loader` — unaffected by the
  `PluginSpec` move.
- Facade temporarily keeps 4 private one-line delegates used by runtime tests;
  removed in S9 after tests migrate to the new module APIs.

---

## 4. Migration steps (each independently green)

Gate battery per step: `task test:plugin-api` (cov-fail-under=80) →
`task test:plugin-contract` → `tests/runtime/` → compile smoke (clean
`generated/` diff) → `validate-v5` lane.

| Step | Content | Key risk control |
|------|---------|------------------|
| S1 | `kernel/specs.py` leaf types; submodule `TYPE_CHECKING` imports → real imports from `kernel.specs`; delete duplicate `PluginManifest` | diff both `PluginManifest` impls before deletion |
| S2 | includes traversal + duplicate-ID from `load_manifest` → `ManifestLoader` (merge with dead impl); `_load_errors` moves to loader | preserve append-only error order (slice reads) |
| S3 | schema-ref payload validation (cluster 10 minus data-bus diag) → `registry/envelope_validator.py` | — |
| S4 | envelope pipeline + context bridge → `scheduler/envelope_pipeline.py` + `scheduler/context_bridge.py`; facade keeps private delegates | runtime tests stay green unmodified |
| S5 | `_execute_phase_parallel` → `scheduler/phase_executor.py`; inline wavefronts replaced by `ParallelExecutor.compute_wavefronts` | **parity test first**: inline vs `compute_wavefronts` on graph fixtures incl. tie-breaks (ADR 0063 §6) |
| S6 | `execute_stage` → `scheduler/stage_executor.py`; model-version + capability gates → `scheduler/preflight.py` | pre-fix invariant tests: FINALIZE-on-fail-fast, invalidation in `finally`, `stage_failure_context` |
| S7 | `execute_plugin` + data-bus contract diagnostics → `scheduler/legacy_executor.py` (D13 quarantine docstring) | no behavior change; compatibility-only |
| S8 | `load_plugin` delegates to `PluginLoader.load`; single instance cache (facade attr = view on loader) | `instances` attribute identity/behavior preserved |
| S9 | split `tests/test_plugin_registry.py` → `tests/kernel/registry/` + `tests/kernel/scheduler/` (calls stay facade-level); keep thin facade smoke; migrate `tests/runtime/scheduler/` off facade privates; drop private delegates; update `taskfiles/test.yml` paths | coverage delta per step; new-module unit tests |
| S10 | New ADR (kernel runtime decomposition) + amendments ADR 0097 D10 (3-module → 5-component) and ADR 0063 checklist; `adr/REGISTER.md` | `task validate:adr-consistency` |

Order: S1 → S2/S3 → S4 → S5/S6 → S7/S8 → S9 → S10.
`tests/test_plugin_registry.py` is **not modified** during S1–S8 — it is the
primary regression detector.

---

## 5. Risks

| Risk | Mitigation |
|------|------------|
| Coverage gate 80% (`--cov=topology-tools/kernel`) shifts with new modules/delegates | measure per step; deleting dead duplicates (S2/S5/S8) raises the ratio; unit tests in S9 |
| Subinterpreter workers import modules by name inside isolate | do not rename `plugin_base`, `snapshot_builder`, `registry/plugin_loader`; gate via `tests/runtime/scheduler/test_worker_failure_isolation.py` |
| Inline wavefronts vs `compute_wavefronts` divergence | parity test before replacement (S5) |
| `execute_stage` hidden invariants (FINALIZE on fail-fast, `finally` invalidation, I4013 skip diag) | explicit tests before S6 |
| Live registry object in `ctx.config["plugin_registry"]` (4 plugins read `.specs`) | facade keeps `specs` as the same dict object; identity contract test |
| Scope creep into D13 shims | `context_bridge`/`legacy_executor` moved as-is, marked; removal is separate work after `thread_legacy` retirement |

---

## 6. ADR scope (S10)

- **New ADR** `kernel-runtime-decomposition-registry-scheduler-facade`:
  module map (§3), dependency direction, frozen facade contract,
  `legacy_executor` lifecycle. Register in `adr/REGISTER.md`.
- **ADR 0097 amendment:** rewrite D10 from 3-module to 5-component layout
  (registry package, scheduler package, `pipeline_runtime`, `plugin_runner`,
  facade); note `snapshot_builder` lives in scheduler.
- **ADR 0063 amendment:** Implementation Checklist location update
  (`PluginSpec`/`PluginManifest` → `kernel/specs.py`); normative sections
  (§1, §4A, §6, §8) unchanged — refactoring conforms.
