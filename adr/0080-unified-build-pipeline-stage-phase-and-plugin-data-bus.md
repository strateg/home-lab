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
4. `discover_plugin_manifests()` is procedural and outside plugin lifecycle.
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

1. `init`: `base.generator.effective_json`, `base.generator.effective_yaml`.
2. `run`: `base.generator.terraform_proxmox`, `base.generator.terraform_mikrotik`, `base.generator.ansible_inventory`, `base.generator.bootstrap_proxmox`, `base.generator.bootstrap_mikrotik`, `base.generator.bootstrap_orangepi`.
3. `post`: `base.generator.docs`, `base.generator.diagrams`.
4. `finalize`: `base.generator.artifact_manifest` (new plugin).

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
3. Plugin implementation is phase-aware via dedicated handlers (`on_init`, `on_pre`, ...) or dispatcher (`execute(ctx, stage, phase)`).
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

### 6. Contractual Publish/Subscribe Data Bus (Normative)

`publish/subscribe` remains the transport but becomes declared and validated.

#### 6.1 Manifest Contract

Manifest fields:

1. `produces` with `key`, `schema_ref` (optional), `scope` (`stage_local|pipeline_shared`), `description`.
2. `consumes` with `from_plugin`, `key`, `required`, `schema_ref` (optional).

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

## Migration Plan (AS-IS -> Target)

### 9.1 Critical Path

`Wave A -> Wave B -> Wave C -> Wave E -> Wave E.1 -> Wave F -> Wave G -> Wave H`

`Wave D` runs in parallel with `Wave B` after schema/types are available.

### 9.2 Gap-to-Wave Closure Map

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

### 9.3 Wave A - Baseline and Inventory Freeze

Goal: freeze current behavior before lifecycle refactor.

Tasks:

1. Freeze plugin inventory baseline from discovered manifests (57 plugins / 7 manifests at ADR update time).
2. Snapshot execution order and published keys for `production` and `modeled`.
3. Freeze generated outputs and diagnostics for parity tests.

Gate:

1. Existing suites green.
2. Baseline snapshots approved.

### 9.4 Wave B - Kernel and Schema Foundations

Goal: add stage/phase/data-bus type contracts without behavior break.

Tasks:

1. Extend runtime `Stage` with `discover`, `assemble`, `build`.
2. Add `Phase` enum and canonical order.
3. Extend `PluginSpec` with `phase` and `when`.
4. Extend `PluginDiagnostic` with phase attribution.
5. Extend `PluginContext` with assemble/build fields.
6. Align manifest schema stage enum with runtime target (`discover|compile|validate|generate|assemble|build`).
7. Align manifest schema phase enum with ADR vocabulary (`init|pre|run|post|verify|finalize`), removing draft token `finished`.
8. Extend manifest schema with `phase`, `produces`, `consumes`, `when`.
9. Allocate `E800x/E810x/E820x/W800x` ranges.
10. Define order ranges for all six stages.
11. Keep backward compatibility defaults (`phase` omitted -> `run`; missing `produces/consumes` tolerated until Wave E/H).
12. Update contract tests to reflect aligned enums and add a loader test proving a `build` stage manifest can be loaded by runtime.

Gate:

1. Contract tests green.
2. Existing manifests load unchanged.
3. Schema and runtime accept the same stage/phase vocabulary (no `build`/`finished` drift).

### 9.5 Wave D - Manifest Phase Annotation (parallel with Wave B)

Goal: annotate explicit phase for all plugins in discovered manifests.

Tasks:

1. Apply section 4 phase mapping to all current plugins.
2. Add CI test: every plugin has explicit `phase`.
3. Preserve ADR 0074 ordering for generate.
4. Coordinate with ADR 0079 changes for docs/diagrams plugins.

Gate:

1. Schema/manifest tests green.
2. Parity tests green.

### 9.6 Wave C - Phase Executor and `when` Gating

Goal: run plugins by `stage -> phase -> DAG/order`.

Tasks:

1. Implement phase-aware executor.
2. Reject forward stage/phase dependencies at load time.
3. Guarantee `finalize` for all started stages.
4. Evaluate `when` predicates for `profiles`, `capabilities`, `pipeline_modes`, `changed_input_scopes` (stub).
5. Add `--trace-execution` canary to compare old/new execution traces.

Gate:

1. Stage/phase tests green.
2. Finalize-on-failure tests green.
3. Canary parity accepted.

### 9.7 Wave E - Data Bus Contract Enforcement

Goal: migrate pub/sub to declared `produces/consumes`.

Tasks:

1. Annotate high-value keys (`class_map`, `object_map`, `normalized_rows`, `catalog_ids`, `packs_map`, `generated_files`).
2. Enforce producer dependency, declared keys, temporal validity, and payload schema checks.
3. Emit `W800x` for undeclared usage during transition.

Gate:

1. No undeclared consume in CI for annotated keys.
2. Runtime validation tests green.

### 9.8 Wave E.1 - `base.generator.artifact_manifest`

Goal: implement missing generate/finalize plugin.

Tasks:

1. Add plugin at `generate/finalize` (order 390).
2. Emit `generated/<project>/artifact-manifest.json` with checksums and plugin attribution.
3. Publish `artifact_manifest_path` for build-stage consumers.

Gate:

1. Manifest file generated and validated.
2. Checksums verified in tests.

### 9.9 Wave F - Discover + Assemble Pluginization

Goal: remove procedural discovery and move assembly under lifecycle.

Tasks:

1. Implement `discover.init/pre/run/verify` plugins and retire bare discovery path.
2. Implement `assemble.run/verify/finalize` plugins.
3. Add assemble verify checks for overrides, local-input contracts, and secret leakage.

Gate:

1. `.work/native` and `dist/` parity with previous flow.
2. `E810x` diagnostics for failing verify checks.

### 9.10 Wave G - Build Pluginization

Goal: unify packaging/trust under plugin runtime.

Tasks:

1. Implement `build.run/verify/finalize` plugins.
2. Include lock/provenance/signature/SBOM checks.
3. Emit release manifest and checksum summary.

Gate:

1. Release pipeline green under pluginized build.
2. `E820x` diagnostics emitted correctly.

### 9.11 Wave H - Hard Cutover and Cleanup

Goal: complete contract hardening and remove transitional paths.

Tasks:

1. Promote undeclared pub/sub from `W800x` to `E800x`.
2. Remove legacy discovery and lifecycle bypass code paths.
3. Keep `--trace-execution` as debug flag or remove after two green cycles.
4. Update runbooks and developer documentation.

Gate:

1. All plugin suites green.
2. No legacy path reachable.
3. No undeclared pub/sub in CI.

## Required Test Additions

1. Kernel contract tests: stage/phase ordering, forward dependency rejection, finalize guarantee.
2. Schema tests: explicit phase, produces/consumes validity, discovery-root policy.
3. Integration tests: compile->validate and generate->assemble->build declared data-bus chains.
4. Regression tests: generated parity, assembled workspace parity, release package/trust parity.
5. CI conformance test: schema stage/phase enums must match runtime `Stage`/`Phase` enums.
6. Cutover checklist tests from `adr/0080-analysis/CUTOVER-CHECKLIST.md` become release gates.

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
11. `finalize` executes for any started stage, including failure paths.
12. Manifest schema and runtime share the same stage/phase vocabulary (`discover|...|build` and `init|...|finalize`).
13. Diagnostic ranges `E800x/E810x/E820x/W800x` are cataloged without overlap.
14. Hard cutover removes legacy discovery and undeclared pub/sub usage.

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
