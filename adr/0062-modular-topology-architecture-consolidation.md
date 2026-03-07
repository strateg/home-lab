# ADR 0062: Topology v5 - Modular Class-Object-Instance Architecture

**Date:** 2026-03-06
**Status:** Accepted
**Supersedes:** ADR 0058, ADR 0059, ADR 0060, ADR 0061
**Evolves:** ADR 0048 (Topology v4 Architecture Consolidation)

---

## Context

The repository already has a large accepted ADR baseline (0001-0057) that defines layer ownership, topology contracts, runtime boundaries, and deploy workflow.

The v5 migration must:

1. stay maximally compatible with accepted ADR contracts
2. move model semantics to `Class -> Object -> Instance`
3. keep migration auditable and reversible
4. avoid reopening already accepted domain decisions unless a new ADR explicitly does that

The previous v5 decisions (0058-0061) defined direction, but in separate documents. This ADR is the single normative integration contract.

---

## Decision

### 1. Compatibility-First Rule

ADR 0062 is an integration ADR, not a domain-reset ADR.

All accepted contracts from earlier ADRs remain valid unless explicitly replaced by a newer ADR:

- L1/L2 power, data-link, firewall and storage boundary contracts (ADR 0001-0005, 0029)
- L3/L4/L5 taxonomy and runtime boundary contracts (ADR 0026, 0038-0044)
- toolchain and architecture constraints (ADR 0027, 0028, 0046, 0048)
- output/runtime/deploy ownership constraints (ADR 0050-0057)

v5 changes the modeling axis and execution contracts, not the business meaning of those accepted decisions.

### 2. Canonical v5 Model Contract

All deployable entities MUST resolve through:

`Instance.object_ref -> Object.class_ref -> Class`

Effective merge order is fixed:

`Class.defaults -> Object.defaults -> Instance.overrides`

Hard rules:

- instance overrides MUST NOT violate class invariants
- object MUST satisfy class required capabilities
- instance MUST NOT request capabilities unsupported by the object

### 3. Dual-Axis Contract Is Mandatory

v5 keeps the `L0 -> L7` layer axis from v4 and adds `Class -> Object -> Instance` as an orthogonal axis.

Both are mandatory:

- semantic composition axis: `Class -> Object -> Instance`
- placement and ownership axis: `L0 -> L7`

Layer ownership and directional contracts from accepted ADRs remain in force and are enforced through v5 layer contract data.

### 4. Capability Model Is Kept Simple

Only three capability levels are normative:

1. capability catalog (flat canonical IDs)
2. class contract (`required_capabilities`, `optional_capabilities`, `capability_packs`)
3. object binding (`enabled_capabilities`, optional `enabled_packs`, optional `vendor.*`)

Guardrails:

- no deep capability inheritance trees
- vendor-only keys must be namespaced as `vendor.*`
- object-local capability is promoted to class-level pack/catalog when reused by 2+ objects with identical semantics

### 5. YAML Source, JSON Canonical Build Artifact

Humans author YAML. Machines consume canonical JSON.

Compiler stages are fixed:

1. `load`
2. `normalize`
3. `resolve`
4. `validate`
5. `emit`

Diagnostics are schema-first and mandatory for both machine and human flows.

### 6. model.lock and Profiles Are Mandatory

`model.lock.yaml` is required for controlled runs and pins:

- core model version
- class module versions
- object module versions

`profile-map.yaml` MUST support:

- `production`
- `modeled`
- `test-real`

Profile replacement is allowed only when class and capability signatures remain compatible.

### 7. Migration Governance: v4 Lane and v5 Lane

Migration is dual-lane:

- legacy lane: `v4/*` (frozen for net-new features)
- target lane: `v5/*` (active development)

Artifact roots are versioned by lane:

- `v4-generated`, `v4-build`, `v4-dist`
- `v5-generated`, `v5-build`, `v5-dist`

No new feature work is allowed in v4 lane.

### 8. Plugin Microkernel Sequencing

Plugin microkernel migration is governed by ADR 0063 and happens after model parity gates are met.

ADR 0062 does not redefine plugin API details.

---

## Consequences

### Positive

1. v5 migration stays close to accepted architectural history instead of rewriting it
2. `Class -> Object -> Instance` becomes a single, testable model contract
3. layer contracts and operational boundaries remain stable during migration
4. diagnostics/lock/profile contracts make migration safer for CI and AI-assisted remediation

### Trade-offs and Risks

1. temporary dual-lane overhead in repository and CI
2. strict compatibility policy slows down disruptive redesigns
3. capability governance needs discipline to avoid drift or sprawl

### Risk Controls

1. enforce lane-specific CI gates and path policies
2. keep parity checks on production-critical artifacts
3. require rollback procedure before full v5 cutover

---

## References

- ADR register: `adr/REGISTER.md`
- Consolidated v5 analysis package: `adr/0062-analysis/`
- Superseded contracts:
  - `adr/0058-core-abstraction-layer.md`
  - `adr/0059-repository-split-and-class-object-instance-module-contract.md`
  - `adr/0060-yaml-to-json-compiler-diagnostics-contract.md`
  - `adr/0061-base-repo-versioned-class-object-instance-and-test-profiles.md`
- Related accepted baselines:
  - `adr/0048-topology-v4-architecture-consolidation.md`
  - `adr/0050-generated-directory-restructuring.md`
  - `adr/0051-ansible-runtime-and-secrets.md`
  - `adr/0052-build-pipeline-after-ansible.md`
  - `adr/0054-local-inputs-directory.md`
  - `adr/0055-manual-terraform-extension-layer.md`
  - `adr/0056-native-execution-workspace.md`
  - `adr/0057-mikrotik-netinstall-bootstrap-and-terraform-handover.md`
- Proposed extension:
  - `adr/0063-plugin-microkernel-for-compiler-validators-generators.md`
