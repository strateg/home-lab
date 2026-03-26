# ADR 0080 Cutover Checklist

**ADR:** `adr/0080-unified-build-pipeline-stage-phase-and-plugin-data-bus.md`
**Date:** 2026-03-26
**Status:** Proposed

---

## Purpose

Gate final activation of the unified lifecycle runtime and retirement of transitional paths.

Complete when all Waves A–H are done and all items below are verified.

---

## A. Stage and Phase Model

- [ ] Runtime `Stage` enum contains: `discover`, `compile`, `validate`, `generate`, `assemble`, `build`.
- [ ] Runtime `Phase` enum contains: `init`, `pre`, `run`, `post`, `verify`, `finalize` in canonical order.
- [ ] Runtime `PluginKind` contains: `compiler`, `validator_yaml`, `validator_json`, `generator`, `assembler`, `builder`.
- [ ] Execution order is `stage → phase → DAG/order` (not flat order within stage).
- [ ] Forward stage dependency is rejected at manifest load time with diagnostic.
- [ ] Forward phase dependency within same stage is rejected at manifest load time with diagnostic.
- [ ] Cycles in `depends_on` are hard load errors.

---

## B. Finalize Guarantee

- [ ] `finalize` phase executes for every stage that was started, even if `run` or `verify` raised an exception.
- [ ] `finalize` phase executes for every started stage in partial `--stages` runs (skipped stages emit no finalize).
- [ ] `finalize` plugins receive full diagnostic context from failed phases.
- [ ] Integration test: stage failure followed by `finalize` emission — passes.
- [ ] Integration test: `--stages compile,validate` run — `finalize` runs for compile and validate only.

---

## C. Plugin Phase Annotations

- [ ] Every plugin in base `plugins.yaml` has explicit `phase` field.
- [ ] Every plugin discovered from class-module manifests has explicit `phase` field.
- [ ] Every plugin discovered from object-module manifests has explicit `phase` field.
- [ ] Test `test_all_plugins_have_explicit_phase` passes across all discovered manifests.

---

## D. `when` Predicate Gating

- [ ] `when.profiles` gates plugin execution by `ctx.profile`.
- [ ] `when.capabilities` gates plugin execution by `ctx.capability_catalog`.
- [ ] `when.pipeline_modes` gates plugin execution by runtime pipeline mode.
- [ ] `when.changed_input_scopes` stub is present (full impl deferred to assemble stage).
- [ ] Plugin skipped by `when` emits informational diagnostic, not failure.

---

## E. Contractual Data Bus

- [ ] Plugin manifest schema accepts `produces` and `consumes` fields.
- [ ] Consumer plugin without `produces`/`consumes` emits `W800x` warning (transitional period).
- [ ] After Wave H: undeclared publish/subscribe emits `E800x` hard error.
- [ ] Consumer must declare producer in `depends_on` — enforced at runtime.
- [ ] Consumer can only subscribe to declared `produces` keys — enforced at runtime.
- [ ] Schema payload validation triggers for declared `schema_ref` entries.
- [ ] High-value keys annotated: `class_map`, `object_map`, `normalized_rows`, `catalog_ids`, `packs_map`, `generated_files`.
- [ ] All existing high-value keys default to `pipeline_shared` scope.
- [ ] `stage_local` keys are invalidated when their publishing stage ends.
- [ ] Subscription to `stage_local` key from a later stage is rejected with hard error.

---

## F. `base.generator.artifact_manifest`

- [ ] Plugin registered at `generate/finalize`, `order: 390`.
- [ ] Emits `generated/<project>/artifact-manifest.json` with per-file SHA checksums.
- [ ] Emits plugin attribution per artifact.
- [ ] Publishes `artifact_manifest_path` for `build.init` consumption.

---

## G. Assemble Stage

- [ ] `assemble.run` merges baseline artifacts with overrides and local inputs.
- [ ] `assemble.verify` checks override layering, local-input requirements, and secret-leak guard.
- [ ] `assemble.finalize` emits assembly manifest.
- [ ] Assembled `.work/native/` and `dist/` are at parity with previous workflows.
- [ ] Secret-leak guard catches test cases with mock unencrypted secrets.
- [ ] `E810x` diagnostics emitted by assemble verify plugins.

---

## H. Build Stage

- [ ] `build.run` produces release bundle.
- [ ] `build.verify` includes lock verification, provenance, signature, and SBOM checks.
- [ ] `base.build.sbom` emits SBOM in expected format.
- [ ] `build.finalize` emits release manifest with checksum list.
- [ ] `E820x` diagnostics emitted by build verify plugins.

---

## I. `discover` Stage

- [ ] `discover.init` loads all plugin manifests from module roots.
- [ ] `discover.pre` enforces framework/project boundary (ADR 0075).
- [ ] `discover.run` builds plugin DAG and validates for cycles.
- [ ] `discover.verify` runs capability catalog preflight.
- [ ] All `discover.*` plugins reside in base manifest only — not in class/object modules.
- [ ] Base manifest is the only pre-lifecycle procedural load; no other procedural manifest loading exists.
- [ ] `compiler_runtime.discover_plugin_manifests()` bare function is **absent** from codebase.
- [ ] `instances_root` is NOT scanned for plugin manifests (ADR 0071).

---

## J. PluginContext Extensions

- [ ] `PluginContext` contains `workspace_root`, `dist_root`, `assembly_manifest`.
- [ ] `PluginContext` contains `signing_backend`, `release_tag`, `sbom_output_dir`.
- [ ] Assemble plugins read `workspace_root`/`dist_root` from context, not hardcoded paths.

---

## K. Diagnostic Code Ranges

- [ ] `E800x` (discover errors) registered in `error-catalog.yaml`.
- [ ] `E810x` (assemble errors) registered in `error-catalog.yaml`.
- [ ] `E820x` (build errors) registered in `error-catalog.yaml`.
- [ ] `W800x` (data bus undeclared key warnings) registered in `error-catalog.yaml`.
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

- [ ] New `phase`, `produces`, `consumes`, `when` fields pass schema validation.
- [ ] All diagnostic codes conform to non-overlapping ranges.

### ADR 0074 (Generator Architecture)

- [ ] Existing generate-stage order ranges 190–399 are preserved.
- [ ] `artifact_manifest` at order 390 does not conflict with existing plugins.

### ADR 0075 (Framework/Project Separation)

- [ ] `discover.pre` enforces framework/project boundary check.

### ADR 0078 (Object-Module Plugins)

- [ ] Object/class module plugins are discovered and phase-annotated.

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
- [ ] `profile_restrictions` field absent from `PluginSpec` dataclass and manifest schema.
- [ ] No plugin manifests contain `profile_restrictions` entries.
- [ ] Operator runbooks updated.
- [ ] `CLAUDE.md` guidance updated if workflow commands changed.

## P. Phase Handler Backward Compatibility

- [ ] Existing plugins with `execute(ctx) -> PluginResult` only run unchanged through full pipeline.
- [ ] Registry dispatch: for `run` phase, `execute(ctx)` is called unless `on_run(ctx)` is defined.
- [ ] Registry dispatch: for non-`run` phases, `on_<phase>(ctx)` is called if defined; plugin is skipped if not.
- [ ] Plugin skipped on non-`run` phase returns empty `PluginResult` (no error).
- [ ] Regression test: all 47+ base manifest plugins produce identical output after phase handler dispatch change.

## Q. `when` Predicates

- [ ] `when.profiles` gates on `ctx.profile` — skipped plugins emit informational diagnostic, not failure.
- [ ] `when.capabilities` gates on `ctx.capability_catalog`.
- [ ] `when.pipeline_modes` gates on runtime pipeline mode.
- [ ] `when.changed_input_scopes` stub returns True (all scopes dirty) until full impl in Wave F.
- [ ] No `profile_restrictions` field accepted by schema (removed, redirected to `when.profiles`).

## R. Parallel Plugin Execution

- [ ] `PluginExecutionScope` data class exists and is `frozen=True` (immutable).
- [ ] `publish()` and `subscribe()` accept `PluginExecutionScope` as first argument.
- [ ] `_current_plugin_id` and `_allowed_dependencies` fields are removed from `PluginContext`.
- [ ] `_published_data` access is protected by `threading.Lock()`.
- [ ] `compiled_json` is deep-copied at compile stage boundary — read-only for later stages.
- [ ] At most one `compiled_json_owner: true` per `(stage, phase)` is allowed; violation is load error.
- [ ] Plugin instance cache is pre-loaded or lock-protected (no TOCTOU race).
- [ ] Per-plugin `config` is injected via `PluginExecutionScope`, not mutated on shared `PluginContext`.
- [ ] Generator output path non-overlap is validated at load time using `produces` declarations.
- [ ] `--parallel-plugins` flag enables wavefront parallel executor.
- [ ] Wavefront executor: submits indegree-0 plugins to `ThreadPoolExecutor`, respects `order` for tie-breaking.
- [ ] Thread pool size: `min(cpu_count, wavefront_size)`, capped at 8.
- [ ] Sequential and parallel modes produce byte-identical outputs for all parity tests.
- [ ] Thread-safety unit tests pass: concurrent publish/subscribe with ≥8 threads, no data loss.
- [ ] `--parallel-plugins` promoted to default in Wave H (after regression parity verified).
