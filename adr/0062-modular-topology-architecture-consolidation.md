# ADR 0062: Topology v5 - Modular Class-Object-Instance Architecture

**Date:** 2026-03-06
**Status:** Accepted
**Supersedes:** ADR 0058, ADR 0059, ADR 0060, ADR 0061
**Evolves:** ADR 0048 (Topology v4 Architecture Consolidation)

---

## Context

ADRs 0058-0061 established the right direction but split critical decisions across multiple documents.
That created drift in four areas:

1. repository split timing and boundaries
2. compiler and diagnostics contract
3. capability modeling rules
4. profile/testing model (production vs modeled/test-real)

Since then, the repository already contains working contract artifacts:

- compiler and diagnostics envelope: `topology-tools/compile-topology.py`
- diagnostics schema: `topology-tools/schemas/diagnostics.schema.json`
- model lock schema: `topology-tools/schemas/model-lock.schema.json`
- profile map schema: `topology-tools/schemas/profile-map.schema.json`
- error catalog: `topology-tools/data/error-catalog.yaml`
- capability contract checker: `topology-tools/check-capability-contract.py`
- initial class/object templates:
  - `topology/class-modules/...`
  - `topology/object-modules/...`

This ADR consolidates all normative rules into one accepted contract.

---

## Decision

### 1. Canonical Model: Class -> Object -> Instance

All deployable entities follow one chain:

`Instance.object_ref -> Object.class_ref -> Class`

Merge precedence for effective model:

`Class.defaults -> Object.defaults -> Instance.overrides`

Hard rules:

- instance overrides must not violate class invariants
- object must satisfy class required capabilities
- instance must not request unsupported object capability

Topology authoring remains instance-centric (L0-L7), while classes/objects encapsulate reusable semantics.

### 2. Simplified Capability Model (Normative)

Capability contract is fixed to three layers only:

1. capability catalog (canonical IDs)
2. class contract (`required_capabilities`, `optional_capabilities`, `capability_packs`)
3. object binding (`enabled_capabilities`, optional `enabled_packs`, optional `vendor.*`)

Complexity guardrails:

- no deep capability inheritance trees
- capability IDs are flat and stable
- vendor-specific capabilities must use `vendor.*`
- object-local capability is promoted to class catalog/pack when reused by 2+ objects with same semantics

Implementation references:

- `topology/class-modules/capability-catalog.example.yaml`
- `topology/class-modules/capability-packs.example.yaml`
- `topology-tools/check-capability-contract.py`

### 3. Repository Strategy: Stage A (Current) -> Stage B (Extraction)

No immediate hard split into two repositories.

Stage A (current, in-repo separation):

- `topology/class-modules/` (class layer)
- `topology/object-modules/` (object layer)
- `topology/` (instance layer, L0-L7)
- `topology-tools/` (compiler/validation/generation runtime)

Stage B (future extraction target):

- `topology-base` (core model, compiler, class/object modules)
- multiple instance repos (network-specific instance topologies)

Extraction criteria (all required):

- at least 3 independent topology consumers
- base layer requires independent release cadence
- CI compatibility matrix exists for base version vs instance repos

### 4. YAML Source, JSON Canonical Artifact

Source of truth for humans remains YAML.
Canonical machine artifact remains JSON emitted by compiler.

Compiler stages (normative stage IDs):

1. `load`
2. `normalize`
3. `resolve`
4. `validate`
5. `emit`

Current entrypoint:

- `python topology-tools/compile-topology.py ...`

### 5. Diagnostics Contract Is Schema-First

Diagnostics contract is defined by:

- `topology-tools/schemas/diagnostics.schema.json`

Required report envelope:

- `report_version`, `tool`, `generated_at`
- `inputs`, `outputs`, `summary`, `diagnostics`
- optional `next_actions`

Required diagnostic fields:

- `code`, `severity`, `stage`, `message`, `path`, `confidence`
- optional `source`, `related`, `hint`, `autofix`, `root_cause_rank`

Error taxonomy is catalog-driven (`topology-tools/data/error-catalog.yaml`) and stable by code family.

### 6. Profiles: production / modeled / test-real

Profile overlays are first-class and validated.
Primary profile names:

- `production`: canonical deployment behavior
- `modeled`: virtual replacements and simplified test topology
- `test-real`: real hardware retained, test behavior enabled by overrides

Profile map contract:

- `instance_overrides` per profile
- each override may set `object_ref`, `class_ref`, `overrides`, `patch`, `enabled`

Compatibility rules:

- replacement object must match class contract
- replacement object must satisfy required capability signature of the instance role
- `test-real` must not replace hardware unless explicitly approved

Reference file:

- `topology/profile-map.example.yaml`

### 7. Version Lock Is Mandatory

`model.lock` is a required compatibility artifact for controlled runs:

- pins `core_model_version`
- pins class versions
- pins object versions
- captures object->class compatibility metadata

Compiler validates model lock contract and linkage consistency.

References:

- `topology/model.lock.yaml`
- `topology-tools/schemas/model-lock.schema.json`

### 8. Backward Compatibility and Deprecation Policy

Legacy fields (`type`, `implementation`) remain temporarily supported for migration only.

Deprecation timeline:

1. 2026-03-06 to 2026-06-30:
   - dual-field mode allowed (`legacy + class_ref/object_ref`)
   - new topology onboarding must use explicit `class_ref` and `object_ref`
2. on and after 2026-07-01:
   - compiler emits warnings for legacy-only bindings
   - CI should fail for new legacy-only additions
3. no earlier than 2026-10-01:
   - remove legacy-only support in next major model version

---

## Current Structure (Normative Stage A)

```text
home-lab/
|- topology/
|  |- class-modules/
|  |- object-modules/
|  |- L0-...L7 ...
|  |- model.lock.yaml
|  `- profile-map.example.yaml
|- topology-tools/
|  |- compile-topology.py
|  |- check-capability-contract.py
|  |- schemas/
|  `- data/error-catalog.yaml
`- adr/
```

---

## Target Extraction Structure (Stage B)

```text
topology-base/
|- model core (schemas, compiler, diagnostics, error catalog)
|- class-modules/
`- object-modules/

<instance-repo>/
|- topology/ (instances + L0-L7 + profile maps + lock files)
`- deployment wrappers
```

This is a target state, not a prerequisite for v5 acceptance.

---

## Validation and Quality Gates

Minimum gates for CI and local runs:

1. compiler run with diagnostics artifact emission
2. diagnostics report schema validation
3. model lock validation (strict mode in CI)
4. capability contract validation (`check-capability-contract.py`)
5. semantic validators execution
6. profile matrix checks (`production`, `modeled`, `test-real`) with effective-output diff policy

---

## Migration Plan (Consolidated)

### Phase A - Contract Stabilization (now)

- keep Stage A directory structure
- align all docs and examples to real diagnostics/profile/model-lock contracts
- complete explicit `class_ref` and `object_ref` bindings in active topology files

### Phase B - Modular Runtime Refactor

- continue moving vendor logic into object-module boundaries
- keep output parity with existing generation pipeline
- replace hardcoded dispatch with registry-based dispatch incrementally

### Phase C - Optional Base Extraction

- execute only after extraction criteria are met
- publish versioned base package/repo
- pin and test compatibility matrix across instance repos

---

## Consequences

### Positive

1. one canonical ADR for model, compiler, diagnostics, and profile contracts
2. stable AI repair loop via schema-first diagnostics and error catalog
3. lower modeling complexity via simplified capability rules
4. clear operational testing model for production/modeled/test-real
5. no premature repository split while preserving extraction path

### Negative

1. migration period keeps dual syntax and compatibility code
2. model.lock and profile governance add process overhead
3. strict contracts require regular maintenance of schemas/catalogs

---

## Risks and Mitigations

1. Risk: diagnostics drift from implementation
   - Mitigation: report validated against `diagnostics.schema.json` on every compile
2. Risk: profile replacement breaks runtime assumptions
   - Mitigation: class/capability compatibility checks and profile matrix CI
3. Risk: capability sprawl
   - Mitigation: catalog + packs + `vendor.*` policy with promotion rule
4. Risk: long dual-mode period
   - Mitigation: explicit deprecation dates and CI policy gates

---

## Open Questions

1. Plugin packaging for generators in Stage B (`pip` package vs repo-local module loading)
2. Formal compatibility matrix format for base extraction (schema + publication workflow)

---

## References

### Related ADRs

- ADR 0048: `adr/0048-topology-v4-architecture-consolidation.md`
- ADR 0058: `adr/0058-core-abstraction-layer.md` (superseded)
- ADR 0059: `adr/0059-repository-split-and-class-object-instance-module-contract.md` (superseded)
- ADR 0060: `adr/0060-yaml-to-json-compiler-diagnostics-contract.md` (superseded)
- ADR 0061: `adr/0061-base-repo-versioned-class-object-instance-and-test-profiles.md` (superseded)

### Runtime Contracts

- Compiler: `topology-tools/compile-topology.py`
- Diagnostics schema: `topology-tools/schemas/diagnostics.schema.json`
- Error catalog: `topology-tools/data/error-catalog.yaml`
- model.lock schema: `topology-tools/schemas/model-lock.schema.json`
- profile map schema: `topology-tools/schemas/profile-map.schema.json`
- Capability checker: `topology-tools/check-capability-contract.py`

### Register

- ADR register: `adr/REGISTER.md`
