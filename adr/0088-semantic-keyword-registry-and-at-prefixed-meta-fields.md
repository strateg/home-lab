# ADR 0088: Semantic Keyword Registry and `@`-Prefixed Meta Fields

| Field | Value |
|-------|-------|
| **Status** | Accepted (implemented) |
| **Date** | 2026-04-05 |
| **Deciders** | dmpr |
| **Supersedes** | ADR 0067 (partial: class/object/instance key policy) |
| **Related** | ADR 0062, ADR 0068, ADR 0069, ADR 0080 |

## Context

The current topology contract is functional but key semantics are hardcoded across compiler/plugins:

- class module identity uses `class`
- object module identity uses `object`
- instance identity uses `instance`
- hierarchy/materialization links are split across different field names (`class_ref`, `object_ref`)

Current gaps:

1. No single unified parent-link contract across class/object/instance.
2. Tooling binds to literal key names in many places instead of semantic IDs.
3. Effective JSON lacks first-class lineage chain (`class -> object -> instance`) for audit.

Topology baseline audit (2026-04-05) identified concrete migration debt:

1. `topology/semantic-keywords.yaml` does not exist yet.
2. Legacy link keys are dominant (`class_ref`: 112 files, `object_ref`: 148 files, `extends`: 0 files).
3. Metadata is incomplete at scale (`title` missing in 271 entity files, `summary` missing in 275, `layer` missing in 141 class/object files).
4. Capability contract is fragmented:
   - 3 capability catalogs
   - 55 duplicate capability IDs across catalogs
   - 51 capability refs not present in catalogs
5. Legacy class names still exist in packs (e.g., `class.network.router`), while active class is `class.router`.
6. Runtime snapshot payload (`observed_runtime`) is present in topology instances and should be isolated from declarative source-of-truth.

At the same time, YAML 1.2.2 supports representation-level features (anchors/aliases, mapping/sequence/scalar model), while our runtime semantics should remain explicit and deterministic.

## Decision

### 1. Introduce semantic keyword registry (single source of truth)

Add a framework-level config file:

`topology/semantic-keywords.yaml`

It defines canonical service keywords and aliases:

- `schema_version`: canonical `@version`, aliases: `version`
- `capability_id`: canonical `@capability`, aliases: `capability`, `id` (legacy capability form)
- `capability_schema`: canonical `@schema`, aliases: `schema`
- `class_id`: canonical `@class`, aliases: `class`
- `object_id`: canonical `@object`, aliases: `object`
- `instance_id`: canonical `@instance`, aliases: `instance`
- `parent_ref`: canonical `@extends`, aliases: `extends`
- `entity_title`: canonical `@title`, aliases: `title`
- `entity_summary`: canonical `@summary`, aliases: `summary`
- `entity_description`: canonical `@description`, aliases: `description`
- `entity_layer`: canonical `@layer`, aliases: `layer`

Registry resolution is **context-scoped**, not global string replacement:

1. `@class/@object/@instance/@extends/@title/@summary/@description/@layer/@version` apply to class/object/instance manifests only.
2. `@capability/@schema` apply to capability-entry records only.
3. Legacy alias `id` is accepted only in capability-entry context during migration.
4. File-level `schema` keys (e.g., catalog file schema type) are out of scope for capability-entry remapping.

### 2. Move tooling from hardcoded keys to semantic IDs

Compiler/plugins must resolve keys via the registry (semantic token -> actual YAML key), not by hardcoded literals.
This is mandatory for runtime implementation families, with priority on compile/validate/generate:

- compilers
- validators
- generators
- assemblers/builders consuming effective model metadata

This applies to:

- module loaders
- instance rows normalization
- validators
- generators consuming effective payload
- compiler/validator/generator plugin manifests and projections that currently assume legacy key names

Additionally, YAML ingestion in compile/validate/generate path must use a strict loader profile:

1. duplicate mapping keys -> hard error
2. ambiguous scalar coercion must be normalized by explicit schema policy
3. no silent overwrite behavior from permissive YAML loading

### 3. Formalize hierarchy and materialization contracts

Add explicit validation rules using one field: `@extends`.

1. **Class file**: `@version: <schema>`, `@class: <name>`, `@title: <text>`, `@layer: <layer>`, optional `@summary`, optional `@description`, optional `@extends: <parent_class>`.
2. **Object file**: `@version: <schema>`, `@object: <name>`, `@title: <text>`, `@layer: <layer>`, optional `@summary`, optional `@description`, required `@extends: <class_name>`.
3. **Instance file**: `@version: <schema>`, `@instance: <name>`, `@title: <text>`, `@layer: <layer>`, optional `@summary`, optional `@description`, required `@extends: <object_name>`.
4. Class inheritance must be acyclic and resolvable.
5. `@extends` target type must match owner type (`instance -> object`, `object -> class`, `class -> class`).
6. `@version`, `@title`, and `@layer` must be present and supported by runtime compatibility policy.
7. `@summary` and `@description` are optional but normalized in effective JSON when present.
8. Capability declarations use `@capability` (instead of legacy `capability/id: ...`) and must also include `@schema` and `@title`.
9. Classes are treated as abstractions by default; no separate abstract-class flag is required.

Deterministic `@extends` resolution algorithm:

1. Resolve owner kind first (`class` | `object` | `instance`) from manifest root key.
2. Apply typed target contract:
   - class -> class
   - object -> class
   - instance -> object
3. Resolve target by canonical registry identity map.
4. Fail on ambiguous matches or cross-kind target.
5. Build lineage graph and reject cycles.

### 4. Enrich effective JSON with lineage

Effective JSON must include normalized lineage fields:

- class: `parent_class`, `lineage`
- object: `extends_class`, `materializes_class`, `class_lineage`
- instance: `extends_object`, `materializes_object`, `materializes_class`, `resolved_lineage`
- all entities: `version`, `title`, `summary` (nullable), `layer`, `description` (nullable)
- capabilities: `capability`, `schema`, `title`, `summary` (resolved from `@capability`, `@schema`, `@title`, `@summary`)

Compatibility output contract (mandatory during migration):

1. Compatibility mode emits canonical fields plus legacy bridge fields (`class_ref`, `object_ref`) for downstream stability.
2. Legacy bridge fields are marked deprecated in diagnostics.
3. Enforce mode may drop bridge fields only after generator/validator/test migration gate passes.

This enables deterministic queries:

- which class extends which class
- which object extends/materializes which class
- which instance materializes which object/class

### 5. Compatibility and migration policy

This ADR does **not** force immediate hard cutover. Migration is phased:

1. read both canonical and alias keys (diagnostic warning on legacy keys)
2. enforce canonical keys in changed/new files
3. full enforcement, then remove aliases

ADR alignment:

1. ADR 0067 strictness remains for entity identity semantics; ADR 0088 supersedes only key-spelling policy for those entities.
2. ADR 0068 placeholder markers (`@required/@optional/...`) remain value-level syntax and must not be interpreted as semantic-key metadata.

### 6. Mandatory pre-cutover normalization gates

Before moving from compatibility to enforce mode:

1. Create and wire `topology/semantic-keywords.yaml` as runtime-loaded contract.
2. Backfill required metadata (`@title`, `@layer`) across class/object/instance manifests.
3. Converge capability contract to one canonical catalog (or strict layered partition with no duplicates), then validate all refs.
4. Migrate/remove legacy pack/class references (`class.network.router` -> `class.router`).
5. Move operational runtime snapshots out of canonical topology manifests into evidence/state artifacts.
6. Add dedicated validators for:
   - semantic-key presence/completeness
   - typed `@extends` chain
   - capability ID existence + duplicate detection
   - canonical/alias collision in one mapping

7. Reserve migration scope to active lane only:
   - include: `topology/`, `projects/*/topology/instances/`, `topology-tools/` runtime plugins
   - exclude unconditionally: `archive/v4/` (immutable reference, never modified by ADR0088 migration), `generated/`, acceptance artifacts, historical fixtures
8. Add ADR 0088 error catalog family (E880x minimum):
   - missing required semantic key
   - typed `@extends` target mismatch
   - ambiguous semantic alias/canonical collision
   - unknown capability ID / duplicate capability ID
   - strict YAML duplicate-key violation

## Consequences

### Positive

1. Semantic key contract becomes explicit, centralized, and versioned.
2. Hierarchy/materialization validation becomes first-class and auditable.
3. Tooling is less brittle to future naming refactors.
4. Effective JSON becomes a reliable graph for topology analysis.

### Trade-offs / Risks

1. Large cross-cutting change in loader/validator/generator contracts.
2. Potential cognitive overlap with ADR 0068 `@required/@optional` value markers.
3. Migration complexity due to many existing files and tests.
4. Temporary dual-key period increases validation/diagnostic complexity.

### Mitigations

1. Keep value-marker namespace (ADR 0068) separate from key-namespace policy.
2. Add dedicated diagnostics for key-resolution ambiguity and alias conflicts.
3. Stage rollout by profile (`warn` -> `warn+gate-new` -> `enforce`).

## Analysis Artifacts

- `adr/0088-analysis/GAP-ANALYSIS.md`
- `adr/0088-analysis/IMPLEMENTATION-PLAN.md`
- `adr/0088-analysis/CUTOVER-CHECKLIST.md`
- `adr/0088-analysis/SWOT-ANALYSIS.md`

## Implementation Status Snapshot (2026-04-06)

Fact-based runtime status:

1. Contract gates are green:
   - compile: `errors=0` (`warnings=5`, `infos=81`)
   - `validate-v5`: PASS
   - full test suite: `911 passed, 4 skipped`.
2. Semantic-only status in active instance lane (`projects/home-lab/topology/instances`):
   - legacy `class_ref/object_ref`: `0/0`
   - canonical `@instance/@extends/@layer/@version`: `148/148/148/148`.
3. Registry and diagnostics status:
   - `topology/semantic-keywords.yaml` is canonical-only (`aliases: []` for all tokens)
   - `E8801..E8806` are defined in error catalog and used in runtime/tests.
4. Quality hardening status:
   - class/object metadata coverage for `@title/@layer` is 100% (`43/43`, `112/112`)
   - governance default mode is `enforce` in `validate-v5` entrypoint
   - boundary-scoped legacy keys remain in `projects/home-lab/_legacy`
   - warning profile remains concentrated in `W7816` duplicate-IP diagnostics (policy-governed).

## References

- YAML 1.2.2: https://yaml.org/spec/1.2.2/
- `topology-tools/compile-topology.py`
- `topology-tools/compiler_runtime.py`
- ADR 0067, ADR 0068, ADR 0069, ADR 0080
