# IMPLEMENTATION PLAN — ADR 0088

## Approach

Incremental migration with compatibility mode first, then enforcement.
`archive/v4/` is immutable reference scope and is never modified as part of ADR0088 implementation waves.

## Current implementation status (2026-04-06)

1. Runtime semantic-only foundations are active:
   - canonical semantic registry wired
   - strict YAML loader active in core runtime path
   - `E8801..E8806` catalog + runtime enforcement in key compilers.
2. Active instance source path is canonical-only (`projects/home-lab/topology/instances`):
   - zero legacy `class_ref/object_ref`
   - full `@instance/@extends/@layer/@version` coverage.
3. Contract gates are green:
   - compile (`errors=0`)
   - `validate-v5` PASS
   - full `pytest` PASS.
4. Residual quality deltas:
   - metadata coverage asymmetry in class/object manifests
   - boundary-scoped legacy keys in `projects/home-lab/_legacy`
   - non-blocking `W7816` duplicate-IP warning profile.

## Wave 0 — Baseline normalization and contract cleanup

1. Create `topology/semantic-keywords.yaml` and wire it as runtime input.
2. Define context-scoped semantic mapping table (entity manifests vs capability entries) and freeze it in schema.
3. Implement strict YAML loader profile for runtime path (duplicate-key rejection + explicit scalar policy).
4. Metadata backfill campaign:
   - class/object/instance: add missing `title`
   - class/object/instance: add missing `summary` where required by profile
   - class/object: add missing `layer`
5. Capability contract cleanup:
   - remove duplicate capability IDs across catalogs (or formalize non-overlapping partitions)
   - resolve unknown capability refs
   - preserve legacy capability IDs only through explicit migration mapping
6. Legacy naming cleanup:
   - migrate `class.network.router` pack references to `class.router`
   - reject stale class refs in active manifests
7. Isolate `observed_runtime` data from source topology into runtime/evidence state files.

**Gate:** baseline inventory is clean enough for semantic migration:
- no stale class refs in active packs
- no unresolved capability refs
- required metadata coverage targets met
- strict YAML loader active for compile/validate/generate path

## Wave 1 — Registry and semantic resolver foundation

1. Implement semantic resolver utility (`semantic_token -> actual key present`).
2. Wire resolver into class/object/instance loaders.
3. Refactor plugin runtime consumers to semantic resolver:
   - **compilers**: stop direct reads of `class/object/instance/class_ref/object_ref`
   - **validators**: enforce semantic keys and typed links via resolver-backed API
   - **generators**: consume normalized effective model fields, not source key literals
   - **assemblers/builders**: treat semantic metadata (`title/summary/layer/version`) as normalized fields only
4. Add diagnostics for:
    - unknown semantic key
    - canonical+alias collision in one mapping
    - missing required semantic key
    - unsupported or missing `@version`
    - missing `@capability` when capability payload is declared
    - missing `@schema` when `@capability` is declared
    - missing required `@title`
    - missing required `@layer`
    - semantic context violation (`@capability/@schema` outside capability entry context)

**Gate:** compile + existing tests pass in compatibility mode with resolver active across compilers/validators/generators.

## Wave 2 — Explicit hierarchy/materialization contract

1. Replace split refs with unified `@extends` contract (`object.class_ref`, `instance.object_ref` -> `@extends`).
2. Add class DAG validation (existence, cycle detection, lineage resolution).
3. Add target-type validation for `@extends`:
   - class extends class
   - object extends class
   - instance extends object
4. Enforce instance materialization chain consistency.

**Gate:** new validator tests covering positive/negative hierarchy cases.

## Wave 3 — Effective JSON lineage model

1. Add lineage/materialization fields to effective JSON.
2. Emit compatibility bridge fields (`class_ref`, `object_ref`) with deprecation diagnostics.
3. Ensure deterministic ordering and stable structure for downstream generators.
4. Update generators/validators that consume model fields.

**Gate:** golden/snapshot tests updated with explicit lineage checks.

## Wave 4 — Migration policy and enforcement

1. Mode A: `warn` (read aliases, prefer canonical).
2. Mode B: `warn+gate-new` (changed/new files must use canonical keys).
3. Mode C: `enforce` (aliases rejected).
4. Remove dead alias-handling code after stabilization window.
5. Remove bridge fields from effective JSON only after generator/test migration gate.

**Gate:** repository topology converted and clean in enforce mode.

## Wave 5 — Post-cutover quality hardening (current focus)

1. Metadata governance hardening:
   - define measurable coverage targets for required semantic metadata
   - apply phased enforcement (`warn -> gate-new -> enforce`) per active lane.
2. Legacy-boundary governance:
   - explicitly fence `_legacy` from active semantic compliance KPIs
   - keep active-lane compliance metrics scope deterministic.
3. Warning-governance hardening:
   - classify accepted warning families
   - define deterministic escalation criteria (warning -> error) for repeated conflict classes.
4. Compliance reporting:
   - publish periodic ADR0088 status snapshot against cutover checklist.

**Gate:** quality-hardening policies are documented, measurable, and enforced in CI without semantic rollback.

## Test strategy

1. Unit tests for semantic resolver and collision detection.
2. Integration tests for inheritance/materialization graph validation.
3. End-to-end compile tests confirming effective lineage JSON.
4. Metadata normalization tests for `@version`/`@capability`/`@schema`/`@title`/`@summary`/`@layer`/`@description`.
5. Capability contract tests for `@capability` + `@schema` resolution and validation.
6. Regression for ADR 0068 placeholder semantics (no behavior change).
7. Baseline guard tests:
   - no stale class refs in active packs
   - no unknown capability refs in active topology
8. Runtime family migration tests:
   - compiler integration tests prove semantic-key source compatibility
    - validator integration tests prove semantic enforcement without literal-key coupling
    - generator integration tests prove outputs are stable with canonical key mode
9. Strict YAML tests:
   - duplicate key in YAML fails with deterministic error code
10. Effective JSON compatibility tests:
   - compatibility mode contains bridge fields
   - enforce mode behavior follows configured deprecation gate
