# ADR 0069 Implementation Plan

**ADR:** `adr/0069-plugin-first-compiler-refactor-and-thin-orchestrator.md`
**Date:** 2026-03-10
**Status:** In Progress (WS1 implemented, WS2 started)
**Cutover Checklist:** `adr/0069-analysis/CUTOVER-CHECKLIST.md`

---

## Goal

Refactor `v5/topology-tools/compile-topology.py` into a thin orchestrator and move compile/validate/generate logic into plugins.

Target outcome:

1. `compile-topology.py` orchestrates stages only.
2. Effective model is assembled by compiler plugins.
3. Artifacts are emitted by generator plugins.
4. Legacy in-core branches are removed after parity gate.

---

## Current Baseline

Current issues:

1. Monolithic compiler (~2000+ LOC) mixes load/resolve/validate/emit.
2. Plugin system exists, but compile ownership is partial.
3. `Stage.GENERATE` is defined in kernel but not used by runtime pipeline.

Existing plugin assets:

- Compiler: `base.compiler.capabilities`
- Validators: references, model_lock, embedded_in, capability_contract, instance_placeholders
- No active generators in manifest

Inherited guardrails from earlier accepted ADRs:

1. ADR 0005: deterministic ordering in generated artifacts.
2. ADR 0027: render quality gates must remain part of default pipeline.
3. ADR 0028: top-level CLI compatibility entrypoints stay stable.
4. ADR 0046: generator modularity and testability principles are mandatory.
5. ADR 0050: artifact layout contracts must not drift.

---

## Refactor Workstreams

### WS1: Stage Wiring and Context Contract

Files:

- `v5/topology-tools/compile-topology.py`
- `v5/topology-tools/kernel/plugin_base.py`
- `v5/topology-tools/kernel/plugin_registry.py`

Tasks:

1. Ensure stage order is always `compile -> validate -> generate`.
2. Populate `ctx.compiled_json` before `validate` and `generate`.
3. Define stable context keys published by compiler plugins.

Exit criteria:

1. `Stage.GENERATE` executes in runtime.
2. Validators and generators consume same compiled model contract.

Progress note (2026-03-10):

1. `compile-topology.py` now executes plugin stages in order `compile -> validate -> generate` on successful runs.
2. `ctx.compiled_json` is populated before validate/generate stages.
3. Stage-order integration test added: `v5/tests/plugin_integration/test_parity_stage_order.py`.

### WS2: Compiler Plugins for Core Build Path

New plugin targets:

1. `base.compiler.module_loader`
2. `base.compiler.reference_resolver`
3. `base.compiler.effective_model`
4. `base.compiler.software_projection` (optional split)

Files:

- `v5/topology-tools/plugins/compilers/*.py`
- `v5/topology-tools/plugins/plugins.yaml`

Tasks:

1. Move class/object/index loading logic out of core.
2. Move instance row normalization/resolution out of core.
3. Move effective model assembly (`_build_effective`) to plugin.
4. Publish stable outputs through `ctx.publish(...)`.

Exit criteria:

1. Effective model can be fully assembled without calling legacy core builders.

Progress note (2026-03-10):

1. Added compiler plugin `base.compiler.effective_model`:
   - `v5/topology-tools/plugins/compilers/effective_model_compiler.py`
2. Plugin is registered in manifest:
   - `v5/topology-tools/plugins/plugins.yaml`
3. Candidate compiled model is published via:
   - `ctx.publish("effective_model_candidate", ...)`
   - `ctx.compiled_json = ...` (candidate during compile stage)
4. Integration test added:
   - `v5/tests/plugin_integration/test_effective_model_compiler.py`
5. Added runtime source selection flag:
   - CLI: `--pipeline-mode legacy|plugin-first`
   - `legacy`: core effective payload remains authoritative
   - `plugin-first`: output source switches to plugin `ctx.compiled_json`
6. Added parity drift diagnostic in legacy mode:
   - `W6901` when plugin candidate differs from legacy payload.
7. Added strict parity gate support:
   - CLI: `--parity-gate`
   - `E6902` on parity mismatch or gate misconfiguration.
8. Added initial generator plugin for effective YAML artifact:
   - `base.generator.effective_yaml`
   - `v5/topology-tools/plugins/generators/effective_yaml_generator.py`

### WS3: Validation Decomposition Completion

Files:

- `v5/topology-tools/plugins/validators/*.py`
- `v5/topology-tools/data/error-catalog.yaml`

Tasks:

1. Migrate remaining in-core validations to plugins:
   - refs and class/object compatibility
   - embedded OS rules
   - capability contract
   - model.lock checks
2. Keep one diagnostic code system in catalog.

Exit criteria:

1. Core validate methods are no longer required for feature parity.

### WS4: Generator Plugins and Artifact Emission

New generator targets:

1. `base.generator.effective_json`
2. `base.generator.effective_yaml`
3. `base.generator.diagnostics_report` (optional, if moving reporting too)

Files:

- `v5/topology-tools/plugins/generators/*.py` (new directory)
- `v5/topology-tools/plugins/plugins.yaml`

Tasks:

1. Emit `effective-topology.json` via generator plugin.
2. Add optional YAML artifact emission from same compiled model.
3. Keep output path policy controlled by CLI/config context.

Exit criteria:

1. No artifact files are emitted directly by legacy core branch.
2. Existing output roots and layout semantics remain ADR0050-compatible.

### WS5: Thin-Orchestrator Cutover

Files:

- `v5/topology-tools/compile-topology.py`

Tasks:

1. Remove superseded helper methods from core.
2. Keep only CLI + bootstrap + stage execution + exit codes.
3. Add compatibility mode flag only if parity gate is incomplete.

Exit criteria:

1. Core file size and complexity reduced substantially.
2. No direct business-rule validation in core.
3. Inherited ADR0005/0027/0028/0046/0050 guardrails pass checklist.

---

## Sequencing

1. WS1 (stage wiring contract)
2. WS2 (compiler build plugins)
3. WS3 (validation completion)
4. WS4 (generator plugins)
5. WS5 (cutover + cleanup)

---

## Sprint 1 Execution Package (Immediate)

Scope: WS1 only (stage wiring + context contract), no domain-rule migration.

Target file set:

1. `v5/topology-tools/compile-topology.py`
2. `v5/topology-tools/plugins/plugins.yaml` (only if temporary WS1 helper plugin is needed)
3. `v5/tests/plugin_integration/test_execution.py`
4. `v5/tests/plugin_integration/test_parity_stage_order.py` (new)

Mandatory WS1 outcomes:

1. `Stage.GENERATE` executes in runtime pipeline.
2. `ctx.compiled_json` is populated before validate/generate stages.
3. Stage order is deterministic and tested.
4. No behavior change in legacy output paths yet (no WS2/WS4 scope creep).

---

## Parity and Quality Gates

Mandatory parity gates before full cutover:

1. Effective JSON parity vs legacy path on `production`, `modeled`, `test-real`.
2. Diagnostics parity for key codes and severity.
3. Plugin test suite green:
   - `v5/tests/plugin_contract/*`
   - `v5/tests/plugin_integration/*`
   - new parity tests for compiler/generator plugins.
4. Deterministic output ordering parity (ADR0005).
5. Render validation/quality gate parity (ADR0027).

---

## Risks and Mitigation

1. Risk: behavior drift during staged migration.
   Mitigation: golden-file parity checks and dual-run comparison.
2. Risk: plugin dependency complexity.
   Mitigation: explicit `depends_on`, stable stage order, deterministic `order`.
3. Risk: diagnostics inconsistency.
   Mitigation: centralized `error-catalog.yaml` and regression snapshots.

---

## Definition of Done

1. `compile-topology.py` is an orchestrator, not domain logic container.
2. Effective model assembly is plugin-owned.
3. Generator plugins emit canonical artifacts (JSON + optional YAML).
4. Legacy core compile/validate/emit branches removed or permanently disabled.
5. CI validates plugin-first path as default.

Acceptance gating is defined in `adr/0069-plugin-first-compiler-refactor-and-thin-orchestrator.md` (`Status Promotion Rule`) and evidenced via `adr/0069-analysis/CUTOVER-CHECKLIST.md`.

---

## Compiled Model Contract (Normative)

To prevent silent drift between compiler/validator/generator plugins, `ctx.compiled_json` is versioned and validated.

Required metadata:

1. `compiled_model_version` (string, semantic version style; initial: `1.0`)
2. `compiled_at` (ISO8601 timestamp)
3. `compiler_pipeline_version` (string)
4. `source_manifest_digest` (string)

Contract rules:

1. Compiler plugins MUST publish `ctx.compiled_json` with `compiled_model_version`.
2. Validator/generator plugins MUST declare compatible model versions.
3. Minor version bump (`1.x -> 1.y`) is backward-compatible.
4. Major version bump (`1.x -> 2.0`) requires explicit migration note and parity re-baseline.
5. Runtime MUST fail fast on incompatible version ranges.

Recommended follow-up artifacts:

- Schema file: `v5/topology-tools/data/compiled-model-schema-v1.yaml`
- Contract tests: `v5/tests/plugin_contract/test_compiled_model_contract.py`

---

## Parity Specification (Normative)

Parity checks are required before full plugin-first cutover.

### Effective Model Parity

Compare plugin-first vs legacy outputs for `production`, `modeled`, `test-real`:

1. Strict structural equality after deterministic normalization:
   - sorted object keys,
   - stable list ordering where order is semantic,
   - normalized numeric/string scalar rendering where applicable.
2. No unresolved placeholders in either output.
3. Output path/layout remains ADR0050-compatible.

### Diagnostics Parity

Diagnostics comparison policy:

1. MUST match exactly:
   - `code`
   - `severity`
   - `entity/path` target (or equivalent location field)
2. MAY differ:
   - human-readable message wording
   - internal producer metadata
3. Ordering of diagnostics MUST be deterministic after normalization.
4. Any missing/extra diagnostic code is parity failure.

Recommended follow-up tests:

- `v5/tests/plugin_integration/test_parity_effective_model.py`
- `v5/tests/plugin_integration/test_parity_diagnostics.py`

---

## Rollback Protocol (Normative)

Rollback must be executable in one operational step during migration phases.

### Triggers

Rollback is mandatory if any of the following occurs on baseline fixtures:

1. Effective model parity failure.
2. Diagnostics parity failure (code/severity/path mismatch).
3. Determinism regression (noisy diffs on identical inputs).
4. Critical CLI contract break against ADR0028 workflows.
5. Quality-gate regression required by ADR0027.

### Mechanism

1. Keep explicit runtime switch during rollout:
   - `--pipeline-mode=legacy|plugin-first` (or equivalent config key).
2. Default may move to `plugin-first` only after parity gates are green.
3. Rollback action sets default back to `legacy` and opens blocking incident/task.

### Ownership and SLA

1. Cutover owner: topology-tools maintainer on duty.
2. Rollback decision window: immediate on gate failure.
3. Recovery expectation:
   - restore stable default path first,
   - investigate root cause second,
   - reattempt cutover only after green parity + checklist evidence.

---

## Scope Control (In/Out)

To limit migration risk:

In scope for ADR0069 implementation:

1. Thin orchestrator refactor.
2. Plugin ownership for compile/validate/generate pipeline.
3. Parity-based cutover and legacy branch retirement.

Out of scope (separate track unless required for parity):

1. New domain contracts unrelated to pluginization.
2. Non-essential feature additions in generators/validators.
3. Major data-model redesign beyond compiled-model versioning.
