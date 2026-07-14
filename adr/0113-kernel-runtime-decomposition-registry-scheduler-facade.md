# ADR 0113: Kernel Runtime Decomposition into Registry, Scheduler, and Facade

- Status: Implemented
- Date: 2026-07-13
- Related: ADR-0063 (Plugin Microkernel), ADR-0080 (6-Stage Pipeline), ADR-0097 (Subinterpreter Execution, D10/D13), ADR-0099 (Runtime Test Architecture), ADR-0112 (Projection Domain Package Refactor)

## Context

`topology-tools/kernel/plugin_registry.py` had grown to 2383 LOC and owned
every runtime responsibility at once: manifest loading, spec/config
validation, dependency resolution, plugin instantiation, snapshot building,
envelope execution and commit, wavefront-parallel phase execution, stage
orchestration with preflight gates, the legacy thread execution path, and
the introspection API. ADR 0097 D10 prescribed a runtime decomposition but
described only a coarse 3-module layout (`plugin_registry` /
`pipeline_runtime` / `plugin_runner`) that no longer matched reality: partial
submodules under `kernel/registry/` and `kernel/scheduler/` existed with
duplicated or dead implementations, while the god-class remained the actual
execution path.

Constraints that shaped the decomposition:

- The facade public API is load-bearing: `compile-topology.py`, 4 plugins
  duck-typing `.specs` via `ctx.config["plugin_registry"]`,
  `kernel/__init__.py` re-exports, `validate_plugin_manifests.py`, and
  `multi_project_runner.py` all consume it.
- Subinterpreter workers import modules by name inside the isolate
  (`plugin_base`, `snapshot_builder`, `registry/plugin_loader`); those
  module names must not change (ADR 0097 D9).
- The `thread_legacy` execution mode (ADR 0097 D13) is compatibility-only
  and must remain quarantined, not redistributed into new code.
- Coverage gate `--cov=topology-tools/kernel --cov-fail-under=80` must hold
  at every step.

Executed via `docs/analysis/PLUGIN-REGISTRY-DECOMPOSITION-PLAN-2026-07-07.md`
(steps S1-S10, each independently green and committed separately).

## Decision

Decompose the kernel runtime into leaf specs, a static-loading registry
package, an execution scheduler package, and a thin facade:

```
kernel/
├── specs.py                      # leaf: PluginSpec, PluginManifest (single impl),
│                                 #   kernel constants; depends only on plugin_base
├── registry/                     # loading + static validation
│   ├── manifest_loader.py        # manifest parse, includes traversal, duplicate-ID
│   ├── spec_validator.py         # stage affinity, order ranges, entry families
│   ├── dependency_resolver.py    # dependency graph, cycles, execution order
│   ├── plugin_loader.py          # entry import + single plugin instance cache
│   ├── config_validator.py       # manifest config schema validation
│   └── envelope_validator.py     # envelope/payload schema-ref validation
├── scheduler/                    # execution
│   ├── execution_planner.py      # serialized specs, planning
│   ├── snapshot_builder.py       # PluginInputSnapshot construction
│   ├── parallel_executor.py      # subinterpreter worker + pool;
│   │                             #   compute_wavefronts = the only wavefront impl
│   ├── envelope_pipeline.py      # local envelope execution, commit, failure keys
│   ├── context_bridge.py         # pipeline_state mirror/sync + authoritative
│   │                             #   commit side effects (D13 shim, marked)
│   ├── phase_executor.py         # wavefront-parallel phase execution + routing
│   │                             #   per execution_mode (ADR 0097 PR2)
│   ├── stage_executor.py         # execute_stage: gates, fail-fast, FINALIZE,
│   │                             #   trace hooks, finally invariants
│   ├── preflight.py              # model-version + capability gates (E4010/11/12)
│   └── legacy_executor.py        # thread_legacy execute_plugin + data-bus contract
│                                 #   diagnostics (D13 quarantine)
├── pipeline_runtime.py           # PipelineState (envelope commit, invalidation)
├── plugin_runner.py              # run_plugin_once(snapshot, spec) -> envelope
└── plugin_registry.py            # facade (~800 LOC): frozen public API, wiring,
                                  #   introspection, re-exports
```

Rules:

1. **Dependency direction (invariant):**
   `plugin_base ← specs ← registry ← {pipeline_runtime, plugin_runner} ←
   scheduler ← plugin_registry (facade)`. `registry` never imports
   `scheduler` or `pipeline_runtime`; `scheduler` never imports the facade.
   *Verification:* currently manual (import review / grep of the package
   import graph; last audited 2026-07-13, clean). No automated layering
   gate exists yet; an `ast`-based layering test under `tests/kernel/` is
   the designated hardening path if drift is ever observed.
2. **Frozen facade contract:** constructor `(base_path)`; attributes `specs`
   (dict identity preserved — live references held by plugins and
   sub-components), `instances` (alias of the `PluginLoader` cache dict),
   `manifests`; methods `load_manifest`, `load_manifests_from_dir`,
   `load_plugin`, `validate_plugin_config`, `resolve_dependencies`,
   `get_execution_order`, `execute_plugin`, `execute_stage`,
   `get_load_errors` (append order observable — provided by `_load_errors`
   aliasing the `ManifestLoader` list objects; `manifests` uses the same
   alias mechanism), `get_all_results`, `get_execution_trace`,
   `reset_execution_trace`, `get_stats`, `get_kernel_info`.
   Re-exports (exhaustive; module-level names importable from the facade):
   - from `specs`: `PluginSpec`, `PluginManifest`, `KERNEL_VERSION`,
     `KERNEL_API_VERSION`, `SUPPORTED_API_VERSIONS`, `MODEL_VERSIONS`,
     `EXECUTION_PROFILES`, `DEFAULT_PLUGIN_TIMEOUT`;
   - from `registry`: `ManifestLoader`, `ManifestLoadError`,
     `SpecValidator`, `SpecValidationError`, `DependencyResolver`,
     `DependencyError`, `PluginCycleError`, `PluginLoader`,
     `PluginLoadError`, `ConfigValidator`, `ConfigValidationError`
     (alias `PluginConfigError`), `EnvelopeValidator`, plus constants
     `STAGE_ORDER`, `PHASE_ORDER`, `STAGE_ORDER_RANGES`,
     `KIND_STAGE_AFFINITY`, `KIND_ENTRY_FAMILY`, `ENTRY_FAMILIES`;
   - from `scheduler`: `ExecutionPlanner`, `SnapshotBuilder`,
     `SerializablePluginSpec`, `execute_plugin_isolated`,
     `get_parallel_executor`, `HAS_REAL_SUBINTERPRETERS`;
   - `plugin_base` types (`PluginBase`, `PluginContext`, `PluginResult`,
     `Stage`, `Phase`, ...) are additionally importable via the facade,
     but their canonical home is `kernel/plugin_base`.
   Audited load-bearing consumers (S9 audit, 2026-07-13):
   `kernel/__init__.py` re-exports `PluginCycleError` and `PluginManifest`
   *from the facade*; `tests/test_adr0097_execution_model.py` imports
   `SerializablePluginSpec` from the facade. Removing any listed name is a
   breaking change even when static analysis reports it unused.
3. **Host-Protocol pattern:** scheduler module functions take a `host`
   parameter (the facade) and call bound methods, so registry-instance
   patch points remain stable for tests; `phase_executor` receives
   `has_real_subinterpreters` and `isolated_worker` explicitly per call
   instead of reading module globals.
4. **`legacy_executor` lifecycle (exit protocol):** quarantined
   compatibility code. New code must use the envelope path
   (`envelope_pipeline` / `phase_executor`).
   - *Trigger:* the decision to remove the `thread_legacy` execution mode
     is owned by ADR 0097 D13; this ADR fixes only the mechanics of the
     removal, not its date.
   - *Deletion inventory (exhaustive as of 2026-07-13):*
     `scheduler/legacy_executor.py`; `scheduler/context_bridge.py`;
     the `context_bridge` exports in `scheduler/__init__.py`;
     the facade call sites into the quarantine (`plugin_registry.py`:
     context-bridge wrappers at ~354/358/362, the
     `attach_data_bus_contract_diagnostics` call, and the
     `execute_plugin` delegation to `legacy_executor.execute_plugin`);
     the `thread_legacy` routing branches (`phase_executor.py:227`,
     `stage_executor.py:354`); the `thread_legacy` literal in the
     `execution_mode` validation (`specs.py`).
   - *Dependent behavior:* data-bus contract diagnostics (W800x/E800x)
     are implemented inside `legacy_executor`; at removal they must be
     either ported to the envelope path or explicitly retired together
     with `tests/kernel/scheduler/test_data_bus_contracts.py` — silent
     loss of these diagnostics is not an accepted outcome.
   - *Verification:* full gate battery green with the quarantine files
     absent, and `grep -r "thread_legacy\|legacy_executor\|context_bridge"`
     over `topology-tools/kernel/` returns no runtime references.
5. **Test tree mirrors the runtime layout:** unit tests live in
   `tests/kernel/registry/` and `tests/kernel/scheduler/` (plus
   `tests/kernel/test_plugin_results.py`); `tests/test_plugin_registry.py`
   remains a thin facade smoke on real manifests;
   `tests/runtime/scheduler/` targets the scheduler module APIs directly.
   No `__init__.py` exists under `tests/kernel` (a test package named
   `kernel` would shadow the real package). CI gates `test:plugin-api` and
   `test:plugin-contract` include `tests/kernel`.
   *Relation to ADR 0099:* the layers under `tests/runtime/*`
   (worker_runner, pipeline_state, scheduler, parity) remain the
   execution-model contract tests defined by ADR 0099; `tests/kernel/*`
   adds package-mirroring unit tests introduced by this ADR. The two
   trees are complementary — a scheduler concern may legitimately have
   both a contract test (0099 layer) and a unit test (this tree). This
   ADR does not amend ADR 0099.
6. **Trace ownership:** execution-trace state and logic (`_trace_event`,
   `_trace_lock`, `get_execution_trace`, `reset_execution_trace`) remain
   facade-owned introspection responsibilities. The separate `trace.py`
   module (`ExecutionTracer`) foreseen by the plan (§3) was deliberately
   not created: the trace is part of the frozen introspection API, has no
   consumers outside the facade, and extracting it would add a module
   boundary without decoupling anything.

## Alternatives Considered

1. **Keep the god-class, add tests only.** Rejected: 2383 LOC with ten
   interleaved responsibilities defeats per-concern review; coverage
   alone does not make the D13 quarantine boundary physical.
2. **No facade — migrate all consumers to package imports.** Rejected:
   the facade API is load-bearing for `compile-topology.py`, 4 plugins
   duck-typing `.specs`, `kernel/__init__.py`, `validate_plugin_manifests.py`
   and `multi_project_runner.py`; a big-bang consumer migration violates
   the step-by-step green-gate constraint and buys nothing the frozen
   facade does not already provide.
3. **Keep ADR 0097 D10's 3-module layout as-is.** Rejected: it no longer
   matched reality (partial submodules already existed with duplicated or
   dead implementations) and gives no home to the registry/scheduler
   split or the D13 quarantine.
4. **Extract `trace.py` per the plan §3.** Rejected — see Rule 6.

## Acceptance Criteria

- AC1: Dependency direction of Rule 1 holds across `kernel/`
  (verified manually by import audit; automated layering test is the
  designated hardening path — see Rule 1).
- AC2: Frozen facade surface of Rule 2 is exercised by
  `tests/test_plugin_registry.py` (facade smoke) and the
  `test:plugin-contract` gate; audited load-bearing re-exports resolve.
- AC3: Coverage gate `--cov=topology-tools/kernel --cov-fail-under=80`
  passes (`test:plugin-api`).
- AC4: `tests/kernel/` mirrors the package layout and contains no
  `__init__.py`; both CI gates include `tests/kernel` (Rule 5).
- AC5: D13 quarantine remains exactly two scheduler files
  (`legacy_executor.py`, `context_bridge.py`) plus the facade call sites
  enumerated in Rule 4; no new code imports the quarantine.

## Consequences

What improves:

- The 2383-LOC god-class becomes 15 extracted modules (6 in `registry/`,
  9 in `scheduler/`) plus the new leaf `specs.py`, alongside the
  pre-existing `pipeline_runtime.py` and `plugin_runner.py`, fronted by
  an ~800-LOC facade; execution logic is reviewable and testable per
  concern.
- Dead duplicates removed (second `PluginManifest`, dead `ParallelExecutor`
  wavefront copy, duplicate plugin-loader construction, 8 obsolete facade
  delegates).
- D13 debt is physically isolated in two files with an explicit exit
  protocol (Rule 4) instead of being interleaved with the primary path.

Trade-offs / risks:

- The facade keeps private host-surface methods (`_commit_envelope_result`,
  `_execute_phase_parallel`, context-bridge and preflight delegates) that
  scheduler modules call back into; they are internal wiring, not public
  API. This host surface — together with facade-owned trace logic
  (Rule 6) — is why the facade landed at ~800 LOC instead of the plan's
  §3 target of ~350–420 LOC; the delta is accepted deliberately in favor
  of stable patch points and the frozen API.
- `framework.lock` integrity changes with kernel edits and must be
  refreshed (CORE-005).
- Historical documents (ADR 0063/0097 analysis trees, older plans)
  reference the monolithic layout; they are records and are intentionally
  not rewritten. This ADR supersedes the module-layout description of
  ADR 0097 D10 (layout only, not the execution-model decisions).

Migration impact:

- No topology, manifest, or generated-artifact change; behavior preserved
  step-by-step (verbatim moves, parity tests for wavefronts, pre-fix
  invariant tests for stage execution).

## References

- Plan: `docs/analysis/PLUGIN-REGISTRY-DECOMPOSITION-PLAN-2026-07-07.md`
- Commits: 7000115c (S1-S3), fc798774 (S4), d4836ae9 (S5), ef79542e (S6),
  3b3a77ab (S7), 401a38eb (S8), 1509b33b (S9), cbb09720 (S10, this ADR
  and cross-references)
- Amends: `adr/0097-subinterpreter-parallel-plugin-execution.md` (D10),
  `adr/0063-plugin-microkernel-for-compiler-validators-generators.md`
  (Implementation Checklist locations)
