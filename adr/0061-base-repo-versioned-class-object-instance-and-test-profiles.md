# ADR 0061: Base Repo with Versioned Class-Object-Instance and Test Profiles

**Date:** 2026-03-06
**Status:** Proposed
**Related:** ADR 0059 (Class-Object-Instance Module Contract), ADR 0060 (YAML-to-JSON Compiler and Diagnostics Contract)

---

## Context

The accepted architectural direction is `Class -> Object -> Instance`:

- `Class` captures semantics and invariants
- `Object` captures implementation behavior
- `Instance` captures concrete deployment nodes and their links

We also need an explicit operational model for two testing realities:

1. **Production network** (real devices and real service traffic)
2. **Modeled network** (simulation/lab with virtual substitutions, for example MikroTik CHR instead of hardware)

Additionally, production may use **test profiles on real devices** (feature-flag-like behavior) without replacing hardware.

To keep this reproducible across many topology repositories, version and compatibility must be explicit through the chain:

`Class version -> Object version -> Instance selection`.

---

## Decision

### 1. Split Ownership into Base Repo and Multiple Instance Repos

Adopt repository model:

1. **Base repository (`topology-base`)**
   - model core contracts (schemas, compiler, diagnostics)
   - class modules
   - object modules
2. **Instance repositories (many)**
   - network-specific instance topology (nodes + links + overrides)
   - profile maps for production/modeled/test-real variations
   - lock files pinning compatible base artifacts

Instance repos depend on base repo artifacts by explicit versions.

### 2. Introduce model.lock as Mandatory Version Contract

Every instance repository must ship `model.lock` that pins:

- `core_model_version`
- class module pins
- object module pins
- optional object->class compatibility metadata

Compiler validates the lock against references used in compiled topology.

### 3. Introduce Profile Overlay Contract for Runtime Variants

Profile overlays are external YAML maps applied during compilation:

- `production` profile: canonical production behavior
- `modeled` profile: virtual substitutions and simplified topology for testing
- `test-real` profile: test behavior on real devices (no hardware replacement)

Supported per-instance actions:

- replace `object_ref` (e.g., hardware MikroTik -> CHR)
- merge additional `overrides`
- optional disable/drop instance from effective topology

Profile substitution compatibility rule:

- replacement object must match class and satisfy required capability signature of the replaced instance role
- `modeled` profile may reduce non-critical optional capabilities, but must preserve test target capabilities
- `test-real` profile keeps hardware object and applies only behavioral overrides

Recommended profile capability signatures:

- `production-min`: baseline required by production contracts
- `modeled-min`: baseline for simulation correctness
- `test-real-min`: baseline + test-specific capabilities

### 4. Keep Human-Readable Top Layer on Instances

Top-level topology authoring remains instance-centric and concise.
Class/Object complexity is encapsulated in base modules.

This keeps instance repos readable while maximizing module reuse.

### 5. Complexity Reduction Rules for Capability Reuse

To avoid model bloat across many repos:

1. Reuse class capability packs before introducing new object-local capabilities
2. Promote repeated object-local capabilities into class pack when reused in 2+ object modules
3. Keep vendor-only capabilities under `vendor.*` namespace and out of class required set
4. Limit profile overlays to operational differences; avoid embedding full object semantics into profile maps

---

## Consequences

### Positive

1. Clear scaling model: one reusable base + many environment repos
2. Reproducible builds with explicit version lock chain
3. Safe experimentation via modeled profile without touching production descriptors
4. Real-device test profiles become first-class and auditable

### Negative

1. Additional artifact to maintain (`model.lock`)
2. Profile overlays add one more compilation dimension
3. Release management required across base and instance repos

### Risks and Mitigations

1. Risk: silent drift between production and modeled topology
   - Mitigation: keep both profiles in CI and diff effective outputs
2. Risk: object replacement breaks class contract
   - Mitigation: lock compatibility and compile-time class/object validation
3. Risk: test-real profile leaks into production run
   - Mitigation: explicit `--profile` selection and CI policy on default profile

---

## References

- Class-Object-Instance contract: `adr/0059-repository-split-and-class-object-instance-module-contract.md`
- Compiler/diagnostics contract: `adr/0060-yaml-to-json-compiler-diagnostics-contract.md`
- Compiler implementation: `topology-tools/compile-topology.py`
- Capability contract checker: `topology-tools/check-capability-contract.py`
- model.lock bootstrap example: `topology/model.lock.example.yaml`
- profile map bootstrap example: `topology/profile-map.example.yaml`
- Error catalog: `topology-tools/data/error-catalog.yaml`
- ADR register: `adr/REGISTER.md`
- Commit: pending
