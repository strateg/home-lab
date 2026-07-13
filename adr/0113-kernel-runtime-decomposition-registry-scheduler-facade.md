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
2. **Frozen facade contract:** constructor `(base_path)`; attributes `specs`
   (dict identity preserved — live references held by plugins and
   sub-components), `instances` (alias of the `PluginLoader` cache dict),
   `manifests`; methods `load_manifest`, `load_manifests_from_dir`,
   `load_plugin`, `validate_plugin_config`, `resolve_dependencies`,
   `get_execution_order`, `execute_plugin`, `execute_stage`,
   `get_load_errors` (append order observable), `get_all_results`,
   `get_execution_trace`, `reset_execution_trace`, `get_stats`,
   `get_kernel_info`; re-exports `PluginSpec`, `PluginManifest`,
   `SerializablePluginSpec`, `STAGE_ORDER`, exception types, kernel
   constants.
3. **Host-Protocol pattern:** scheduler module functions take a `host`
   parameter (the facade) and call bound methods, so registry-instance
   patch points remain stable for tests; `phase_executor` receives
   `has_real_subinterpreters` and `isolated_worker` explicitly per call
   instead of reading module globals.
4. **`legacy_executor` lifecycle:** quarantined compatibility code; it is
   deleted together with the `thread_legacy` execution mode (ADR 0097 D13),
   along with the `context_bridge` merge-back shim used only by that path.
   New code must use the envelope path
   (`envelope_pipeline` / `phase_executor`).
5. **Test tree mirrors the runtime layout:** unit tests live in
   `tests/kernel/registry/` and `tests/kernel/scheduler/` (plus
   `tests/kernel/test_plugin_results.py`); `tests/test_plugin_registry.py`
   remains a thin facade smoke on real manifests;
   `tests/runtime/scheduler/` targets the scheduler module APIs directly.
   No `__init__.py` exists under `tests/kernel` (a test package named
   `kernel` would shadow the real package). CI gates `test:plugin-api` and
   `test:plugin-contract` include `tests/kernel`.

## Consequences

What improves:

- 2383-LOC god-class becomes 15 focused modules plus an ~800-LOC facade;
  execution logic is reviewable and testable per concern.
- Dead duplicates removed (second `PluginManifest`, dead `ParallelExecutor`
  wavefront copy, duplicate plugin-loader construction, 8 obsolete facade
  delegates).
- D13 debt is physically isolated in two files with explicit deletion
  criteria instead of being interleaved with the primary path.

Trade-offs / risks:

- The facade keeps private host-surface methods (`_commit_envelope_result`,
  `_execute_phase_parallel`, context-bridge and preflight delegates) that
  scheduler modules call back into; they are internal wiring, not public
  API.
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
  3b3a77ab (S7), 401a38eb (S8), 1509b33b (S9)
- Amends: `adr/0097-subinterpreter-parallel-plugin-execution.md` (D10),
  `adr/0063-plugin-microkernel-for-compiler-validators-generators.md`
  (Implementation Checklist locations)
