# ADR 0080 Implementation Plan

**ADR:** `adr/0080-unified-build-pipeline-stage-phase-and-plugin-data-bus.md`
**Date:** 2026-03-26
**Status:** Accepted
**Gap Analysis:** `adr/0080-analysis/GAP-ANALYSIS.md`
**Cutover Checklist:** `adr/0080-analysis/CUTOVER-CHECKLIST.md`
**Cutover Plan:** `adr/0080-analysis/CUTOVER-PLAN.md`

---

## Goal

Unify the plugin runtime around a single lifecycle model with:

1. Six explicit stages: `discover → compile → validate → generate → assemble → build`
2. Universal phase order within each stage: `init → pre → run → post → verify → finalize`
3. Declared `produces`/`consumes` contracts on the publish/subscribe data bus
4. `assemble` and `build` stages executed via plugin registry
5. `finalize` guaranteed to run for any started stage

---

## Implementation Status (2026-03-26)

- `Wave B` completed: runtime stage/phase enums, plugin kind extensions, scope-based execution context, and schema alignment are implemented.
- `Wave C` completed: stage->phase executor, finalize guarantees, `stage_local` invalidation, and trace mode are implemented.
- `Wave C+` completed: intra-phase parallel wavefront executor, deterministic result ordering, and thread-safe publish/subscribe are implemented.
- `Wave D` completed: explicit `phase` annotations are present across all discovered manifests.
- `Wave E` completed: produces/consumes contracts are validated; strict undeclared contract mode (`E8004`-`E8007`) is implemented.
- Stage-specific `order` ranges are now enforced at manifest load time and validated by contract tests.
- Structured module plugin entry paths are now enforced at manifest load time:
  deprecated flat `plugins/<file>.py` entries are rejected; kind-to-family affinity is enforced
  for `plugins/<family>/...` (`discoverers`, `compilers`, `validators`, `generators`, `assemblers`, `builders`).
- Kind-to-family affinity checks now also cover base-style entry paths (`<family>/module.py:ClassName`),
  and contract tests verify discovered manifest entries resolve to real modules on disk.
- Error catalog range conformance tests now guard ADR0080 allocations (`E800x/E810x/E820x/W800x`) against overlap.
- Repeated-run deterministic guards are added for parallel result ordering and artifact manifest emission.
- Profile parity tests now compare sequential vs parallel diagnostics/trace signatures, effective payloads, and published key inventory for `production` and `modeled`.
- Contract-warning parity tests confirm no `W800x` data-bus warnings on current `production`/`modeled` baseline.
- Base-manifest run-phase backward-compat regression test now verifies `execute_phase(run)` dispatches through `execute()` for 47+ plugins.
- Quality-gate contract tests assert key validation/render gate plugins stay active in plugin-first path.
- Cutover checklist closure: `.work/native` + `dist` assembly/build parity is now covered by integration assertions.
- `Wave E.1` completed: `base.generator.artifact_manifest` implemented at `generate/finalize`.
- `Wave F` completed (runtime slice): assemble stage plugins implemented (`workspace`, `verify`, `manifest`) and wired into compiler lifecycle.
- `Wave G` completed (runtime slice): build stage plugins implemented (`bundle`, `sbom`, `release_manifest`) and wired into compiler lifecycle.
- Parallel executor is now default; CLI exposes `--no-parallel-plugins` to force sequential mode.
- Discover bootstrap is pluginized: base manifest is loaded procedurally, module manifests are loaded by `discover.init`, and `instances_root` is excluded from plugin discovery.
- `Wave H` completed for runtime enforcement: undeclared data-bus usage is hard-error by default (`plugin_contract_errors=True`), with explicit opt-out via `--no-plugin-contract-errors`.
- Transitional consume-inference shim removed from runtime; all active subscriptions now require explicit `consumes` declarations.
- Contract audit snapshot (2026-03-26, `production` + `modeled` profiles): 0 runtime `W800x` even with inference disabled.
- `when.changed_input_scopes` now uses `assemble.init` dirty-scope evaluation backed by artifact-manifest checksum deltas (state persisted per workspace).

---

## Primary Files

| File | Role |
|------|------|
| `topology-tools/kernel/plugin_base.py` | `Stage`, `Phase` enums; `PluginContext` extensions |
| `topology-tools/kernel/plugin_registry.py` | Phase-aware executor, `when` predicate evaluation |
| `topology-tools/compiler_runtime.py` | Discovery pluginization |
| `topology-tools/compile-topology.py` | Thin orchestrator wiring |
| `topology-tools/plugin_manifest_discovery.py` | Deterministic base/class/object manifest discovery (no `instances_root` scanning) |
| `topology-tools/plugins/plugins.yaml` | Phase annotations for all base plugins (current baseline: 48 in base manifest, 57 discovered total) |
| `topology-tools/schemas/plugin-manifest.schema.json` | `phase`, `produces`, `consumes`, `when` fields |
| `topology-tools/data/error-catalog.yaml` | E80xx–E82xx range allocation |
| `tests/plugin_contract/test_manifest.py` | Schema/runtime conformance tests for stage/phase vocabulary |

---

## Critical Path

```
Wave A  (baseline freeze)
  ↓
Wave B  (kernel extensions)  ←→  Wave D  (phase annotations — runs in parallel)
  ↓
Wave C  (phase executor refactor)
  ↓
Wave C+ (parallel plugin executor — opt-in)
  ↓
Wave E  (data bus contracts)  +  Wave E.1  (artifact_manifest plugin)
  ↓
Wave F  (assemble stage)
  ↓
Wave G  (build stage)
  ↓
Wave H  (cleanup and hard cutover — parallel executor promoted to default)
```

Wave D is **parallel with Wave B** — annotations require only schema/PluginSpec changes
from Wave B, not the new executor from Wave C.

Wave C+ follows Wave C — it requires the sequential phase executor as baseline and
`PluginExecutionScope` from Wave B.

---

## P0 Alignment Blockers (must be closed in Wave B)

1. Runtime `Stage` enum currently supports only `compile|validate|generate`; schema already accepts `build` — misaligned.
2. Schema phase enum uses draft token `finished`; target lifecycle token is `finalize` — misaligned.
3. `PluginSpec` has no `phase` field — manifest phase annotations are silently ignored at runtime.
4. `PluginSpec` has no `when` field — smart plugin gating cannot be implemented.
5. `PluginKind` lacks `assembler` and `builder` values — new stage plugins have no kind affinity.
6. `PluginContext` has no assemble/build fields — Wave F/G are fully blocked.
7. `execute_stage()` is stage-only; its signature and return type must evolve for phase-aware execution.
8. Phase handler protocol (`on_<phase>`) is not defined in `PluginBase` — new phase methods have no contract.
9. `profile_restrictions` and `when.profiles` are parallel gating mechanisms — need consolidation path.
10. Existing contract tests assert draft schema values (`finished`, missing `discover/assemble` stages) and produce false greens.

---

## Wave A — Baseline and Inventory Freeze

**Goal:** Freeze current behavior before lifecycle refactor.

**Tasks:**

1. Count actual registered plugins per stage across all discovered manifests
   (current observed baseline: 57 plugins in 7 manifests; base manifest: 48).
2. Snapshot current plugin execution order and published data keys via `ctx.get_published_data()`
   after a full compile run on `production` and `modeled` profiles.
3. Add regression fixtures for generated outputs and diagnostics.
4. Add runtime publish/subscribe key inventory snapshot.

**Gate:**

- Existing test suite green.
- Baseline artifact snapshots committed and approved.
- Published key snapshot committed to `adr/0080-analysis/`.

---

## Wave B — Kernel Type Extensions

**Goal:** Add stage/phase primitives and context extensions without behavior break.

**Primary files:**

- `topology-tools/kernel/plugin_base.py`
- `topology-tools/kernel/plugin_registry.py`
- `topology-tools/schemas/plugin-manifest.schema.json`
- `topology-tools/data/error-catalog.yaml`

**Tasks:**

1. Extend `Stage` enum with `DISCOVER`, `ASSEMBLE`, `BUILD`.
2. Add `Phase` enum: `INIT`, `PRE`, `RUN`, `POST`, `VERIFY`, `FINALIZE` with canonical order.
3. Extend `PluginSpec` with `phase` (default: `RUN`) and `when` (opaque dict, unevaluated).
4. Extend `PluginDiagnostic` with `phase` field.
5. Extend `PluginContext` with assemble/build fields:
   ```python
   workspace_root: Optional[str]   # .work/native/ path
   dist_root: Optional[str]        # dist/ path
   assembly_manifest: dict         # output of assemble.finalize
   signing_backend: Optional[str]  # age/gpg/none
   release_tag: Optional[str]      # for provenance
   sbom_output_dir: Optional[str]
   ```
6. Extend `PluginKind` with `ASSEMBLER` and `BUILDER`.
7. Add phase handler dispatch to `PluginBase` and `PluginRegistry` (ADR Section 5.3):
   - Add optional `on_init`, `on_pre`, `on_run`, `on_post`, `on_verify`, `on_finalize` methods to `PluginBase`.
   - Registry dispatch rule: for `run` phase call `execute(ctx, stage)` unless `on_run(ctx, stage)` exists; for other phases call `on_<phase>(ctx, stage)` if exists, skip otherwise.
   - Preserve full backward compat — existing plugins with only `execute(ctx, stage)` work unchanged.
8. Align schema stage enum to runtime target: `discover`, `compile`, `validate`, `generate`, `assemble`, `build`.
9. Align schema phase enum to runtime target: `init`, `pre`, `run`, `post`, `verify`, `finalize` (remove draft token `finished`).
10. Add `produces`/`consumes`/`when` fields to manifest schema (unenforced, structure only).
11. Deprecate `profile_restrictions` in schema (keep accepting but emit deprecation note pointing to `when.profiles`).
12. Allocate diagnostic code ranges in `error-catalog.yaml`:
    - `E800x`: discover stage errors
    - `E810x`: assemble stage errors
    - `E820x`: build stage errors
    - `W800x`: data bus undeclared key warnings (transitional)
13. Define normative `order` ranges per stage:
    - `discover`: 10–89
    - `compile`: 30–89 (preserve)
    - `validate`: 90–189 (preserve)
    - `generate`: 190–399 (preserve, per ADR 0074)
    - `assemble`: 400–499
    - `build`: 500–599
14. Keep `phase=RUN` default — existing manifests load unchanged.
15. Update `tests/plugin_contract/test_manifest.py` to assert aligned stage/phase enums and add test that a manifest with `stage: build` loads successfully in runtime.
16. Add regression test: existing plugins with `execute(ctx, stage)` only — full pipeline run produces identical output.
17. Introduce `PluginExecutionScope` immutable data class (ADR Section 9.2):
    ```python
    @dataclass(frozen=True)
    class PluginExecutionScope:
        plugin_id: str
        allowed_dependencies: frozenset[str]
        phase: Phase
        config: Mapping[str, Any]  # immutable per-plugin config snapshot
    ```
18. Keep plugin API signatures unchanged (`publish(key, value)`, `subscribe(plugin_id, key)`); refactor internals to read scope from per-worker `contextvars`.
19. Add `ctx.active_config` read-only accessor backed by `PluginExecutionScope.config`; shared `ctx.config` remains pipeline-global read-only.
20. Add `compiled_json_owner: bool` manifest field; validate at most one owner per `(stage, phase)` at load time.
21. Remove `_current_plugin_id` and `_allowed_dependencies` mutable fields from `PluginContext` after migration.

**Gate:**

- Contract/unit tests green.
- Existing manifests load unchanged.
- Schema validation passes with and without `phase`/`produces`/`consumes`.
- Schema/runtime vocabulary lock proven by tests (no `build`/`finished` drift).
- Regression test: all existing plugins produce identical output after phase handler dispatch change.

---

## Wave D — Manifest Phase Annotation (parallel with Wave B)

**Goal:** Explicitly annotate phases for all plugins per ADR 0080 Section 4.

**Prerequisite:** Wave B schema/PluginSpec changes only (not Wave C executor).

**Coordination:** `base.generator.docs` and `base.generator.diagrams` are concurrently
modified by ADR 0079. Annotate them with `phase: run` as-is; ADR 0079 work must preserve
or re-apply phase annotation after any plugin restructuring.

**Tasks:**

1. Annotate all `compile` plugins per Section 4.1:
   - `init`: `module_loader`, `model_lock_loader`, `annotation_resolver`, `capability_contract_loader`
   - `run`: `instance_rows`, `capabilities`
   - `finalize`: `effective_model`

2. Annotate all `validate` plugins per Section 4.2:
   - `pre`: governance, foundation_layout, foundation_include_contract, foundation_file_placement
   - `run`: all validator_json domain checks
   - `post`: capability_contract, instance_placeholders

3. Annotate all `generate` plugins per Section 4.3:
   - `run`: `effective_json`, `effective_yaml`, terraform_proxmox, terraform_mikrotik,
     ansible_inventory, bootstrap_* (note: `effective_json/yaml` are `run`, not `init` — they write files)
   - `post`: docs, diagrams
   - `finalize`: `artifact_manifest` (placeholder — implemented in Wave E.1)

4. Convert all `profile_restrictions` entries to `when.profiles` (ADR Section 5.4).

5. Add test: every plugin in every discovered manifest must have an explicit `phase` field.
6. Add test: no plugin in any manifest uses `profile_restrictions` after Wave D is done.

**Gate:**

- Manifest schema tests green.
- Execution order/parity tests green (phase field ignored by current executor — backward compat).
- Every plugin has explicit `phase` in manifest.
- No `profile_restrictions` entries remain.

---

## Wave C — Stage/Phase Executor Refactor

**Goal:** Execute plugins by `stage → phase → DAG/order`.

**Primary files:**

- `topology-tools/kernel/plugin_registry.py`
- `topology-tools/compile-topology.py`
- `topology-tools/compiler_runtime.py`

**Tasks:**

1. Replace stage-only execution loop with phase-aware execution:
   `for stage in stages: for phase in phases: execute(plugins_at(stage, phase))`
2. Enforce forward stage/phase dependency rejection at manifest load time.
3. Enforce `finalize` execution for any started stage, even after exception.
4. Enforce `finalize` for started stages in partial `--stages` runs (skipped stages never start, so no finalize needed for them).
5. Enforce data bus scope: invalidate all `stage_local` keys when their publishing stage ends.
6. Implement `when` predicate evaluation:
   - `profiles`: gate on `ctx.profile`
   - `capabilities`: gate on `ctx.capability_catalog`
   - `pipeline_modes`: gate on runtime pipeline mode flag
   - `changed_input_scopes`: gate on dirty-input scope detection (stub — returns True; full impl in Wave F)
7. Add canary mode: `--trace-execution` flag that logs stage/phase/plugin execution sequence
   for comparison against Wave A baseline before hard cutover.
8. Wrap `compiler_runtime.discover_plugin_manifests()` call in a `discover.run` shim
   (full pluginization deferred to Wave F).

**Gate:**

- Stage/phase order tests green.
- `finalize` runs in all failure scenarios (unit tests).
- `finalize` runs in partial `--stages` execution (integration test).
- `stage_local` invalidation tested: subscribe after stage end → hard error.
- Diagnostics parity with Wave A baseline accepted.
- `when` predicate gates pass for profile, capability, and pipeline_mode cases.

---

## Wave C+ — Parallel Plugin Executor

**Goal:** Enable intra-phase parallel execution per ADR Section 9 contract.

**Prerequisite:** Wave C (sequential phase executor), Wave B (`PluginExecutionScope`).

**Primary files:**

- `topology-tools/kernel/plugin_registry.py`
- `topology-tools/kernel/plugin_base.py`

**Tasks:**

1. Add `--parallel-plugins` CLI flag (default: disabled; sequential executor remains default).
2. Implement wavefront executor within each `(stage, phase)`:
   - Build indegree map from intra-phase dependency edges.
   - Submit all `indegree == 0` plugins to `concurrent.futures.ThreadPoolExecutor`.
   - On completion, decrement dependants' indegree; submit newly-zero plugins.
   - `order` field controls submission order within each wavefront (deterministic logging).
3. Pass `PluginExecutionScope` per-invocation — no shared mutable fields used during execution.
4. Protect `_published_data` with `threading.Lock()` for concurrent `publish()`/`subscribe()` calls.
5. Pre-load all plugin instances before execution to eliminate TOCTOU race on instance cache.
6. Deep-copy `compiled_json` at compile stage boundary — frozen read-only snapshot for all later stages.
7. Validate generator output path non-overlap at load time using `produces` declarations.
8. Add parallel regression test: run full pipeline with `--parallel-plugins`, compare output
   byte-for-byte against sequential baseline from Wave A.
9. Add thread-safety unit tests: concurrent `publish()`/`subscribe()` with ≥8 threads, verify no data loss.
10. Thread pool size: `min(cpu_count, wavefront_size)`, capped at 8.
11. Deterministic result merge: collect worker completions and emit diagnostics/results sorted by
    `(stage, phase, order, plugin_id)` rather than completion timestamp.
12. Define timeout semantics for parallel wavefronts:
    - timed-out plugin is marked failed,
    - dependants in same phase are skipped,
    - stage `finalize` still runs if stage started.

**Gate:**

- Sequential and parallel modes produce byte-identical outputs for all parity tests.
- Thread-safety unit tests green (no data loss under concurrent publish/subscribe).
- No data race under stress test with 8+ concurrent plugins.
- Performance improvement measurable for ≥4 parallel validators.
- `--parallel-plugins` disabled by default — zero behavior change for users who don't opt in.
- Diagnostics ordering is deterministic across repeated parallel runs.
- Parallel timeout/skip/finalize semantics match sequential contract.

---

## Wave E — Data Bus Contract Upgrade

**Goal:** Migrate publish/subscribe from implicit keys to declared contracts.

**Primary files:**

- `topology-tools/schemas/plugin-manifest.schema.json`
- `topology-tools/kernel/plugin_registry.py`
- All plugins that publish/subscribe in compile/validate/generate stages

**Tasks:**

1. Enable runtime enforcement of `produces`/`consumes` declarations:
   - Plugin without `produces` but calling `ctx.publish()` → `W800x` warning (not error).
   - Plugin without `consumes` but calling `ctx.subscribe()` → `W800x` warning (not error).
   - Transitional period: warnings only. Hard errors activate in Wave H.
2. Add runtime schema payload validation when `schema_ref` is declared in `produces`/`consumes`.
3. Enforce `stage_local` vs `pipeline_shared` cross-stage subscription constraints (reject `stage_local` subscriptions from later stages).
4. Default all existing high-value keys to `pipeline_shared` scope during annotation.
5. Annotate high-value keys first:
   - `base.compiler.module_loader` → `produces: class_map, object_map` (scope: pipeline_shared)
   - `base.compiler.instance_rows` → `produces: normalized_rows` (scope: pipeline_shared)
   - `base.compiler.capability_contract_loader` → `produces: catalog_ids, packs_map` (scope: pipeline_shared)
   - `base.generator.*` → `produces: generated_dir, generated_files, <family>_files` (scope: pipeline_shared)
6. Add `consumer must include producer in depends_on` enforcement.

**Gate:**

- No undeclared consume in CI for annotated high-value keys.
- `W800x` warnings emitted for remaining unannotated plugins.
- Schema payload validation passes for declared `schema_ref` entries.
- Cross-stage `stage_local` subscription rejected with hard error.

---

## Wave E.1 — `base.generator.artifact_manifest` Plugin

**Goal:** Implement the `generate/finalize` artifact manifest plugin from ADR 0080 Section 4.3.

**Primary files:**

- `topology-tools/plugins/generators/artifact_manifest_generator.py` (new)
- `topology-tools/plugins/plugins.yaml`

**Tasks:**

1. Implement `base.generator.artifact_manifest` as a `GeneratorPlugin`:
   - `stage: generate`, `phase: finalize`, `order: 390`
   - Subscribes to `generated_files` from all `generate/run` and `generate/post` plugins.
   - Emits `generated/<project>/artifact-manifest.json` with per-file checksums and plugin attribution.
2. Declare `consumes` for all upstream generator keys.
3. Declare `produces: artifact_manifest_path` for `build.init` to consume.

**Gate:**

- `artifact-manifest.json` emitted and passes schema validation.
- Checksums match actual generated files.
- `build.init` can subscribe to `artifact_manifest_path` (tested with stub).

---

## Wave F — Assemble Stage Pluginization

**Goal:** Move execution-root assembly under plugin lifecycle.

**Primary files:**

- `topology-tools/plugins/assemblers/` (new directory)
- `topology-tools/compile-topology.py`
- `topology-tools/compiler_runtime.py`

**Prerequisite:** Wave B `PluginContext` extensions (`workspace_root`, `dist_root`).

**Tasks:**

1. Implement `assemble.run` plugin for native/dist workspace assembly:
   - Reads `workspace_root` and `dist_root` from `ctx`.
   - Merges baseline artifacts with overrides and local inputs per ADR 0055/0056.
   - Subscribes to `artifact_manifest_path` from `base.generator.artifact_manifest`.
2. Implement `assemble.verify` plugin for override/local-input/secrets contract:
   - Override layering checks.
   - Local-input requirement checks.
   - Secret-leak guard: regex scan of assembled outputs for unencrypted secret patterns.
   - Emits `E810x` diagnostics on violations.
3. Implement `assemble.finalize` plugin for assembly manifest emission.
4. Complete pluginization of `discover_plugin_manifests()` per ADR Section 5.5 bootstrap contract:
   - `discover.init`: load manifests from all module roots (base manifest already loaded by orchestrator before this plugin runs).
   - `discover.pre`: framework/project boundary check (ADR 0075).
   - `discover.run`: build plugin DAG, validate cycles.
   - `discover.verify`: capability catalog preflight.
   - All `discover.*` plugins MUST reside in base manifest (no class/object module dependency).
   - Stop scanning `instances_root` for plugin manifests (ADR 0071 data-only policy).
5. Implement `changed_input_scopes` stub → full evaluation in `assemble.init`
   (compares artifact manifest checksums against previous run to determine dirty scopes).

**Gate:**

- `.work/native` and `dist/` parity with existing assembly workflows.
- Secret-leak guard catches test cases with mock unencrypted secrets.
- `E810x` diagnostics emitted correctly.
- `discover_plugin_manifests()` bare function replaced, bootstrap contract respected.

---

## Wave G — Build Stage Pluginization

**Goal:** Unify packaging and trust verification under plugin runtime.

**Primary files:**

- `topology-tools/plugins/build/` (new directory)
- Framework lock and distribution helpers integration points

**Prerequisite:** Wave F `assemble.finalize` plugin (provides `assembly_manifest`).

**Tasks:**

1. `build.run` — package/bundle plugin:
   - Reads `assembly_manifest` from `assemble.finalize`.
   - Produces release bundle.
2. `build.verify` — trust verification plugins:
   - Lock verification.
   - Provenance/signature checks.
   - SBOM generation (separate sub-plugin `base.build.sbom`).
   - Emits `E820x` diagnostics on violations.
3. `build.finalize` — release manifest, checksum, and result summary plugin:
   - Produces `release-manifest.json` with artifact list and trust status.

**Gate:**

- Release pipeline passes with pluginized build stage.
- `E820x` diagnostics emitted correctly by verify plugins.
- SBOM output matches expected format.

---

## Wave H — Cleanup and Hard Cutover

**Goal:** Remove transitional paths and complete hard enforcement.

**Primary files:**

- `topology-tools/compiler_runtime.py` (remove legacy `discover_plugin_manifests()`)
- `topology-tools/compiler_plugin_context.py`
- Any compatibility bridges in orchestrator/runtime

**Tasks:**

1. Promote `W800x` data bus warnings to `E800x` hard errors (end of transitional period).
2. Verify all plugins have `produces`/`consumes` declarations.
3. Remove legacy `compiler_runtime.discover_plugin_manifests()` bare function
   (replaced by `discover.*` plugins in Wave F).
4. Remove `profile_restrictions` deprecated alias from `PluginSpec` and schema.
5. Remove any dead code paths that bypass plugin lifecycle.
6. Remove `--trace-execution` canary mode or promote to permanent debug flag.
7. Promote `--parallel-plugins` to default (parallel executor becomes standard after regression parity).
8. Finalize operator runbooks and update CLAUDE.md guidance.

**Gate:**

- All plugin contract/integration/regression suites green.
- No `W800x` warnings in CI — all undeclared pub/sub resolved.
- No legacy runtime paths reachable.
- `discover_plugin_manifests()` function absent from codebase.
- `profile_restrictions` absent from schema and `PluginSpec`.

---

## Acceptance Criteria Summary

Mapped to ADR 0080 sections plus additions from gap analysis:

| # | Criterion | Wave |
|---|-----------|------|
| 1 | Stage order `discover → compile → validate → generate → assemble → build` implemented | C |
| 2 | Universal phase order `init → pre → run → post → verify → finalize` per stage | C |
| 3 | All plugins have explicit `phase` annotation | D |
| 4 | Forward stage/phase dependencies rejected at manifest load | C |
| 5 | `produces`/`consumes` contracts supported and validated | E |
| 6 | `assemble` and `build` stages execute via plugin registry | F/G |
| 7 | `finalize` runs for all started stages (failure paths and `--stages` partial runs) | C |
| 8 | `when` predicate gates work for profile/capability/pipeline_mode | C |
| 9 | `discover` stage replaces `compiler_runtime.discover_plugin_manifests()` | F |
| 10 | Diagnostic code ranges E800x–E820x + W800x registered in error-catalog.yaml | B |
| 11 | `PluginContext` contains assemble/build fields | B |
| 12 | `base.generator.artifact_manifest` implemented and emitting checksums | E.1 |
| 13 | Order ranges defined for all 6 stages | B |
| 14 | Schema and runtime use identical stage/phase enums | B |
| 15 | `PluginKind` includes `assembler` and `builder` | B |
| 16 | Phase handler protocol backward-compat: existing `execute(ctx, stage)` plugins unchanged | B/C |
| 17 | `profile_restrictions` converted to `when.profiles`, deprecated alias removed | D/H |
| 18 | `stage_local` keys invalidated at stage boundary, cross-stage subscription rejected | C/E |
| 19 | Bootstrap contract: base manifest is only pre-lifecycle load; discover plugins in base manifest only | B/F |
| 20 | `PluginExecutionScope` replaces shared `_current_plugin_id`/`_allowed_dependencies` | B |
| 21 | `_published_data` access is thread-safe under concurrent execution | C+ |
| 22 | `compiled_json` frozen (read-only deep-copy) after compile stage boundary | C+ |
| 23 | `--parallel-plugins` enables wavefront parallel execution within each `(stage, phase)` | C+ |
| 24 | Sequential and parallel modes produce identical outputs for all parity tests | C+/H |
| 25 | Parallel diagnostics/results ordering is deterministic across repeated runs | C+ |
| 26 | Parallel timeout/skip/finalize behavior matches sequential contract | C+ |

---

## Immediate Start Slice

The implementation should start with the smallest Wave B slice that removes ADR/runtime drift and unlocks the rest of the work.

**Start now:**

1. Align runtime/schema enums:
   - add `discover`, `assemble`, `build` to `Stage`
   - add `Phase`
   - replace schema token `finished` with `finalize`
2. Extend `PluginSpec` and manifest schema:
   - `phase`
   - `when`
   - `compiled_json_owner`
   - `assembler` / `builder` kinds
3. Add backward-compatible phase dispatch:
   - keep `execute(ctx, stage)` working for all existing plugins
   - add optional `on_<phase>(ctx, stage)` hooks
4. Introduce `PluginExecutionScope` + `contextvars` plumbing:
   - remove reliance on `_current_plugin_id` / `_allowed_dependencies`
   - add `ctx.active_config`
5. Update contract tests first:
   - schema/runtime enum sync
   - `build` manifest load
   - legacy plugin dispatch parity

**Definition of done for implementation start:**

- Existing manifests still load.
- Existing plugin pipeline still runs without behavior drift.
- Runtime is ready for Wave D annotations and Wave C executor work.
