# ADR 0082: Plugin Module-Pack Composition and Index-First Discovery Analysis

- Status: Accepted
- Date: 2026-03-29
- Updated: 2026-04-03
- Depends on: ADR 0063, ADR 0078, ADR 0080, ADR 0081

## Context

ADR 0063 and ADR 0078 established plugin microkernel boundaries and class/object plugin co-location.
ADR 0081 established artifact-first framework consumption and deterministic discovery chain
(`kernel -> framework -> class -> object -> project`).

Current runtime already supports:

1. Co-located class/object plugin manifests.
2. Deterministic multi-level discovery.
3. `module-index.yaml` + fallback scan behavior.
4. Single framework runtime artifact distribution.

The analysis phase completed and current repository state was re-evaluated in
`adr/0082-analysis/ANALYSIS.md`.

## Decision

Adopt **Option A+** now:

1. Keep current structure and single framework runtime artifact contract (ADR 0081).
2. Treat `topology/module-index.yaml` as an authoritative contract for class/object plugin manifests.
3. Enforce bidirectional index consistency checks (`index -> filesystem`, `filesystem -> index`) in validation and compiler runtime diagnostics.
4. Keep module-pack assembly (Option B) and schema-v2 metadata expansion (Option C) deferred until explicit growth gates are hit.

Non-negotiable constraints remain:

1. **Developer/AI workspace must stay monorepo-first and unified** (`topology/`, `topology-tools/`, `projects/`).
2. **Project consumption remains one runtime framework artifact** (ADR 0081 contract).
3. **Plugin co-location remains mandatory** for class/object ownership boundaries.
4. **Discovery contract stays deterministic and additive** with global plugin ID uniqueness.
5. **No behavior-breaking runtime cutover** is allowed while module count stays below trigger thresholds.

Growth gates for reconsidering Option C/B:

1. Active module manifests exceed 15.
2. Per-module release cadence/versioning is required.
3. Module-level integrity provenance is repeatedly required beyond framework lock scope.

## Consequences

Positive:

1. Avoids premature structural split and assembly complexity.
2. Preserves ADR 0081 runtime artifact contract.
3. Makes module-index drift detectable and blocking in validation/runtime.

Trade-offs:

1. Per-module versioning remains deferred.
2. Metadata-rich module-pack model is postponed until growth triggers.

## References

- ADR 0063: `adr/0063-plugin-microkernel-for-compiler-validators-generators.md`
- ADR 0078: `adr/0078-object-module-local-template-layout.md`
- ADR 0080: `adr/0080-unified-build-pipeline-stage-phase-and-plugin-data-bus.md`
- ADR 0081: `adr/0081-framework-runtime-artifact-and-1-n-project-repository-model.md`
- ADR 0082 analysis refresh: `adr/0082-analysis/ANALYSIS.md`
- Discovery implementation: `topology-tools/plugin_manifest_discovery.py`
- Topology module index: `topology/module-index.yaml`
