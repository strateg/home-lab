# ADR 0080 Implementation Plan

**ADR:** `adr/0080-unified-build-pipeline-stage-phase-and-plugin-data-bus.md`
**Date:** 2026-03-26
**Status:** Accepted
**Gap Analysis:** `adr/0080-analysis/GAP-ANALYSIS.md`
**Cutover Checklist:** `adr/0080-analysis/CUTOVER-CHECKLIST.md`

---

## Goal

Unify the plugin runtime around a single lifecycle model with:

1. Six explicit stages: `discover → compile → validate → generate → assemble → build`
2. Universal phase order within each stage: `init → pre → run → post → verify → finalize`
3. Declared `produces`/`consumes` contracts on the publish/subscribe data bus
4. `assemble` and `build` stages executed via plugin registry
5. `finalize` guaranteed to run for any started stage

---

## Primary Files

| File | Role |
|------|------|
| `topology-tools/kernel/plugin_base.py` | `Stage`, `Phase` enums; `PluginContext` extensions |
| `topology-tools/kernel/plugin_registry.py` | Phase-aware executor, `when` predicate evaluation |
| `topology-tools/compiler_runtime.py` | Discovery pluginization |
| `topology-tools/compile-topology.py` | Thin orchestrator wiring |
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
Wave E  (data bus contracts)  +  Wave E.1  (artifact_manifest plugin)
  ↓
Wave F  (assemble stage)
  ↓
Wave G  (build stage)
  ↓
Wave H  (cleanup and hard cutover)
```

Wave D is **parallel with Wave B** — annotations require only schema/PluginSpec changes
from Wave B, not the new executor from Wave C.

---

## P0 Alignment Blockers (must be closed in Wave B)

1. Runtime `Stage` enum currently supports only `compile|validate|generate`, while schema already accepts `build`.
2. Schema phase enum uses draft token `finished`, while target lifecycle token is `finalize`.
3. Runtime does not parse/store `phase` yet (`PluginSpec` is stage-only).
4. Existing contract tests currently assert draft schema values and must be realigned to target ADR vocabulary.

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
6. Align schema stage enum to runtime target: `discover`, `compile`, `validate`, `generate`, `assemble`, `build`.
7. Align schema phase enum to runtime target: `init`, `pre`, `run`, `post`, `verify`, `finalize` (remove draft token `finished`).
8. Add `produces`/`consumes` fields to manifest schema (unenforced, structure only).
9. Allocate diagnostic code ranges in `error-catalog.yaml`:
   - `E800x`: discover stage errors
   - `E810x`: assemble stage errors
   - `E820x`: build stage errors
   - `W800x`: data bus undeclared key warnings (transitional)
10. Define normative `order` ranges per stage:
   - `discover`: 10–89
   - `compile`: 30–89 (preserve)
   - `validate`: 90–189 (preserve)
   - `generate`: 190–399 (preserve, per ADR 0074)
   - `assemble`: 400–499
   - `build`: 500–599
11. Keep `phase=RUN` default — existing manifests load unchanged.
12. Update `tests/plugin_contract/test_manifest.py` to assert aligned stage/phase enums and add test that a manifest with `stage: build` loads successfully in runtime.

**Gate:**

- Contract/unit tests green.
- Existing manifests load unchanged.
- Schema validation passes with and without `phase`/`produces`/`consumes`.
- Schema/runtime vocabulary lock proven by tests (no `build`/`finished` drift).

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
   - `init`: `effective_json`, `effective_yaml`
   - `run`: terraform_proxmox, terraform_mikrotik, ansible_inventory, bootstrap_*
   - `post`: docs, diagrams
   - `finalize`: `artifact_manifest` (placeholder — implemented in Wave E.1)

4. Add test: every plugin in every discovered manifest must have an explicit `phase` field.

**Gate:**

- Manifest schema tests green.
- Execution order/parity tests green (phase field ignored by current executor — backward compat).
- Every plugin has explicit `phase` in manifest.

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
4. Implement `when` predicate evaluation:
   - `profiles`: gate on `ctx.profile`
   - `capabilities`: gate on `ctx.capability_catalog`
   - `pipeline_modes`: gate on runtime pipeline mode flag
   - `changed_input_scopes`: gate on dirty-input scope detection (stub — full impl in Wave F)
5. Add canary mode: `--trace-execution` flag that logs stage/phase/plugin execution sequence
   for comparison against Wave A baseline before hard cutover.
6. Wrap `compiler_runtime.discover_plugin_manifests()` call in a `discover.run` shim
   (full pluginization deferred to Wave F).

**Gate:**

- Stage/phase order tests green.
- `finalize` runs in all failure scenarios (unit tests).
- Diagnostics parity with Wave A baseline accepted.
- `when` predicate gates pass for profile, capability, and pipeline_mode cases.

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
3. Annotate high-value keys first:
   - `base.compiler.module_loader` → `produces: class_map, object_map`
   - `base.compiler.instance_rows` → `produces: normalized_rows`
   - `base.compiler.capability_contract_loader` → `produces: catalog_ids, packs_map`
   - `base.generator.*` → `produces: generated_dir, generated_files, <family>_files`
4. Add `consumer must include producer in depends_on` enforcement.

**Gate:**

- No undeclared consume in CI for annotated high-value keys.
- `W800x` warnings emitted for remaining unannotated plugins.
- Schema payload validation passes for declared `schema_ref` entries.

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
4. Complete pluginization of `discover_plugin_manifests()`:
   - `discover.init`: load manifests from all module roots.
   - `discover.pre`: framework/project boundary check (ADR 0075).
   - `discover.run`: build plugin DAG, validate cycles.
   - `discover.verify`: capability catalog preflight.
   - stop scanning `instances_root` for plugin manifests (ADR 0071 data-only policy).

**Gate:**

- `.work/native` and `dist/` parity with existing assembly workflows.
- Secret-leak guard catches test cases with mock unencrypted secrets.
- `E810x` diagnostics emitted correctly.

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
4. Remove any dead code paths that bypass plugin lifecycle.
5. Remove `--trace-execution` canary mode or promote to permanent debug flag.
6. Finalize operator runbooks and update CLAUDE.md guidance.

**Gate:**

- All plugin contract/integration/regression suites green.
- No `W800x` warnings in CI — all undeclared pub/sub resolved.
- No legacy runtime paths reachable.
- `discover_plugin_manifests()` function absent from codebase.

---

## Acceptance Criteria Summary

Mapped to ADR 0080 Section plus additions from gap analysis:

| # | Criterion | Wave |
|---|-----------|------|
| 1 | Stage order `discover → compile → validate → generate → assemble → build` implemented | C |
| 2 | Universal phase order `init → pre → run → post → verify → finalize` per stage | C |
| 3 | All plugins have explicit `phase` annotation | D |
| 4 | Forward stage/phase dependencies rejected at manifest load | C |
| 5 | `produces`/`consumes` contracts supported and validated | E |
| 6 | `assemble` and `build` stages execute via plugin registry | F/G |
| 7 | `finalize` runs for all started stages and emits manifests/reports | C |
| 8 | `when` predicate gates work for profile/capability/pipeline_mode | C |
| 9 | `discover` stage replaces `compiler_runtime.discover_plugin_manifests()` | F |
| 10 | Diagnostic code ranges E800x–E820x registered in error-catalog.yaml | B |
| 11 | `PluginContext` contains assemble/build fields | B |
| 12 | `base.generator.artifact_manifest` implemented and emitting checksums | E.1 |
| 13 | Order ranges defined and documented for all 6 stages | B |
| 14 | Schema and runtime use identical stage/phase enums (`discover..build`, `init..finalize`) | B |
