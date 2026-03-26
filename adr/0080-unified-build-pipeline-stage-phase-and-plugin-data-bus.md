# ADR 0080: Unified Build Pipeline, Stage-Phase Lifecycle, and Contractual Plugin Data Bus

- Status: Accepted
- Date: 2026-03-26
- Depends on: ADR 0005, ADR 0027, ADR 0028, ADR 0050, ADR 0051, ADR 0052, ADR 0055, ADR 0056, ADR 0063, ADR 0065, ADR 0066, ADR 0069, ADR 0071, ADR 0072, ADR 0074, ADR 0075, ADR 0076, ADR 0078, ADR 0079

## Context

Early and mid-stack ADRs already define hard constraints:

1. Determinism and quality gates are non-negotiable (ADR 0005, ADR 0027, ADR 0074).
2. Stable tool boundaries and entrypoints are required (ADR 0028, ADR 0069).
3. Generated baseline must be separated from assembled execution roots (ADR 0050, ADR 0052, ADR 0056).
4. Manual overrides and local secrets are separate layers (ADR 0051, ADR 0055, ADR 0072).
5. Runtime is plugin-first and already exposes publish/subscribe (ADR 0063, ADR 0065, ADR 0069).
6. `instances_root` is data-only (ADR 0071), while plugin ownership is layered (ADR 0078).
7. Framework/project distribution verification is a build lifecycle concern (ADR 0075, ADR 0076).

Current runtime (AS-IS baseline confirmed on 2026-03-26):

1. Runtime stages in code are `compile`, `validate`, `generate`.
2. No `Phase` concept in runtime execution (`stage -> DAG/order` only).
3. `publish/subscribe` is operational but key contracts are implicit.
4. Base manifest is loaded procedurally; module manifests are loaded by `discover.init` plugin.
5. Discovered inventory is 57 plugins in 7 manifests (`compile`: 7, `validate`: 40, `generate`: 10).
6. Base manifest currently registers 48 plugins (`compile`: 7, `validate`: 36, `generate`: 5).
7. Schema/runtime are not aligned yet: schema accepts `build` stage and `phase=finished`, while runtime `Stage` supports only `compile|validate|generate`.

## Gap Analysis (AS-IS -> Target)

| Gap ID | Target contract | Current state (verified) | Impact | Priority |
|---|---|---|---|---|
| G1 | `discover` stage is real and plugin-owned | Stage exists in target model but has no plugin assignment in ADR section 4 | runtime would keep procedural discovery path | High |
| G2 | `PluginContext` supports `assemble`/`build` | context has compile/validate/generate fields only | Wave F/G blocked | High |
| G3 | `when` predicates are executable, not declarative only | `when` described but not mapped to implementation wave | smart plugin model incomplete | Medium |
| G4 | Diagnostic ranges allocated for new lifecycle domains | no explicit E80xx allocation for discover/assemble/build | ADR 0065 compliance risk | Medium |
| G5 | Order ranges documented for all 6 stages | ranges are only clear for existing stages | plugin authoring conflicts | Medium |
| G6 | `base.generator.artifact_manifest` has implementation wave | plugin is listed but no explicit wave ownership | generate->build contract gap | Medium |
| G7 | Wave sequencing is optimized | phase annotation can run after schema/type extension, independent of phase executor | avoid unnecessary critical path | Low |
| G8 | ADR 0079 coordination is explicit | docs/diagrams plugins are under active migration | churn/conflict risk in Wave D | Medium |
| G9 | Wave C rollback has execution canary | behavior parity cannot rely only on final artifacts | hidden ordering regressions | Low |
| G10 | Plugin inventory baseline is accurate | ADR text can drift from discovered manifests | migration scope ambiguity | Low |
| G11 | Schema/runtime stage-phase vocabulary is aligned | schema allows `build` and `finished`, runtime cannot execute these values | manifest load failures and false green contract tests | High |
| G12 | `generate/init` semantics are consistent with phase contract | `effective_json/yaml` were initially assigned to `init` but write business artifacts | violates "no artifact mutation in init" rule | Medium |
| G13 | `PluginKind` covers assemble/build domains | only `compiler/validator_yaml/validator_json/generator` exist | no kind affinity for new stage plugins | Medium |
| G14 | Phase handler protocol preserves backward compat | adding `on_<phase>` methods changes plugin interface contract | all existing plugins would need rewrite | High |
| G15 | `when.profiles` supersedes `profile_restrictions` | both exist in parallel with overlapping semantics | duplicate profile gating, config drift | Low |
| G16 | Discovery bootstrap contract is specified | no rule about how base manifest is seeded before plugin lifecycle | circular dependency risk | High |
| G17 | Partial stage execution (`--stages`) interacts correctly with finalize guarantee | not addressed | finalize may not run for started stages in partial mode | Medium |
| G18 | Data bus scope (`stage_local` vs `pipeline_shared`) has enforcement rules | scope field defined but no enforcement semantics | cross-stage data leakage risk | Medium |
| G19 | Plugin execution identity is isolated per concurrent invocation | `_current_plugin_id` / `_allowed_dependencies` are shared mutable context fields | identity/dependency corruption in parallel mode | High |
| G20 | Published bus storage is safe under concurrent access | `_published_data` is an unsynchronized nested dict | race conditions and lost/corrupted payloads | High |
| G21 | Per-plugin config is isolated per invocation | runtime mutates shared `ctx.config` before each execution | config bleed between concurrent plugins | Medium |
| G22 | Plugin instance cache is race-free | check-then-insert in `registry.instances` has TOCTOU window | duplicate loads and non-deterministic startup behavior | Medium |
| G23 | Parallel diagnostics/results preserve deterministic ordering | completion order differs from submission order | unstable diagnostics ordering/noisy CI diffs | Medium |
| G24 | Parallel timeout/failure semantics are precise | no finalized contract for cancellation/finalize sequencing under parallel workers | hanging workers or inconsistent finalize coverage | Medium |

Concrete file anchors:

1. `topology-tools/kernel/plugin_base.py`
2. `topology-tools/kernel/plugin_registry.py`
3. `topology-tools/compiler_runtime.py`
4. `topology-tools/compile-topology.py`
5. `topology-tools/plugins/plugins.yaml`
6. `topology-tools/schemas/plugin-manifest.schema.json`
7. `topology-tools/data/error-catalog.yaml`

## Decision

Adopt one plugin-first lifecycle model with explicit stages, universal phases, and contractual inter-plugin data exchange.

### 1. Terminology (Normative)

1. `Stage`: top-level pipeline segment with fixed global order.
2. `Phase`: lifecycle position inside a stage.
3. `Plugin`: unit of execution bound to exactly one stage and one phase.
4. `Data Bus`: typed publish/subscribe channel for plugin-to-plugin exchange.

### 2. Global Stage Model (Normative)

Global order:

`discover -> compile -> validate -> generate -> assemble -> build`

Stage intent:

1. `discover`: load manifests, resolve framework/project context, validate plugin graph/capabilities.
2. `compile`: normalize and resolve canonical compiled model.
3. `validate`: enforce structural/domain/contracts on source and compiled data.
4. `generate`: emit deterministic baseline artifacts (`generated/...`).
5. `assemble`: create execution views (`.work/native/...`, `dist/...`) from baseline + overrides + local inputs.
6. `build`: package, verify trust/integrity, and publish release metadata/artifacts.

### 3. Universal Phase Model (Normative)

Every stage uses:

`init -> pre -> run -> post -> verify -> finalize`

Phase semantics:

1. `init`: data acquisition, context setup, no business artifact mutation.
2. `pre`: fail-fast preconditions and governance checks.
3. `run`: primary stage logic.
4. `post`: derived outputs from successful `run`.
5. `verify`: contract validation of stage outputs.
6. `finalize`: manifests/reports/cleanup; MUST run for any started stage.

### 4. Initial Plugin Assignment (Normative Migration Target)

#### 4.0 Discover

1. `init`: manifest loading from framework/project plugin roots.
2. `pre`: framework/project boundary checks (ADR 0075).
3. `run`: plugin DAG construction and cycle detection.
4. `verify`: capability catalog preflight and compatibility gates.

#### 4.1 Compile

1. `init`: `base.compiler.module_loader`, `base.compiler.model_lock_loader`, `base.compiler.annotation_resolver`, `base.compiler.capability_contract_loader`.
2. `run`: `base.compiler.instance_rows`, `base.compiler.capabilities`.
3. `finalize`: `base.compiler.effective_model`.

#### 4.2 Validate

1. `pre`: `base.validator.governance_contract`, `base.validator.foundation_layout`, `base.validator.foundation_include_contract`, `base.validator.foundation_file_placement`.
2. `run`: all validator_json domain checks, including object/class validators (`object_*`, `class_router.*`).
3. `post`: `base.validator.capability_contract`, `base.validator.instance_placeholders`.

#### 4.3 Generate

1. `run`: `base.generator.effective_json`, `base.generator.effective_yaml`, `base.generator.terraform_proxmox`, `base.generator.terraform_mikrotik`, `base.generator.ansible_inventory`, `base.generator.bootstrap_proxmox`, `base.generator.bootstrap_mikrotik`, `base.generator.bootstrap_orangepi`.
2. `post`: `base.generator.docs`, `base.generator.diagrams`.
3. `finalize`: `base.generator.artifact_manifest` (new plugin).

Note: `effective_json` and `effective_yaml` export the compiled model as baseline artifacts.
They belong in `run` because `init` MUST NOT mutate business artifacts (Section 3, phase 1).

#### 4.4 Assemble (new)

1. `run`: native/dist assembly.
2. `verify`: override layering, local-input requirements, secret-leak guards.
3. `finalize`: assembly manifest and summary.

#### 4.5 Build (new)

1. `run`: package/bundle creation.
2. `verify`: lock/signature/provenance/SBOM verification.
3. `finalize`: release manifest, checksums, result summary.

### 5. Smart Plugin Model (Normative)

Required runtime behavior:

1. Every plugin declares explicit `stage` and `phase` in manifest (`phase` default is `run` only for backward compatibility).
2. Kernel executes by `stage -> phase -> DAG/order`.
3. Plugin implementation is phase-aware via dedicated handlers (`on_init`, `on_pre`, ...) or dispatcher (`execute_phase(ctx, stage, phase)`).
4. Optional `when` predicates can gate execution by:
   - `profiles`
   - `pipeline_modes`
   - `capabilities`
   - `changed_input_scopes` (stub in initial implementation, hardening later)

#### 5.1 PluginContext Extensions (Normative)

`PluginContext` MUST be extended for new stages:

1. `workspace_root`: `.work/native/` root.
2. `dist_root`: `dist/` root.
3. `assembly_manifest`: output of `assemble.finalize`.
4. `signing_backend`: trust backend (`age`, `gpg`, `none`).
5. `release_tag`: release/provenance identifier.
6. `sbom_output_dir`: SBOM output location.

#### 5.2 PluginKind Extension (Normative)

New stage domains require new `PluginKind` values:

1. `assembler`: owns execution-view construction; runs in `assemble` stage only.
2. `builder`: owns packaging and trust verification; runs in `build` stage only.

Existing kinds (`compiler`, `validator_yaml`, `validator_json`, `generator`) retain their stage affinity unchanged.

#### 5.3 Phase Handler Protocol (Normative)

Backward compatibility: existing `execute(ctx, stage) -> PluginResult` is preserved for the `run` phase.

Phase-aware plugins may additionally implement `on_<phase>(ctx, stage) -> PluginResult` handlers.

Registry dispatch rule:
1. For `run` phase: call `execute(ctx, stage)` unless `on_run(ctx, stage)` is also defined (prefer `on_run`).
2. For any other phase: call `on_<phase>(ctx, stage)` if defined; skip (return empty result) if not.
3. The dispatcher `execute_phase(ctx, stage, phase)` is an alternative to handlers — registry prefers handlers if both are present.

This rule guarantees all existing single-phase plugins continue to work without modification and without signature rewrites.

#### 5.4 `when` and `profile_restrictions` Alignment (Normative)

The existing `profile_restrictions` field in `PluginSpec` is superseded by `when.profiles`.

Migration rule: Wave D MUST convert `profile_restrictions` entries to `when.profiles` entries during
phase annotation. Once all plugins are migrated, `profile_restrictions` becomes a deprecated alias
and is removed in Wave H.

#### 5.5 Discovery Bootstrap Contract (Normative)

The `discover` stage faces a bootstrap problem: plugin manifests must be discovered before
plugin lifecycle can start.

Resolution:
1. The base manifest (`topology-tools/plugins/plugins.yaml`) is loaded procedurally by the orchestrator
   before any stage executes — this is the only mandatory non-plugin step.
2. `discover.*` plugins MUST reside in the base manifest; they MUST NOT depend on class/object manifests.
3. `discover.init` then loads all additional manifests (class/object modules) for the remaining stages.
4. Instance roots MUST NOT be scanned for plugin manifests (ADR 0071 data-only policy).

#### 5.6 Partial Stage Execution (Normative)

When pipeline runs with a reduced stage set (e.g., `--stages compile,validate`):

1. Only explicitly requested stages execute their full phase sequence.
2. `finalize` guarantee applies to all started stages regardless of `--stages` flag.
3. `when.changed_input_scopes` stub must not interfere with `--stages` selection; they are orthogonal filters.
4. Skipped stages do not emit `finalize` — they were never started.

### 6. Contractual Publish/Subscribe Data Bus (Normative)

`publish/subscribe` remains the transport but becomes declared and validated.

#### 6.1 Manifest Contract

Manifest fields:

1. `produces` with `key`, `schema_ref` (optional), `scope` (`stage_local|pipeline_shared`), `description`.
2. `consumes` with `from_plugin`, `key`, `required`, `schema_ref` (optional).

`scope` semantics:
- `stage_local`: data is valid only within the publishing stage; invalidated when stage ends.
- `pipeline_shared`: data persists in `_published_data` for the entire pipeline and may be consumed by later stages.

Consumers in a later stage MUST only subscribe to `pipeline_shared` keys. Subscriptions to
`stage_local` keys across stage boundaries are rejected at load time (hard error).

#### 6.2 Runtime Enforcement

1. Consumer MUST include producer in `depends_on`.
2. Consumer MUST subscribe only to declared `produces` keys.
3. Subscriptions are allowed only for completed producers (earlier stage or earlier phase in same stage).
4. Missing required payload is hard error.
5. Payload schema validation is enforced when `schema_ref` is declared.
6. Transitional behavior:
   - Wave E: undeclared publish/subscribe -> `W800x` warning.
   - Wave H: undeclared publish/subscribe -> `E800x` hard error.

#### 6.3 Example

```yaml
plugins:
  - id: base.compiler.instance_rows
    kind: compiler
    stages: [compile]
    phase: run
    order: 40
    depends_on: [base.compiler.annotation_resolver]
    produces:
      - key: normalized_rows
        schema_ref: schemas/plugin-payloads/normalized_rows.v1.json
        scope: pipeline_shared

  - id: base.validator.references
    kind: validator_json
    stages: [validate]
    phase: run
    order: 100
    depends_on: [base.compiler.instance_rows]
    consumes:
      - from_plugin: base.compiler.instance_rows
        key: normalized_rows
        required: true
        schema_ref: schemas/plugin-payloads/normalized_rows.v1.json
```

#### 6.4 Diagnostic Range Allocation (Normative)

1. `E800x`: discover-stage errors.
2. `E810x`: assemble-stage errors.
3. `E820x`: build-stage errors.
4. `W800x`: undeclared data-bus usage during migration window.
5. Ranges MUST remain non-overlapping with existing catalog allocations.

### 7. Dependency and Ordering Rules (Normative)

1. No forward-stage dependency.
2. No forward-phase dependency in same stage.
3. Cycles are hard load errors.
4. `order` remains deterministic tie-breaker inside `stage+phase`.
5. `finalize` MUST run for any started stage.

Normative order ranges by stage:

1. `discover`: 10-89
2. `compile`: 30-89 (preserved)
3. `validate`: 90-189 (preserved)
4. `generate`: 190-399 (preserved per ADR 0074)
5. `assemble`: 400-499
6. `build`: 500-599

### 8. Artifact Ownership Rules (Normative)

1. `generate` writes baseline artifacts only.
2. `assemble` writes execution views only.
3. `build` writes release/package/trust outputs only.
4. Secret-bearing outputs MUST NOT be written into baseline roots.

### 9. Intra-Phase Parallel Execution Model (Normative)

Within each phase of a stage, plugins whose DAG dependencies are fully satisfied MAY execute in parallel.

#### 9.1 Execution Model

Wavefront execution inside each `stage+phase` slice:

1. Build the set of plugins at the current `(stage, phase)`.
2. Compute intra-phase dependency sub-graph (only edges between plugins in the same `stage+phase` set).
3. Execute in wavefronts:
   - Wavefront 0: all plugins with `indegree == 0` — submit to thread pool.
   - When a plugin completes, decrement indegree of its dependants.
   - Next wavefront: all plugins that reached `indegree == 0` — submit.
   - Repeat until all plugins are complete.
4. Cross-phase dependencies are automatically satisfied because phases execute sequentially.
5. `order` field breaks ties in submission order within a wavefront, preserving deterministic log output.

#### 9.2 Thread-Safety Contract (Normative)

The current `PluginContext` design has structural blockers for parallel execution.
The following contracts MUST be enforced before parallelism is enabled:

**Blocker 1 — Shared per-plugin execution state (Critical)**

`_current_plugin_id` and `_allowed_dependencies` are mutable fields on the shared `PluginContext`.
If two plugins execute concurrently, they overwrite each other's identity and dependency set.

Resolution: introduce `PluginExecutionScope` — an immutable per-invocation value object:

```python
@dataclass(frozen=True)
class PluginExecutionScope:
    plugin_id: str
    allowed_dependencies: frozenset[str]
    phase: Phase
    config: Mapping[str, Any]
```

`PluginContext` keeps API compatibility (`publish(key, value)`, `subscribe(plugin_id, key)`).
Registry sets the current `PluginExecutionScope` in a per-worker `contextvars.ContextVar`.
`publish()`/`subscribe()` read identity/dependency/config from that context-local scope, never from shared mutable fields.

**Blocker 2 — Published data concurrent writes (High)**

`_published_data` is a nested `dict[str, dict[str, Any]]` with no synchronization.
Concurrent `publish()` and `subscribe()` calls can corrupt data.

Resolution: protect `_published_data` with `threading.Lock()`.
Alternatively, use per-plugin isolated write buffers merged after plugin completion (copy-on-write).

**Blocker 3 — `compiled_json` mutation (High)**

Compiler plugins can assign `ctx.compiled_json = new_value` directly.
Under parallelism, simultaneous writes produce last-write-wins corruption.

Resolution: enforce write-ownership rule:
- Only ONE plugin per `(stage, phase)` pair is allowed to assign `compiled_json` (the "model owner").
- Model owner is declared in manifest: `compiled_json_owner: true`.
- At most one model owner per `(stage, phase)` is allowed; violation is a load error.
- All other plugins in the same phase MUST NOT assign `compiled_json`.
- Under the phase assignment from Section 4, `base.compiler.effective_model` is the sole owner
  at `(compile, finalize)`. No other plugin in any `compile` phase writes `compiled_json`.

**Blocker 4 — Per-plugin config injection (Medium)**

`execute_plugin()` modifies `ctx.config` in-place before each plugin call.
Concurrent calls would interleave config state.

Resolution: per-plugin config lives in `PluginExecutionScope.config` and is exposed via read-only
`ctx.active_config` accessor. Shared `ctx.config` is treated as pipeline-global read-only config.

**Blocker 5 — Plugin instance caching TOCTOU (Medium)**

`PluginRegistry.instances` dict has a check-then-insert pattern that can load the same plugin twice under concurrency.

Resolution: use `threading.Lock()` around instance cache access, or pre-load all instances before execution.

**Blocker 6 — Generator file write isolation (Low)**

Generators write to a shared `output_dir`. If two generators target the same filename, the last write wins.

Resolution: each generator MUST declare its output file list in `produces`.
The registry validates no two parallel generators claim the same output file path.
This is already partly addressed by the artifact manifest (Section 4.3 `finalize`).

#### 9.3 Plugin Purity Contract (Normative)

A plugin is "parallel-safe" if it satisfies:

1. Does not assign `ctx.compiled_json` (unless declared `compiled_json_owner: true`).
2. Does not mutate any shared `PluginContext` field other than through `publish()`.
3. All outputs go through `publish()` or to explicitly declared file paths.
4. Side effects are limited to file writes under declared output paths.

Validators and generators are parallel-safe by design (they only read `compiled_json` and publish/write files).
Compiler plugins require individual review; most publish data, only `effective_model` writes `compiled_json`.

#### 9.4 Opt-In Enablement (Normative)

Parallel execution is gated by `--parallel-plugins` CLI flag (default: disabled).

Rollout:
1. Wave C: sequential phase executor is the default.
2. Wave C+: add `--parallel-plugins` flag with thread-pool executor. Gated behind feature flag.
3. Wave H: promote parallel executor to default after regression parity.

Thread pool size: `min(cpu_count, plugins_in_wavefront)`. Capped at 8 threads for I/O-bound generators.

## Migration Plan (AS-IS -> Target)

### 10.1 Critical Path

`Wave A -> Wave B -> Wave C -> Wave C+ -> Wave E -> Wave E.1 -> Wave F -> Wave G -> Wave H`

`Wave D` runs in parallel with `Wave B` after schema/types are available.
`Wave C+` (parallel executor) runs after `Wave C` (sequential executor).

### 10.2 Gap-to-Wave Closure Map

| Gap | Closed in wave |
|---|---|
| G1 | F |
| G2 | B |
| G3 | C |
| G4 | B |
| G5 | B |
| G6 | E.1 |
| G7 | B + D (parallelization) |
| G8 | D (coordination rule) |
| G9 | C |
| G10 | A |
| G11 | B |
| G12 | D (annotation fix) |
| G13 | B |
| G14 | B + C |
| G15 | D (convert profile_restrictions) + H (remove alias) |
| G16 | B (specify bootstrap contract) |
| G17 | C (finalize guarantee in partial-stage mode) |
| G18 | E (scope enforcement in runtime) |
| G19 | B |
| G20 | B + C+ |
| G21 | B |
| G22 | C+ |
| G23 | C+ |
| G24 | C+ |

### 10.3 Wave A - Baseline and Inventory Freeze

Goal: freeze current behavior before lifecycle refactor.

Tasks:

1. Freeze plugin inventory baseline from discovered manifests (57 plugins / 7 manifests at ADR update time).
2. Snapshot execution order and published keys for `production` and `modeled`.
3. Freeze generated outputs and diagnostics for parity tests.

Gate:

1. Existing suites green.
2. Baseline snapshots approved.

### 10.4 Wave B - Kernel and Schema Foundations

Goal: add stage/phase/data-bus type contracts without behavior break.

Tasks:

1. Extend runtime `Stage` with `discover`, `assemble`, `build`.
2. Add `Phase` enum and canonical order.
3. Extend `PluginSpec` with `phase` and `when`.
4. Extend `PluginDiagnostic` with phase attribution.
5. Extend `PluginContext` with assemble/build fields (Section 5.1).
6. Extend `PluginKind` with `assembler` and `builder` (Section 5.2).
7. Align manifest schema stage enum with runtime target (`discover|compile|validate|generate|assemble|build`).
8. Align manifest schema phase enum with ADR vocabulary (`init|pre|run|post|verify|finalize`), removing draft token `finished`.
9. Extend manifest schema with `phase`, `produces`, `consumes`, `when`.
10. Add phase handler dispatch protocol to `PluginBase` and `PluginRegistry` (Section 5.3).
11. Document bootstrap contract for discover stage (Section 5.5).
12. Allocate `E800x/E810x/E820x/W800x` ranges in error catalog.
13. Define order ranges for all six stages (Section 7).
14. Keep backward compatibility defaults (`phase` omitted -> `run`; `profile_restrictions` still accepted but deprecated).
15. Update contract tests to reflect aligned enums; add loader test proving a `build` stage manifest can be loaded by runtime.
16. Introduce `PluginExecutionScope` data class with `plugin_id`, `allowed_dependencies`, `phase`, `config` (Section 9.2).
17. Refactor `publish()`/`subscribe()` internals to resolve identity/dependencies/config from per-worker `contextvars` scope.
18. Add `ctx.active_config` read-only accessor backed by `PluginExecutionScope.config`.
19. Add `compiled_json_owner` manifest field; validate at most one owner per `(stage, phase)` at load time.

Gate:

1. Contract tests green.
2. Existing manifests load unchanged.
3. Schema and runtime accept the same stage/phase vocabulary (no `build`/`finished` drift).
4. Phase handler dispatch: existing plugins with only `execute(ctx, stage)` pass a regression run unchanged.

### 10.5 Wave D - Manifest Phase Annotation (parallel with Wave B)

Goal: annotate explicit phase for all plugins in discovered manifests.

Tasks:

1. Apply section 4 phase mapping to all current plugins (note: `effective_json/yaml` → `run`, not `init`).
2. Convert `profile_restrictions` entries to `when.profiles` for all plugins (Section 5.4).
3. Add CI test: every plugin has explicit `phase`.
4. Preserve ADR 0074 ordering for generate.
5. Coordinate with ADR 0079 changes for docs/diagrams plugins.

Gate:

1. Schema/manifest tests green.
2. Parity tests green.
3. No `profile_restrictions` entries remain; all converted to `when.profiles`.

### 10.6 Wave C - Phase Executor and `when` Gating

Goal: run plugins by `stage -> phase -> DAG/order`.

Tasks:

1. Implement phase-aware executor (`for stage: for phase: execute(plugins_at(stage, phase))`).
2. Reject forward stage/phase dependencies at load time.
3. Guarantee `finalize` for all started stages, including partial-stage execution (`--stages` flag).
4. Evaluate `when` predicates for `profiles`, `capabilities`, `pipeline_modes`, `changed_input_scopes` (stub).
5. Enforce data bus scope at stage boundary: invalidate `stage_local` published keys when stage ends.
6. Add `--trace-execution` canary to compare old/new execution traces.

Gate:

1. Stage/phase tests green.
2. Finalize-on-failure tests green (including partial `--stages` runs).
3. `stage_local` keys are inaccessible after stage completion.
4. Canary parity accepted.

### 10.7 Wave C+ - Parallel Plugin Executor

Goal: enable intra-phase parallel execution per Section 9 contract.

Tasks:

1. Add `--parallel-plugins` CLI flag (default: disabled, sequential executor remains default).
2. Implement wavefront executor: build indegree map within `(stage, phase)`, submit zero-indegree plugins to `ThreadPoolExecutor`.
3. Pass `PluginExecutionScope` per-invocation (no shared mutable context fields).
4. Protect `_published_data` with `threading.Lock()` for concurrent publish/subscribe.
5. Pre-load all plugin instances before execution to eliminate TOCTOU race on instance cache.
6. Deep-copy `compiled_json` at stage boundary (frozen read-only snapshot for validate/generate/assemble/build).
7. Validate generator output path non-overlap at load time using `produces` declarations.
8. Add parallel regression tests: run full pipeline with `--parallel-plugins`, compare output to sequential baseline.
9. Add thread-safety unit tests for `publish()`/`subscribe()` under concurrent access.
10. Emit diagnostics/results in deterministic order:
    - collect worker completions in memory,
    - sort by `(stage, phase, order, plugin_id)` before writing reports.
11. Define parallel timeout semantics:
    - timeout marks only the offending plugin as failed,
    - dependants in same phase are skipped,
    - stage `finalize` still runs for started stage.

Gate:

1. Sequential and parallel modes produce byte-identical outputs for all parity tests.
2. No race symptoms under repeated concurrent stress tests (`pytest -n` + high-iteration thread tests).
3. Thread-safety unit tests green.
4. Performance improvement measurable for ≥4 parallel validators.
5. Diagnostics and plugin result ordering are identical across repeated parallel runs.
6. Timeout/skip/finalize behavior matches sequential semantics in dedicated failure tests.

### 10.8 Wave E - Data Bus Contract Enforcement

Goal: migrate pub/sub to declared `produces/consumes`.

Tasks:

1. Annotate high-value keys (`class_map`, `object_map`, `normalized_rows`, `catalog_ids`, `packs_map`, `generated_files`).
2. Enforce producer dependency, declared keys, temporal validity, and payload schema checks.
3. Enforce `stage_local` vs `pipeline_shared` cross-stage subscription constraints.
4. Emit `W800x` for undeclared usage during transition.

Gate:

1. No undeclared consume in CI for annotated keys.
2. Cross-stage `stage_local` subscriptions caught and rejected.
3. Runtime validation tests green.

### 10.9 Wave E.1 - `base.generator.artifact_manifest`

Goal: implement missing generate/finalize plugin.

Tasks:

1. Add plugin at `generate/finalize` (order 390).
2. Emit `generated/<project>/artifact-manifest.json` with checksums and plugin attribution.
3. Publish `artifact_manifest_path` for build-stage consumers.

Gate:

1. Manifest file generated and validated.
2. Checksums verified in tests.

### 10.10 Wave F - Discover + Assemble Pluginization

Goal: remove procedural discovery and move assembly under lifecycle.

Tasks:

1. Implement `discover.init/pre/run/verify` plugins and retire bare discovery path.
2. Implement `assemble.run/verify/finalize` plugins.
3. Add assemble verify checks for overrides, local-input contracts, and secret leakage.

Gate:

1. `.work/native` and `dist/` parity with previous flow.
2. `E810x` diagnostics for failing verify checks.

### 10.11 Wave G - Build Pluginization

Goal: unify packaging/trust under plugin runtime.

Tasks:

1. Implement `build.run/verify/finalize` plugins.
2. Include lock/provenance/signature/SBOM checks.
3. Emit release manifest and checksum summary.

Gate:

1. Release pipeline green under pluginized build.
2. `E820x` diagnostics emitted correctly.

### 10.12 Wave H - Hard Cutover and Cleanup

Goal: complete contract hardening and remove transitional paths.

Tasks:

1. Promote undeclared pub/sub from `W800x` to `E800x`.
2. Remove `profile_restrictions` deprecated alias from `PluginSpec` and schema (Section 5.4).
3. Remove legacy discovery and lifecycle bypass code paths.
4. Keep `--trace-execution` as debug flag or remove after two green cycles.
5. Promote `--parallel-plugins` to default (parallel executor becomes standard).
6. Update runbooks and developer documentation.

Gate:

1. All plugin suites green.
2. No legacy path reachable.
3. No undeclared pub/sub in CI.
4. `profile_restrictions` absent from schema and runtime.

## Required Test Additions

1. Kernel contract tests: stage/phase ordering, forward dependency rejection, finalize guarantee.
2. Schema tests: explicit phase, produces/consumes validity, discovery-root policy.
3. Integration tests: compile->validate and generate->assemble->build declared data-bus chains.
4. Regression tests: generated parity, assembled workspace parity, release package/trust parity.
5. CI conformance test: schema stage/phase enums must match runtime `Stage`/`Phase` enums.
6. Cutover checklist tests from `adr/0080-analysis/CUTOVER-CHECKLIST.md` become release gates.
7. Thread-safety tests: concurrent `publish()`/`subscribe()` under `ThreadPoolExecutor` with ≥8 threads.
8. Parallel parity tests: sequential vs `--parallel-plugins` output byte-identical for full pipeline.
9. `compiled_json_owner` uniqueness: load-time test rejects two owners at same `(stage, phase)`.

## Acceptance Criteria

1. Stage order is implemented as `discover -> compile -> validate -> generate -> assemble -> build`.
2. Universal phase order is implemented for every stage.
3. All discovered plugins have explicit `phase`.
4. Forward stage/phase dependencies are rejected at load time.
5. Runtime diagnostics include phase attribution.
6. Manifest schema supports and runtime enforces `produces`/`consumes`.
7. `when` predicates are evaluated for profile/capability/pipeline mode with changed-scope stub.
8. `base.generator.artifact_manifest` is implemented and consumed by downstream stage.
9. `discover` and `assemble` run via plugin registry, no mandatory procedural bypass.
10. `build` runs via plugin registry and emits trust/release outputs.
11. `finalize` executes for any started stage, including failure paths and partial `--stages` runs.
12. Manifest schema and runtime share the same stage/phase vocabulary (`discover|...|build` and `init|...|finalize`).
13. Diagnostic ranges `E800x/E810x/E820x/W800x` are cataloged without overlap.
14. Hard cutover removes legacy discovery and undeclared pub/sub usage.
15. `PluginKind` includes `assembler` and `builder`.
16. Phase handler protocol preserves backward compat: all existing `execute(ctx, stage)` plugins run unchanged.
17. `profile_restrictions` converted to `when.profiles` and removed as standalone field in Wave H.
18. `stage_local` data bus keys are invalidated at stage boundary and rejected for cross-stage subscriptions.
19. Discovery bootstrap contract is respected: base manifest is the only pre-lifecycle load, discover plugins reside in base manifest only.
20. `PluginExecutionScope` replaces shared `_current_plugin_id`/`_allowed_dependencies` for all plugin invocations.
21. `_published_data` access is thread-safe under concurrent plugin execution.
22. `compiled_json` is frozen (read-only deep-copy) after compile stage boundary.
23. `--parallel-plugins` flag enables wavefront parallel execution within each `(stage, phase)`.
24. Sequential and parallel modes produce identical outputs for all parity tests.
25. Parallel diagnostics ordering is deterministic across repeated runs.
26. Parallel timeout/skip/finalize semantics are equivalent to sequential contract.

## Risks and Mitigations

1. Risk: executor refactor changes runtime ordering subtly.
   - Mitigation: Wave A baseline + Wave C `--trace-execution` canary before hard cutover.
2. Risk: assemble/build plugins blocked by missing context fields.
   - Mitigation: context extension is mandatory in Wave B.
3. Risk: discover stage remains partially procedural.
   - Mitigation: explicit discover pluginization in Wave F with deletion gate in Wave H.
4. Risk: schema/runtime drift for new fields.
   - Mitigation: enforce conformance tests at load-time and runtime for each new field.
5. Risk: ADR 0079 concurrent generator migration causes phase annotation churn.
   - Mitigation: Wave D coordination rule to preserve/re-apply phase annotations during docs/diagrams refactors.
6. Risk: stale plugin inventory assumptions.
   - Mitigation: Wave A mandatory recount from discovered manifests.
7. Risk: determinism regressions in later optimization.
   - Mitigation: keep parallel/incremental optimizations after hard cutover and guard with repeat-run assertions.
8. Risk: schema/runtime drift reappears after partial merges.
   - Mitigation: add CI guard test that stage and phase enums in schema and runtime stay in sync.
9. Risk: phase handler protocol change breaks existing plugin interface contract.
   - Mitigation: Registry dispatch prefers legacy `execute(ctx, stage)` for `run` phase; new methods are additive. Full regression before Wave C gate.
10. Risk: `stage_local` scope enforcement invalidates data needed by later phases.
    - Mitigation: review all high-value key scopes before Wave E; default all existing keys to `pipeline_shared` during migration.
11. Risk: parallel plugin execution introduces non-deterministic output ordering.
    - Mitigation: `order` controls submission order, and result emission is sorted by `(stage, phase, order, plugin_id)` before reporting; parity tests compare sequential vs parallel byte-for-byte.
12. Risk: thread-safety regressions introduced by future plugins unaware of parallel contract.
    - Mitigation: `PluginExecutionScope` is the only interface for identity/config; `PluginContext` shared fields are read-only after stage start. Plugin purity contract (Section 9.3) documented and enforced by code review.
13. Risk: GIL limits parallelism benefit for CPU-bound plugins.
    - Mitigation: most plugins are I/O-bound (YAML parse, file write); `ThreadPoolExecutor` is sufficient. If CPU-bound bottleneck emerges, migrate to `ProcessPoolExecutor` with serializable scope (future ADR).

## References

- `adr/0005-diagram-generation-determinism-and-binding-visibility.md`
- `adr/0027-mermaid-rendering-strategy-consolidation.md`
- `adr/0028-topology-tools-architecture-consolidation.md`
- `adr/0050-generated-directory-restructuring.md`
- `adr/0051-ansible-runtime-and-secrets.md`
- `adr/0052-build-pipeline-after-ansible.md`
- `adr/0055-manual-terraform-extension-layer.md`
- `adr/0056-native-execution-workspace.md`
- `adr/0063-plugin-microkernel-for-compiler-validators-generators.md`
- `adr/0065-plugin-api-contract-specification.md`
- `adr/0069-plugin-first-compiler-refactor-and-thin-orchestrator.md`
- `adr/0071-sharded-instance-files-and-flat-instances-root.md`
- `adr/0072-unified-secrets-management-sops-age.md`
- `adr/0074-v5-generator-architecture.md`
- `adr/0075-framework-project-separation.md`
- `adr/0076-framework-distribution-and-multi-repository-extraction.md`
- `adr/0078-object-module-local-template-layout.md`
- `adr/0079-v5-documentation-and-diagram-generation-migration.md`
- `adr/0080-analysis/GAP-ANALYSIS.md`
- `adr/0080-analysis/IMPLEMENTATION-PLAN.md`
- `adr/0080-analysis/CUTOVER-CHECKLIST.md`
