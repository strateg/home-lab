# ADR 0080: Unified Build Pipeline, Stage-Phase Lifecycle, and Contractual Plugin Data Bus

- Status: Proposed
- Date: 2026-03-26
- Depends on: ADR 0005, ADR 0027, ADR 0028, ADR 0050, ADR 0051, ADR 0052, ADR 0055, ADR 0056, ADR 0063, ADR 0065, ADR 0066, ADR 0069, ADR 0071, ADR 0074, ADR 0075, ADR 0076, ADR 0078

## Context

Early and mid-stack ADRs already define hard constraints:

1. Determinism and quality gates are non-negotiable (ADR 0005, ADR 0027, ADR 0074).
2. Stable tool boundaries and entrypoints are required (ADR 0028, ADR 0069).
3. Generated baseline must be separated from assembled execution roots (ADR 0050, ADR 0052, ADR 0056).
4. Manual overrides and local secrets are separate layers (ADR 0051, ADR 0055, ADR 0072).
5. Runtime is plugin-first and already exposes publish/subscribe (ADR 0063, ADR 0065, ADR 0069).
6. `instances_root` is data-only (ADR 0071), while plugin ownership is layered (ADR 0078).
7. Framework/project distribution verification is a build lifecycle concern (ADR 0075, ADR 0076).

Current runtime (AS-IS, 2026-03-26):

1. Stages in code are `compile`, `validate`, `generate` only.
2. Manifest execution is mostly order-based, phase semantics are implicit.
3. `publish/subscribe` keys are runtime conventions, not manifest contracts.
4. Build/packaging/attestation verification are partially outside the same plugin lifecycle.
5. Loaded plugin inventory is 57 plugins in 7 manifests:
   - `compile`: 7
   - `validate`: 40
   - `generate`: 10

This ADR unifies these concerns into one runtime contract.

## Decision

Adopt one plugin-first lifecycle model with explicit stages, universal phases, and a contractual inter-plugin data bus.

### 1. Terminology (Normative)

1. `Stage`: top-level pipeline segment with fixed global order.
2. `Phase`: lifecycle position inside a stage.
3. `Plugin`: unit of execution bound to exactly one stage and one phase.
4. `Data Bus`: typed publish/subscribe channel used for plugin-to-plugin exchange.

### 2. Global Stage Model (Normative)

Global stage order:

`discover -> compile -> validate -> generate -> assemble -> build`

Stage intent:

1. `discover`: load manifests, resolve framework/project context, preflight plugin graph.
2. `compile`: normalize and resolve canonical compiled model.
3. `validate`: enforce structural/domain/contracts on source and compiled data.
4. `generate`: emit deterministic baseline artifacts (`generated/...`).
5. `assemble`: create execution views (`.work/native/...`, `dist/...`) from baseline + overrides + local inputs.
6. `build`: package, verify trust/integrity, and publish release metadata/artifacts.

### 3. Universal Phase Model (Normative)

Every stage uses:

`init -> pre -> run -> post -> verify -> finalize`

Phase semantics:

1. `init`: data acquisition, cache/context setup, no business artifact mutation.
2. `pre`: fail-fast preconditions and governance checks.
3. `run`: primary stage logic.
4. `post`: derived outputs from successful run phase.
5. `verify`: contract validation of stage outputs.
6. `finalize`: manifests/reports/cleanup; MUST run for any started stage.

### 4. Initial Phase Assignment for Existing Plugins (Normative Migration Target)

#### 4.1 Compile

1. `init`: `base.compiler.module_loader`, `base.compiler.model_lock_loader`, `base.compiler.annotation_resolver`, `base.compiler.capability_contract_loader`
2. `run`: `base.compiler.instance_rows`, `base.compiler.capabilities`
3. `finalize`: `base.compiler.effective_model`

#### 4.2 Validate

1. `pre`: `base.validator.governance_contract`, `base.validator.foundation_layout`, `base.validator.foundation_include_contract`, `base.validator.foundation_file_placement`
2. `run`: all validator_json domain checks, including object/class validators (`object_*`, `class_router.*`)
3. `post`: `base.validator.capability_contract`, `base.validator.instance_placeholders`

#### 4.3 Generate

1. `init`: `base.generator.effective_json`, `base.generator.effective_yaml`
2. `run`: `base.generator.terraform_proxmox`, `base.generator.terraform_mikrotik`, `base.generator.ansible_inventory`, `base.generator.bootstrap_proxmox`, `base.generator.bootstrap_mikrotik`, `base.generator.bootstrap_orangepi`
3. `post`: `base.generator.docs`, `base.generator.diagrams`
4. `finalize`: `base.generator.artifact_manifest` (new)

#### 4.4 Assemble (new)

1. `run`: assembly of native/dist execution roots
2. `verify`: assembled root contract checks (override layering, local-input requirements, secret-leak guards)
3. `finalize`: assembly manifest and summary

#### 4.5 Build (new)

1. `run`: package/bundle creation
2. `verify`: lock, signature, provenance, SBOM verification
3. `finalize`: release manifest, checksums, result summary

### 5. Smart Plugin Model (Normative)

Plugins are phase-aware and can react to lifecycle position.

Required runtime behavior:

1. Plugin declares explicit `stage` and `phase` in manifest (`phase` default is `run` for compatibility).
2. Kernel executes by stage, then phase, then DAG/order.
3. Plugin implementation is phase-aware:
   - either dedicated handlers (`on_init`, `on_pre`, ...),
   - or `execute(ctx, stage, phase)` dispatcher.
4. Optional `when` predicates may gate execution by profile, pipeline mode, capabilities, or changed-input scopes.

### 6. Contractual Publish/Subscribe Data Bus (Normative)

`publish/subscribe` remains the transport but becomes declared and validated.

#### 6.1 Manifest contract

New plugin manifest fields:

1. `produces`:
   - `key`
   - `schema_ref` (optional)
   - `scope` (`stage_local|pipeline_shared`)
   - `description`
2. `consumes`:
   - `from_plugin`
   - `key`
   - `required` (bool)
   - `schema_ref` (optional expected schema)

#### 6.2 Runtime enforcement

1. Consumer MUST include producer in `depends_on`.
2. Consumer MUST subscribe only to declared `produces`.
3. Subscription is allowed only to already-completed producer executions:
   - earlier stage, or
   - same stage and earlier phase (same phase allowed only after producer completion).
4. Missing required payload is hard error.
5. Payload schema validation is enforced when `schema_ref` is declared.

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

### 7. Dependency and Ordering Rules (Normative)

1. No forward-stage dependency is allowed.
2. No forward-phase dependency is allowed in same stage.
3. Cycles are hard load errors.
4. `order` remains deterministic tiebreaker inside stage+phase.
5. `finalize` MUST run for any started stage.

### 8. Artifact Ownership Rules (Normative)

1. `generate` writes only baseline artifacts.
2. `assemble` writes execution views only.
3. `build` writes release/package/trust outputs only.
4. Secret-bearing outputs MUST NOT be written to baseline roots.

## Detailed Migration Plan (Current Code -> Target Schema)

### Wave A - Baseline and Inventory Freeze

Goal: freeze current behavior before lifecycle refactor.

Changes:

1. Snapshot current plugin inventory and execution order.
2. Add regression fixtures for generated outputs and diagnostics.
3. Add runtime inventory fixture for publish/subscribe key usage.

Gate:

1. Existing test suite green.
2. Baseline artifact snapshots approved.

### Wave B - Kernel Type Extensions

Goal: add stage/phase primitives without behavior break.

Primary files:

1. `topology-tools/kernel/plugin_base.py`
2. `topology-tools/kernel/plugin_registry.py`
3. `topology-tools/schemas/plugin-manifest.schema.json`

Tasks:

1. Extend `Stage` with `discover`, `assemble`, `build`.
2. Add `Phase` enum and canonical phase order.
3. Extend `PluginSpec` with `phase`.
4. Extend `PluginDiagnostic` with `phase`.
5. Keep default `phase=run` compatibility.

Gate:

1. Contract/unit tests green.
2. Existing manifests load unchanged.

### Wave C - Stage/Phase Executor Refactor

Goal: execute plugins by stage -> phase -> DAG order.

Primary files:

1. `topology-tools/kernel/plugin_registry.py`
2. `topology-tools/compile-topology.py`
3. `topology-tools/compiler_runtime.py`

Tasks:

1. Replace stage-only execution loop with phase-aware execution.
2. Enforce forward stage/phase dependency rejection.
3. Keep fail-fast semantics for compile critical paths.
4. Enforce finalize execution for started stages.

Gate:

1. Stage/phase order tests green.
2. Diagnostics parity with baseline accepted.

### Wave D - Manifest Phase Annotation (57 plugins)

Goal: explicitly annotate phases for all current plugins.

Primary files:

1. `topology-tools/plugins/plugins.yaml`
2. `topology/class-modules/**/plugins.yaml`
3. `topology/object-modules/**/plugins.yaml`

Tasks:

1. Add explicit `phase` to all entries according to section 4.
2. Preserve deterministic order compatibility (ADR 0074 generate ranges).
3. Add tests that every plugin has explicit phase.

Gate:

1. Manifest schema tests green.
2. Execution order/parity tests green.

### Wave E - Data Bus Contract Upgrade

Goal: migrate publish/subscribe from implicit keys to declared contracts.

Primary files:

1. `topology-tools/schemas/plugin-manifest.schema.json`
2. `topology-tools/kernel/plugin_registry.py`
3. plugins that publish/subscribe data in compile/validate/generate

Tasks:

1. Add `produces`/`consumes` to schema.
2. Add runtime checks for undeclared publish/subscribe.
3. Add schema payload validation hooks for declared `schema_ref`.
4. Annotate high-value keys first (`class_map`, `object_map`, `normalized_rows`, `catalog_ids`, `packs_map`).

Gate:

1. No undeclared consume in CI.
2. No undeclared produced key usage in CI.

### Wave F - Assemble Stage Pluginization

Goal: move execution-root assembly under plugin lifecycle.

Primary files:

1. New assemble plugins under `topology-tools/plugins/assemblers/` (or equivalent)
2. `topology-tools/compile-topology.py`
3. `topology-tools/compiler_runtime.py`

Tasks:

1. Implement `assemble.run` for native/dist workspace assembly.
2. Implement `assemble.verify` checks for override/local-input/secrets contract.
3. Implement `assemble.finalize` manifest emission.

Gate:

1. `.work/native` and `dist` parity with existing workflows.
2. Security checks green.

### Wave G - Build Stage Pluginization

Goal: unify packaging and trust verification in plugin runtime.

Primary files:

1. New build plugins under `topology-tools/plugins/build/`
2. framework lock and distribution helpers integration points

Tasks:

1. `build.run`: package bundle plugin.
2. `build.verify`: lock/provenance/signature/SBOM plugins.
3. `build.finalize`: release manifest/checksum plugin.

Gate:

1. Release pipeline passes with pluginized build stage.
2. `E78xx` family diagnostics emitted by stage plugins.

### Wave H - Cleanup and Hard-Cutover

Goal: remove transitional ownership flags and legacy branches.

Primary files:

1. `topology-tools/compiler_ownership.py`
2. `topology-tools/compiler_plugin_context.py`
3. compatibility paths in orchestrator/runtime

Tasks:

1. Remove legacy ownership toggles after parity proof.
2. Remove dead code paths bypassing plugin lifecycle.
3. Finalize docs and operator runbooks.

Gate:

1. All plugin contract/integration/regression suites green.
2. No legacy runtime paths reachable in CI.

## Acceptance Criteria

1. Stage order is implemented as `discover -> compile -> validate -> generate -> assemble -> build`.
2. Universal phase order is implemented for each stage.
3. All existing plugins have explicit phase.
4. Forward stage/phase dependencies are rejected at manifest load.
5. Data bus `produces/consumes` contracts are supported and validated.
6. Assemble and build stages are executed via plugin registry.
7. Finalize phase runs for all started stages and emits manifests/reports.

## Risks and Mitigations

1. Risk: lifecycle refactor changes execution ordering subtly.
   - Mitigation: baseline snapshots + strict parity gates.
2. Risk: manifest migration mistakes.
   - Mitigation: automated phase-contract tests and linting.
3. Risk: undeclared data bus coupling breaks plugins.
   - Mitigation: staged adoption of `produces/consumes` with compatibility fallback window.
4. Risk: build pluginization impacts release flow.
   - Mitigation: dual-path canary period and release dry-runs before hard cutover.

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
- `adr/0074-v5-generator-architecture.md`
- `adr/0075-framework-project-separation.md`
- `adr/0076-framework-distribution-and-multi-repository-extraction.md`
- `adr/0078-object-module-local-template-layout.md`
