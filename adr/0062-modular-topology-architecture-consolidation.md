# ADR 0062: Topology v5 - Modular Class-Object-Instance Architecture

**Date:** 2026-03-06
**Status:** Accepted (Harmonized with ADR 0064 on 2026-03-09)
**Supersedes:** ADR 0058, ADR 0059, ADR 0060, ADR 0061
**Evolves:** ADR 0048 (Topology v4 Architecture Consolidation)
**Extended by:** ADR 0064 (Firmware + OS Two-Entity Model)

---

## Context

The repository already has a large accepted ADR baseline (0001-0057) that defines layer ownership, topology contracts, runtime boundaries, and deploy workflow.

The v5 migration must:

1. stay maximally compatible with accepted ADR contracts
2. move model semantics to `Class -> Object -> Instance`
3. keep migration auditable and reversible
4. avoid reopening already accepted domain decisions unless a new ADR explicitly does that

The previous v5 decisions (0058-0061) defined direction, but in separate documents. This ADR is the single normative integration contract.

ADR 0064 is approved as a normative extension and clarifies software-stack modeling:
- firmware and OS are separate first-class entities
- both follow the same `Class -> Object -> Instance` semantics
- device bindings are instance-based (`firmware_ref`, `os_refs[]`)

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
- canonical identifiers MUST use stable prefixes:
  - class: `class.<domain>.<name>`
  - object: `obj.<domain>.<name>` + `class_ref`
  - instance: `inst.<domain>.<name>` + `object_ref`

#### 2.1 Software Stack Entity Contract (Harmonized with ADR 0064)

Firmware and OS are modeled as separate entities with uniform semantics:

- `class.firmware -> obj.firmware.* -> inst.firmware.*`
- `class.os -> obj.os.* -> inst.os.*`

Device/workload instances MUST reference software stack by instance refs:

- `firmware_ref: inst.firmware.*` (required if class contract requires firmware)
- `os_refs: [inst.os.*]` (0..N depending on class `os_policy` and cardinality)

Legacy bindings are deprecated and non-normative in v5:

- `bindings.firmware`
- `os_primary`, `os_secondary`, `os_tertiary`
- class-level OS subclass contracts (`os.firmware`, `os.installable`)

Class/object contracts define class constraints and cardinality only.
Concrete firmware/OS selection is made at instance level.

#### 2.2 Multi-Boot Contract

Multi-boot is represented only by `os_refs[]` plus class/object constraints:

- `multi_boot: true` allows multiple OS instance refs
- `multi_boot: false` requires at most one OS instance ref
- service compatibility MUST be validated against effective capabilities of all referenced OS instances

### 3. Dual-Axis Contract Is Mandatory

v5 keeps the `L0 -> L7` layer axis from v4 and adds `Class -> Object -> Instance` as an orthogonal axis.

Both are mandatory:

- semantic composition axis: `Class -> Object -> Instance`
- placement and ownership axis: `L0 -> L7`

Layer ownership and directional contracts from accepted ADRs remain in force and are enforced through v5 layer contract data.

Layer contract source of truth: `v5/topology/layer-contract.yaml`

Target v5 layer scope (full coverage):

| Layer | Group | Class Domain | Status |
|-------|-------|--------------|--------|
| L0 | meta | meta.* | deferred (no instances) |
| L1 | devices | compute.*, network.router, power.*, firmware, os | implemented |
| L2 | network | network.bridge, network.vlan, network.trust_zone, network.firewall_policy, network.qos | implemented |
| L3 | storage | storage.pool, storage.volume, storage.data_asset | implemented |
| L4 | vms, lxc | compute.workload.* | implemented |
| L5 | services | service.* | implemented |
| L6 | observability | observability.healthcheck, observability.alert | implemented (partial) |
| L7 | operations | operations.backup | implemented (partial) |

Cross-layer dependency rules (normative):

| Relation | Source Layer | Target Layer | Direction | Status |
|----------|--------------|--------------|-----------|--------|
| firmware_ref | L1, L4 | L1 (inst.firmware.*) | downward | enforced |
| os_refs | L1, L4 | L1 (inst.os.*) | downward | enforced |
| runtime.target_ref | L5 | L1, L4 | downward | enforced |
| storage.pool_ref | L4 | L3 | downward | enforced |
| storage.volume_ref | L5 | L3 | downward | enforced |
| network.bridge_ref | L4 | L2 | downward | enforced |
| network.vlan_ref | L1, L4 | L2 | downward | enforced |
| observability.target_ref | L6 | L1, L4, L5 | downward | enforced |
| operations.target_ref | L7 | L1, L4, L5, L6 | downward | enforced |
| power.source_ref | L1 | L1 | lateral | enforced |

Execution tracker for enforced relation ownership/evidence:
- `adr/0062-cross-layer-relations-execution-backlog.md`

### 4. Capability Model Is Kept Simple

Only three capability levels are normative:

1. capability catalog (flat canonical IDs)
2. class contract (`required_capabilities`, `optional_capabilities`, `capability_packs`)
3. object binding (`enabled_capabilities`, optional `enabled_packs`, optional `vendor.*`)

#### 4.1 Namespace Convention

```text
cap.<domain>.<subdomain>.<capability>    # Standard capabilities (catalog-registered)
vendor.<vendor>.<domain>.<capability>    # Vendor-specific extensions
pack.<domain>.<profile>                  # Capability packs (reusable bundles)
```

#### 4.2 Domain Taxonomy (by layer)

| Layer | Domain | Capability Prefix | Status |
|-------|--------|-------------------|--------|
| L1 | Compute | `cap.compute.*`, `cap.arch.*` | implemented |
| L1 | Firmware | `cap.firmware.*` | implemented |
| L1 | OS | `cap.os.*` | implemented |
| L1 | Network | `cap.net.*` | implemented |
| L1 | Power | `cap.power.*` | implemented |
| L2 | Bridge/VLAN/Firewall/QoS | `cap.bridge.*`, `cap.vlan.*`, `cap.zone.*`, `cap.firewall.*`, `cap.qos.*` | implemented |
| L3 | Storage | `cap.storage.pool.*`, `cap.storage.volume.*`, `cap.storage.asset.*` | implemented |
| L4 | Workload | `cap.compute.workload.*` | implemented |
| L5 | Service | `cap.service.*` | implemented |
| L6 | Observability | `cap.observability.healthcheck.*`, `cap.observability.alert.*` | implemented |
| L7 | Operations | `cap.operations.backup.*` | implemented |

#### 4.3 Guardrails

- no deep capability inheritance trees (max 1 level via packs)
- capability IDs are flat and stable within domain
- vendor-only capabilities must use `vendor.<vendor>.*` namespace
- object-local capability is promoted to catalog when reused by 2+ objects with same semantics
- capability packs must reference only catalog-registered capabilities
- class required_capabilities must be subset of catalog
- software-derived capabilities (`cap.firmware.*`, `cap.os.*`) are computed from resolved firmware/OS instances and participate in effective capability validation

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
3. firmware/OS modeling is explicit, uniform, and instance-resolved
4. layer contracts and operational boundaries remain stable during migration
5. diagnostics/lock/profile contracts make migration safer for CI and AI-assisted remediation

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
- Proposed extensions:
  - `adr/0063-plugin-microkernel-for-compiler-validators-generators.md`
- Canonical extension:
  - `adr/0064-os-taxonomy-object-property-model.md`
