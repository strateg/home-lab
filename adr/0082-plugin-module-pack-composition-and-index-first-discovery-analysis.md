# ADR 0082: Plugin Module-Pack Composition and Index-First Discovery Analysis

- Status: Proposed
- Date: 2026-03-29
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

Open architecture question remains:

Should framework internals be assembled from explicit class/object module-packs while preserving
a single runtime artifact for project consumption and keeping AI-assisted development efficient?

## Decision

Run a dedicated analysis phase before any further structural split of framework internals.

This ADR defines analysis scope and non-negotiable constraints:

1. **Developer/AI workspace must stay monorepo-first and unified** (`topology/`, `topology-tools/`, `projects/`).
2. **Project consumption remains one runtime framework artifact** (ADR 0081 contract).
3. **Plugin co-location remains mandatory** for class/object ownership boundaries.
4. **Discovery contract stays deterministic and additive** with global plugin ID uniqueness.
5. **No behavior-breaking runtime cutover** is allowed under this ADR; only analysis and design outputs.

Required analysis deliverables:

1. Option matrix:
   - A: keep current structure + index-first hardening,
   - B: internal module-pack build assembly into one artifact,
   - C: hybrid with optional module-pack metadata lock extensions.
2. AI productivity impact analysis:
   - navigation complexity,
   - prompt/context stability,
   - typical edit/test loop cost.
3. Runtime invariants:
   - path resolution invariants (monorepo vs standalone),
   - discovery invariants,
   - lock/integrity invariants.
4. Migration and rollback design:
   - incremental phases,
   - compatibility shims (if needed),
   - objective rollback triggers.
5. Verification matrix:
   - contract tests,
   - distribution boundary tests,
   - standalone artifact rehearsal tests.

Exit criteria for promoting this ADR to Accepted:

1. One recommended target model selected from options A/B/C with rationale.
2. No regression against ADR 0081 runtime artifact contract.
3. Explicit evidence that AI-assisted daily workflow is not degraded.
4. Implementation plan with staged gates and rollback protocol.

## Consequences

Positive:

1. Avoids premature structural split that could increase cognitive load.
2. Preserves ADR 0081 external contract while allowing internal modular evolution.
3. Creates measurable criteria for evaluating architecture options.

Trade-offs:

1. Adds one analysis phase before additional refactoring.
2. Delays large topology packaging changes until evidence is complete.

## References

- ADR 0063: `adr/0063-plugin-microkernel-for-compiler-validators-generators.md`
- ADR 0078: `adr/0078-object-module-local-template-layout.md`
- ADR 0080: `adr/0080-unified-build-pipeline-stage-phase-and-plugin-data-bus.md`
- ADR 0081: `adr/0081-framework-runtime-artifact-and-1-n-project-repository-model.md`
- Discovery implementation: `topology-tools/plugin_manifest_discovery.py`
- Topology module index: `topology/module-index.yaml`
