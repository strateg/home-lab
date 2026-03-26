# ADR 0080 Cutover Checklist

**ADR:** `adr/0080-unified-build-pipeline-stage-phase-and-plugin-data-bus.md`
**Date:** 2026-03-26
**Status:** Accepted

---

## Purpose

Gate final activation of the unified lifecycle runtime and retirement of transitional paths.

Complete when all Waves A–H are done and all items below are verified.

---

## A. Stage and Phase Model

- [x] Runtime `Stage` enum contains: `discover`, `compile`, `validate`, `generate`, `assemble`, `build`.
- [x] Runtime `Phase` enum contains: `init`, `pre`, `run`, `post`, `verify`, `finalize` in canonical order.
- [x] Runtime `PluginKind` contains: `compiler`, `validator_yaml`, `validator_json`, `generator`, `assembler`, `builder`.
- [x] Execution order is `stage → phase → DAG/order` (not flat order within stage).
- [x] Forward stage dependency is rejected at manifest load time with diagnostic.
- [x] Forward phase dependency within same stage is rejected at manifest load time with diagnostic.
- [x] Cycles in `depends_on` are hard load errors.

---

## B. Finalize Guarantee

- [x] `finalize` phase executes for every stage that was started, even if `run` or `verify` raised an exception.
- [x] `finalize` phase executes for every started stage in partial `--stages` runs (skipped stages emit no finalize).
- [ ] `finalize` plugins receive full diagnostic context from failed phases.
- [ ] Integration test: stage failure followed by `finalize` emission — passes.
- [ ] Integration test: `--stages compile,validate` run — `finalize` runs for compile and validate only.

---

## C. Plugin Phase Annotations

- [x] Every plugin in base `plugins.yaml` has explicit `phase` field.
- [x] Every plugin discovered from class-module manifests has explicit `phase` field.
- [x] Every plugin discovered from object-module manifests has explicit `phase` field.
- [x] Test `test_all_plugins_have_explicit_phase` passes across all discovered manifests.

---

## D. `when` Predicate Gating

- [x] `when.profiles` gates plugin execution by `ctx.profile`.
- [x] `when.capabilities` gates plugin execution by `ctx.capability_catalog`.
- [x] `when.pipeline_modes` gates plugin execution by runtime pipeline mode.
- [x] `when.changed_input_scopes` stub is present (full impl deferred to assemble stage).
- [x] Plugin skipped by `when` emits informational diagnostic, not failure.

---

## E. Contractual Data Bus

- [x] Plugin manifest schema accepts `produces` and `consumes` fields.
- [x] Consumer plugin without `produces`/`consumes` emits `W800x` warning (transitional period).
- [x] After Wave H: undeclared publish/subscribe emits `E800x` hard error.
- [x] Consumer must declare producer in `depends_on` — enforced at runtime.
- [x] Consumer can only subscribe to declared `produces` keys — enforced at runtime.
- [x] Schema payload validation triggers for declared `schema_ref` entries.
- [x] High-value keys annotated: `class_map`, `object_map`, `normalized_rows`, `catalog_ids`, `packs_map`, `generated_files`.
- [x] All existing high-value keys default to `pipeline_shared` scope.
- [x] `stage_local` keys are invalidated when their publishing stage ends.
- [x] Subscription to `stage_local` key from a later stage is rejected with hard error.

---

## F. `base.generator.artifact_manifest`

- [x] Plugin registered at `generate/finalize`, `order: 390`.
- [x] Emits `generated/<project>/artifact-manifest.json` with per-file SHA checksums.
- [x] Emits plugin attribution per artifact.
- [x] Publishes `artifact_manifest_path` for `build.init` consumption.

---

## G. Assemble Stage

- [x] `assemble.run` merges baseline artifacts with overrides and local inputs.
- [x] `assemble.verify` checks override layering, local-input requirements, and secret-leak guard.
- [x] `assemble.finalize` emits assembly manifest.
- [ ] Assembled `.work/native/` and `dist/` are at parity with previous workflows.
- [ ] Secret-leak guard catches test cases with mock unencrypted secrets.
- [x] `E810x` diagnostics emitted by assemble verify plugins.

---

## H. Build Stage

- [x] `build.run` produces release bundle.
- [x] `build.verify` includes lock verification, provenance, signature, and SBOM checks.
- [x] `base.build.sbom` emits SBOM in expected format.
- [x] `build.finalize` emits release manifest with checksum list.
- [x] `E820x` diagnostics emitted by build verify plugins.

---

## I. `discover` Stage

- [ ] `discover.init` loads all plugin manifests from module roots.
- [ ] `discover.pre` enforces framework/project boundary (ADR 0075).
- [x] `discover.run` builds plugin DAG and validates for cycles.
- [x] `discover.verify` runs capability catalog preflight.
- [ ] All `discover.*` plugins reside in base manifest only — not in class/object modules.
- [ ] Base manifest is the only pre-lifecycle procedural load; no other procedural manifest loading exists.
- [ ] `compiler_runtime.discover_plugin_manifests()` bare function is **absent** from codebase.
- [ ] `instances_root` is NOT scanned for plugin manifests (ADR 0071).

---

## J. PluginContext Extensions

- [x] `PluginContext` contains `workspace_root`, `dist_root`, `assembly_manifest`.
- [x] `PluginContext` contains `signing_backend`, `release_tag`, `sbom_output_dir`.
- [x] Assemble plugins read `workspace_root`/`dist_root` from context, not hardcoded paths.

---

## K. Diagnostic Code Ranges

- [x] `E800x` (discover errors) registered in `error-catalog.yaml`.
- [x] `E810x` (assemble errors) registered in `error-catalog.yaml`.
- [x] `E820x` (build errors) registered in `error-catalog.yaml`.
- [x] `W800x` (data bus undeclared key warnings) registered in `error-catalog.yaml`.
- [ ] No overlap with existing code ranges E60xx–E97xx.

---

## L. Order Ranges

- [ ] Order range documentation added to ADR or tooling README:
  - `discover`: 10–89
  - `compile`: 30–89
  - `validate`: 90–189
  - `generate`: 190–399
  - `assemble`: 400–499
  - `build`: 500–599
- [ ] No existing plugin uses order values in `assemble` or `build` ranges.

---

## M. Early ADR Guardrails

### ADR 0005 (Determinism)

- [ ] Generated artifact ordering is deterministic across repeated runs with new executor.
- [ ] No noisy diffs on stable inputs after phase-aware execution.

### ADR 0027 (Quality Gates)

- [ ] Render/validation quality gates remain enabled in plugin-first path.

### ADR 0065 (Plugin API Contract)

- [x] New `phase`, `produces`, `consumes`, `when` fields pass schema validation.
- [ ] All diagnostic codes conform to non-overlapping ranges.

### ADR 0074 (Generator Architecture)

- [x] Existing generate-stage order ranges 190–399 are preserved.
- [x] `artifact_manifest` at order 390 does not conflict with existing plugins.

### ADR 0075 (Framework/Project Separation)

- [ ] `discover.pre` enforces framework/project boundary check.

### ADR 0078 (Object-Module Plugins)

- [x] Object/class module plugins are discovered and phase-annotated.

---

## N. Regression Parity

- [ ] Effective JSON parity on `production` profile before/after executor refactor.
- [ ] Effective JSON parity on `modeled` profile.
- [ ] Diagnostics parity (codes + severities) on baseline fixtures.
- [ ] Published key inventory unchanged for compile/validate/generate stages.

---

## O. Legacy Path Retirement

- [ ] No `W800x` warnings in CI (all pub/sub annotated).
- [ ] `compiler_runtime.discover_plugin_manifests()` deleted.
- [ ] No dead code paths bypassing plugin lifecycle exist in `compile-topology.py`.
- [x] `profile_restrictions` field absent from `PluginSpec` dataclass and manifest schema.
- [x] No plugin manifests contain `profile_restrictions` entries.
- [ ] Operator runbooks updated.
- [ ] `CLAUDE.md` guidance updated if workflow commands changed.

## P. Phase Handler Backward Compatibility

- [x] Existing plugins with `execute(ctx, stage) -> PluginResult` only run unchanged through full pipeline.
- [x] Registry dispatch: for `run` phase, `execute(ctx, stage)` is called unless `on_run(ctx, stage)` is defined.
- [x] Registry dispatch: for non-`run` phases, `on_<phase>(ctx, stage)` is called if defined; plugin is skipped if not.
- [x] Plugin skipped on non-`run` phase returns empty `PluginResult` (no error).
- [ ] Regression test: all 47+ base manifest plugins produce identical output after phase handler dispatch change.

## Q. `when` Predicates

- [x] `when.profiles` gates on `ctx.profile` — skipped plugins emit informational diagnostic, not failure.
- [x] `when.capabilities` gates on `ctx.capability_catalog`.
- [x] `when.pipeline_modes` gates on runtime pipeline mode.
- [x] `when.changed_input_scopes` stub returns True (all scopes dirty) until full impl in Wave F.
- [x] No `profile_restrictions` field accepted by schema (removed, redirected to `when.profiles`).

## R. Parallel Plugin Execution

- [x] `PluginExecutionScope` data class exists and is `frozen=True` (immutable).
- [x] `publish()` and `subscribe()` keep their plugin-facing signatures unchanged and resolve execution identity from per-worker `contextvars`.
- [x] `_current_plugin_id` and `_allowed_dependencies` fields are removed from `PluginContext`.
- [x] `ctx.active_config` exposes per-plugin immutable config snapshot from `PluginExecutionScope`.
- [x] `_published_data` access is protected by `threading.Lock()`.
- [x] `compiled_json` is deep-copied at compile stage boundary — read-only for later stages.
- [x] At most one `compiled_json_owner: true` per `(stage, phase)` is allowed; violation is load error.
- [x] Plugin instance cache is pre-loaded or lock-protected (no TOCTOU race).
- [x] Per-plugin config is resolved from `PluginExecutionScope`; shared `PluginContext.config` is not mutated per invocation.
- [x] Generator output path non-overlap is validated at load time using `produces` declarations.
- [x] `--parallel-plugins` flag enables wavefront parallel executor.
- [x] Wavefront executor: submits indegree-0 plugins to `ThreadPoolExecutor`, respects `order` for tie-breaking.
- [x] Thread pool size: `min(cpu_count, wavefront_size)`, capped at 8.
- [x] Sequential and parallel modes produce byte-identical outputs for all parity tests.
- [x] Thread-safety unit tests pass: concurrent publish/subscribe with ≥8 threads, no data loss.
- [x] Diagnostics and plugin results are emitted in deterministic order (`stage`, `phase`, `order`, `plugin_id`) across repeated parallel runs.
- [x] Timeout in parallel mode fails only the timed-out plugin, skips its dependants in the same phase, and still preserves stage-level `finalize`.
- [ ] `--parallel-plugins` promoted to default in Wave H (after regression parity verified).
