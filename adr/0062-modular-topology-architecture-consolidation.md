# ADR 0062: Topology v5 - Modular Class-Object-Instance Architecture

**Date:** 2026-03-06
**Status:** Accepted
**Supersedes:** ADR 0058, ADR 0059, ADR 0060, ADR 0061
**Evolves:** ADR 0048 (Topology v4 Architecture Consolidation)

---

## Context

ADRs 0058-0061 established the direction but split critical decisions across multiple documents.
This ADR is the single normative contract for v5.

Consolidation goals:

1. one model contract (`Class -> Object -> Instance`)
2. one topology layer contract (`L0 -> L7`) for placement and dependency direction
3. one compiler/diagnostics contract (YAML source -> JSON canonical)
4. one profile and version-lock governance model
5. one migration plan from v4 to v5 that is implementation-ready
6. explicit in-repo separation of legacy (v4) and new (v5) systems

Current implemented artifacts used by this ADR:

- legacy compiler entrypoint: `v4/topology-tools/compile-topology.py`
- v5 compiler entrypoint: `v5/topology-tools/compile-topology.py`
- v5 layer contract: `v5/topology/layer-contract.yaml`
- diagnostics schema: `v4/topology-tools/schemas/diagnostics.schema.json`
- model lock schema: `v4/topology-tools/schemas/model-lock.schema.json`
- profile map schema: `v4/topology-tools/schemas/profile-map.schema.json`
- error catalog: `v4/topology-tools/data/error-catalog.yaml`
- capability checker: `v4/topology-tools/check-capability-contract.py`

---

## Decision

### 1. Canonical Model: Class -> Object -> Instance

All deployable entities follow:

`Instance.object_ref -> Object.class_ref -> Class`

Effective merge order:

`Class.defaults -> Object.defaults -> Instance.overrides`

Hard rules:

- instance overrides must not violate class invariants
- object must satisfy class required capabilities
- instance must not request unsupported object capability

### 1A. Dual-Axis Layer Contract (`L0 -> L7`) Is Normative

v5 preserves v4 layered topology model (`L0 -> L7`, historically described as OSI-like) as an orthogonal axis to `Class -> Object -> Instance`.

The two axes are independent and both mandatory:

1. semantic axis: `Instance -> Object -> Class`
2. placement axis: `L0 -> L7`

Independence scope:

- semantic composition (`Class -> Object -> Instance`) is independent from layer taxonomy semantics
- placement is still constrained by `layer-contract.class_layers` and runtime dependency rules

Layer contract source of truth:

- `v5/topology/layer-contract.yaml`

Current v5 layer scope (implemented):

- mapped groups: `l1_devices -> L1`, `l4_vms -> L4`, `l4_lxc -> L4`, `l5_services -> L5`
- class-to-layer policy is defined in `layer-contract.class_layers`
- object inherits class layer policy by default and may only narrow it (never widen)
- every instance binding row must carry explicit `layer`

Target v5 layer scope (full coverage):

| Layer | Group | Class Domain | Status |
|-------|-------|--------------|--------|
| L0 | l0_meta | meta.* | deferred (no instances) |
| L1 | l1_devices | compute.*, network.router, power.* | implemented |
| L2 | l2_network | network.bridge, network.vlan, network.firewall | planned |
| L3 | l3_storage | storage.pool, storage.volume, storage.media | planned |
| L4 | l4_vms, l4_lxc | compute.workload.* | implemented |
| L5 | l5_services | service.* | implemented |
| L6 | l6_observability | observability.healthcheck, observability.alert, observability.dashboard | planned |
| L7 | l7_operations | operations.workflow, operations.backup, operations.policy | planned |

Dependency direction rule:

- dependencies must be downward unless relation-specific rule says otherwise
- current enforced relation: `runtime.target_ref` from `L5` is allowed only to `L1` or `L4`

Enforcement scope:

- rules/entities with status `enforced` are blocking in `make validate-v5-layers`
- rules/entities with status `planned`/`deferred` are normative target-state and non-blocking until promoted
- direction keyword `lateral` is accepted as same-layer dependency intent

Cross-layer dependency rules (normative target):

| Relation | Source Layer | Target Layer | Direction | Status |
|----------|--------------|--------------|-----------|--------|
| runtime.target_ref | L5 | L1, L4 | downward | enforced |
| storage.pool_ref | L4 | L3 | downward | planned |
| storage.volume_ref | L5 | L3 | downward | planned |
| network.bridge_ref | L4 | L2 | downward | planned |
| network.vlan_ref | L1, L4 | L2 | downward | planned |
| observability.target_ref | L6 | L1, L4, L5 | downward | planned |
| operations.target_ref | L7 | L1, L4, L5, L6 | downward | planned |
| power.source_ref | L1 | L1 | lateral | planned |

Transition timeline for layer strictness:

1. from 2026-03-06: `instance-bindings.yaml` export emits explicit `layer` for every row
2. from 2026-03-06: v5 validation blocks on enforced layer-contract violations (`make validate-v5-layers`)
3. from 2026-03-06: v5 compile requires non-empty `layer` in each instance row

### 2. Simplified Capability Model (Normative)

Capability contract has three layers only:

1. capability catalog (canonical IDs)
2. class contract (`required_capabilities`, `optional_capabilities`, `capability_packs`)
3. object binding (`enabled_capabilities`, optional `enabled_packs`, optional `vendor.*`)

Guardrails:

- no deep capability inheritance trees
- capability IDs are flat and stable
- vendor-only capabilities must use `vendor.*`
- object-local capability is promoted to class catalog/pack when reused by 2+ objects with same semantics

### 3. YAML Source, JSON Canonical Artifact

Humans author YAML. Machines consume canonical JSON.

Compiler stage IDs are fixed:

1. `load`
2. `normalize`
3. `resolve`
4. `validate`
5. `emit`

### 4. Diagnostics Contract Is Schema-First

Canonical diagnostics contract:

- `topology-tools/schemas/diagnostics.schema.json`
- `topology-tools/data/error-catalog.yaml`

All validators/generators/compilation errors must be emitted through this envelope.

### 5. Profiles: production / modeled / test-real

Profile overlays are first-class and mandatory for operational variants:

- `production`: canonical behavior
- `modeled`: virtual substitutions for simulation/lab
- `test-real`: real hardware retained, test behavior via overrides

Profile compatibility rules:

- replacement object must satisfy class contract
- replacement object must satisfy required capability signature for the instance role
- `test-real` must not replace hardware unless explicitly approved

### 6. Version Lock Is Mandatory

`model.lock` is required for controlled runs:

- pins `core_model_version`
- pins class versions
- pins object versions
- captures object->class compatibility metadata

CI uses strict model-lock mode.

### 7. Backward Compatibility and Deprecation

Legacy fields (`type`, `implementation`) are temporary migration support only.

Timeline:

1. 2026-03-06 to 2026-06-30: dual mode allowed (`legacy + class_ref/object_ref`)
2. from 2026-07-01: compiler warns on legacy-only bindings; CI blocks new legacy-only additions
3. no earlier than 2026-10-01: remove legacy-only support in next major model version

### 8. In-Repo Dual-Track Separation Is Mandatory

To avoid mixing old and new systems during migration, we explicitly separate legacy v4 and new v5 workspaces in the same repository.

Legacy v4 track (frozen by default):

- `v4/topology/` (current production topology snapshot)
- `v4/topology-tools/` (current runtime snapshot)
- `v4/tests/` (all legacy v4 tests)
- outputs: `v4-generated/`, `v4-build/`, `v4-dist/`

New v5 track (active development):

- `v5/topology/` (new instance topology + class/object modules)
- `v5/topology-tools/` (new runtime and plugin-based pipeline)
- `v5/tests/` (all v5 tests; new tests are created only here)
- outputs: `v5-generated/`, `v5-build/`, `v5-dist/`

Governance rules:

- no new features in legacy v4 track
- legacy track allows only critical fixes and parity corrections
- all new model work, module work, and plugin work go to v5 track only
- CI must run v4 and v5 as separate lanes

Output naming rule (normative):

- legacy output roots are renamed: `generated -> v4-generated`, `build -> v4-build`, `dist -> v4-dist`
- v5 output roots are always: `v5-generated`, `v5-build`, `v5-dist`
- after moving scripts into `v4/`, v4 scripts must write only to `v4-*` output roots
- naming separator is hyphen (`-`) only; underscore variants (for example `v4_build`) are not used

### 9. Plugin Microkernel Alignment

ADR 0063 defines plugin microkernel architecture for compiler/validators/generators.
This ADR sets migration ordering:

- first establish v5 model parity and data contracts
- then migrate execution to plugin microkernel in controlled phases

### 10. Repository Extraction Strategy Remains Conditional

No immediate split into separate repositories.

Extraction to `topology-base` plus multiple instance repos is allowed only when all criteria are met:

- at least 3 independent topology consumers
- independent release cadence is required
- compatibility matrix automation exists across base and instance repos

---

## Migration Separation Layout (Normative)

```text
home-lab/
|- v4/                      # LEGACY lane (frozen except critical fixes)
|  |- topology/
|  |- topology-tools/
|  |- tests/
|  |- ansible/
|  |- deploy/
|  |- manual-scripts/
|  |- scripts/
|  |- terraform-overrides/
|  `- local/
|- v5/                      # NEW lane (active migration and implementation)
|  |- scripts/
|  |- topology/
|  |  |- topology.yaml
|  |  |- class-modules/
|  |  |- object-modules/
|  |  |- instances/
|  |  |  `- home-lab/
|  |  |- layer-contract.yaml
|  |  |- model.lock.yaml
|  |  `- profile-map.yaml
|  |- topology-tools/
|  |- tests/
|  `- (no generated artifacts stored here)
|- v4-generated/
|- v4-build/
|- v4-dist/
|- v5-generated/
|- v5-build/
|- v5-dist/
`- adr/
```

Notes:

- At migration start, the current operational tree is moved into `v4/` as-is.
- All new topology/model/runtime files are created only inside `v5/`.
- Generated artifacts are separated by explicit versioned roots (`v4-*` and `v5-*`).
- Legacy paths remain stable until v5 cutover criteria are satisfied.

---

## Consolidated Migration Plan (v4 -> v5)

### Phase 0 - Freeze and Workspace Split

Objective:

- freeze legacy v4 for net-new feature work
- create explicit `v4/` and `v5/` roots and separate CI lanes

Actions:

- move current operational tree into `v4/` (`topology`, `topology-tools`)
- move current v4 tests into `v4/tests/`
- move v4-dependent operational folders into `v4/`:
  - `ansible/ -> v4/ansible/`
  - `deploy/ -> v4/deploy/`
  - `manual-scripts/ -> v4/manual-scripts/`
  - `scripts/ -> v4/scripts/`
  - `terraform-overrides/ -> v4/terraform-overrides/`
  - `local/ -> v4/local/`
- rename legacy artifact roots:
  - `generated/ -> v4-generated/`
  - `build/ -> v4-build/`
  - `dist/ -> v4-dist/` (if present)
- scaffold v5 roots: `v5/scripts/`, `v5/topology/`, `v5/topology-tools/`, `v5/tests/`
- scaffold v5 artifact roots: `v5-generated/`, `v5-build/`, `v5-dist/`
- update default output paths in moved v4 scripts to `v4-generated/`, `v4-build/`, `v4-dist/`
- mark v4 lane as frozen in docs and CI policy
- add lane-specific commands (`validate-v4`, `validate-v5`, `build-v4`, `build-v5`)

Exit criteria:

- every PR clearly targets either v4 lane or v5 lane
- no v5 feature changes accepted in v4 paths
- no new test files are added outside `v4/tests/` or `v5/tests/`
- no pipelines write to unversioned artifact roots (`generated/`, `build/`, `dist/`)

### Phase 1 - Inventory and Mapping

Objective:

- map all active v4 entities to target v5 class/object bindings and explicit layer placement

Actions:

- build `v4-to-v5` mapping table for L1/L4/L5 entities
- classify unresolved entities and capability gaps
- run automated mapping/backlog/bindings gate (`make phase1-gate`)
- enforce layer contract gate for class/object/instance alignment (`make validate-v5-layers`)

Exit criteria:

- 100% active entities have planned `class_ref` and `object_ref`
- `phase1-module-backlog.yaml` has zero unresolved gaps
- `instance-bindings.yaml` is synchronized with mapping and `make phase1-gate` passes
- `instance-bindings.yaml` has explicit `layer` for every row
- `make validate-v5-layers` passes with no layer/dependency violations

### Phase 1B - L2/L3/L6/L7 Inventory and Mapping

Objective:

- extend v4-to-v5 mapping to cover infrastructure layers (L2-L3) and operational layers (L6-L7)

Actions:

- inventory v4 L2 entities: bridges, VLANs, firewall rules, QoS policies
- inventory v4 L3 entities: storage pools, volumes, media registry
- inventory v4 L6 entities: healthchecks, alerts, dashboards
- inventory v4 L7 entities: workflows, backup policies, power resilience rules
- extend `v4-to-v5-mapping.yaml` with L2/L3/L6/L7 groups
- extend `instance-bindings.yaml` export to include new groups

Exit criteria:

- 100% L2/L3/L6/L7 entities have planned `class_ref` and `object_ref`
- `instance-bindings.yaml` includes `l2_network`, `l3_storage`, `l6_observability`, `l7_operations` groups
- `layer-contract.yaml` includes `group_layers` mapping for all 8 layers

### Phase 2 - Class Module Coverage (L1/L4/L5)

Objective:

- create/complete class modules required by mapped L1/L4/L5 entities

Actions:

- define class contracts and capability packs
- enforce capability checker coverage for new classes
- maintain `layer-contract.class_layers` coverage for every class module

Exit criteria:

- all mapped object targets reference existing class modules
- every class module has explicit allowed layer policy in `layer-contract.yaml`

### Phase 2B - Class Module Coverage (L2/L3/L6/L7)

Objective:

- create class modules for infrastructure and operational layers

Actions:

- define L2 classes: `class.network.bridge`, `class.network.vlan`, `class.network.firewall_rule`, `class.network.qos`
- define L3 classes: `class.storage.pool`, `class.storage.volume`, `class.storage.media`
- define L6 classes: `class.observability.healthcheck`, `class.observability.alert`, `class.observability.dashboard`
- define L7 classes: `class.operations.workflow`, `class.operations.backup`, `class.operations.policy`
- add cross-layer dependency rules to `layer-contract.yaml`

Exit criteria:

- all L2/L3/L6/L7 mapped objects reference existing class modules
- cross-layer dependency rules are enforced in `validate-v5-layers`

### Phase 3 - Object Module Coverage (L1/L4/L5)

Objective:

- create/complete object modules for all mapped L1/L4/L5 implementations

Actions:

- define object contracts and supported capabilities
- validate class/object compatibility
- validate object layer overrides (if present) are subset of class layers

Exit criteria:

- all mapped instance targets resolve to valid objects
- all object modules satisfy layer inheritance rules

### Phase 3B - Object Module Coverage (L2/L3/L6/L7)

Objective:

- create object modules for infrastructure and operational layers

Actions:

- define L2 objects: `obj.proxmox.bridge`, `obj.mikrotik.vlan`, `obj.mikrotik.firewall.*`
- define L3 objects: `obj.proxmox.storage.lvm`, `obj.proxmox.storage.zfs`, `obj.nfs.volume`
- define L6 objects: `obj.prometheus.alert`, `obj.grafana.dashboard`, `obj.uptime.healthcheck`
- define L7 objects: `obj.ansible.workflow`, `obj.proxmox.backup`, `obj.mikrotik.scheduler`

Exit criteria:

- all L2/L3/L6/L7 instance targets resolve to valid objects
- cross-layer references pass dependency direction validation

### Phase 4 - Topology Data Migration

Objective:

- migrate instance data to explicit v5 bindings

Actions:

- add `class_ref` and `object_ref` for migrated entities in `v5/topology/instances/home-lab/`
- add explicit `layer` for migrated entities in `v5/topology/instances/home-lab/`
- keep legacy-only fields out of new files

Exit criteria:

- v5 compilation passes with no unresolved class/object links
- v5 layer contract validation passes for instances and runtime target dependencies

### Phase 5 - Lock and Profile Operationalization

Objective:

- make version and profile governance executable

Actions:

- finalize `v5/topology/model.lock.yaml`
- finalize `v5/topology/profile-map.yaml` with `production/modeled/test-real`
- enforce strict model-lock in CI for v5 lane

Exit criteria:

- all three profiles compile and validate
- compatibility checks pass for substitutions and overrides

### Phase 6 - Generation and Validation Parity

Objective:

- achieve functional parity for generated artifacts

Actions:

- route v5 generation from canonical JSON
- compare key outputs v4 vs v5 for production baseline
- close parity gaps or explicitly document accepted differences

Exit criteria:

- parity checklist approved for production-critical artifacts

### Phase 7 - Plugin Microkernel Migration (ADR 0063)

Objective:

- migrate runtime extension model to plugin architecture

Actions:

- introduce plugin manifest schema and registry
- migrate generators first, then validators, then compiler hooks
- remove hardcoded dispatch from v5 runtime

Exit criteria:

- new module onboarding requires no core branching
- plugin dependency/order rules enforced in CI

### Phase 8 - Cutover and Legacy Retirement Preparation

Objective:

- make v5 the default operational lane

Actions:

- switch primary CI and build/deploy defaults to v5 lane
- keep v4 lane in maintenance mode for defined period
- prepare removal plan for legacy-only fields per timeline

Exit criteria:

- v5 lane is default for production workflows
- legacy removal gate date and rollback policy are documented

---

## Implementation Status Snapshot (as of 2026-03-06, updated)

Current measured status:

- Phase 0 completed (workspace split and artifact root renaming):
  - created dual-lane roots `v4/` and `v5/`
  - moved legacy operational tree to `v4/` (`topology`, `topology-tools`, `tests`)
  - moved v4-dependent folders to `v4/` (`ansible`, `deploy`, `manual-scripts`, `scripts`, `terraform-overrides`, `local`)
  - renamed artifact roots: `generated/` → `v4-generated/`, `dist/` → `v4-dist/`
  - created v5 artifact roots: `v5-generated/`, `v5-build/`, `v5-dist/`
  - added lane commands: `validate-v4`, `validate-v5`, `build-v4`, `build-v5` (root `Makefile`, `v5/scripts/lane.py`)
  - enabled CI lane split via `.github/workflows/lane-validation.yml` (`validate-v4` job + `validate-v5` job)
  - fixed v4/terraform symlink to point to `../v4-generated/terraform/proxmox`
- v5 module structure initialized:
  - moved `class-modules/` from v4/topology to v5/topology (router class defined)
  - moved `object-modules/` from v4/topology to v5/topology (mikrotik objects defined)
  - copied `model.lock.yaml` to v5/topology
- restored v4 lane functional integrity after path split:
  - fixed v4 runtime/generator/deploy path resolution for moved roots
  - aligned native/dist/parity tooling to `v4/*` sources
  - restored legacy compatibility for test/runtime callers using `topology.yaml` and `topology-tools/templates` defaults
  - added v4 test bootstrap (`v4/tests/conftest.py`) for deterministic module resolution in dual-lane layout
- v4 verification evidence (2026-03-06):
  - `validate-topology` (strict): PASS
  - `compile-topology` (strict model-lock): PASS
  - `regenerate-all` (strict, fail-on-validation): PASS
  - `make -f v4/deploy/Makefile validate`: PASS
  - `make -f v4/deploy/Makefile generate`: PASS
  - `make -f v4/deploy/Makefile assemble-dist`: PASS
  - `make -f v4/deploy/Makefile check-parity`: PASS
  - `check-terraform-override-flow`: PASS
  - `pytest v4/tests`: PASS (`210 passed`, `1 skipped`)
- migration progress:
  - Phase 0 complete
  - Phase 1 mapping baseline completed and reconciled for active L1/L4/L5 entities:
    - `v5/topology/instances/home-lab/v4-to-v5-mapping.yaml` has `class_ref` + `object_ref` for all 44 entities (`mapped=44`, `pending=0`, `gap=0`)
    - duplicate L5 IDs are disambiguated with composite instance IDs (`service_id@runtime_type:target_ref`)
    - automated phase gate added: `v5/scripts/validate_phase1_gate.py`
    - lane command `phase1-gate` added (`make phase1-gate`) and included in `validate-v5` flow
    - machine-readable gate report is exported to `v5-build/diagnostics/phase1-gate-report.json`
    - normalized instance export includes explicit `layer` per row
    - layer contract introduced: `v5/topology/layer-contract.yaml`
    - automated layer validator added: `v5/scripts/validate_v5_layer_contract.py`
    - machine-readable layer report is exported to `v5-build/diagnostics/layer-contract-report.json`
    - lane command `validate-v5-layers` added (`make validate-v5-layers`) and included in `validate-v5` flow
  - Phase 2/3 scaffolding advanced:
    - class module set expanded to 21 files under `v5/topology/class-modules/classes/`
    - object module set expanded to 34 files under `v5/topology/object-modules/`
    - `v5/topology/instances/home-lab/phase1-module-backlog.yaml` currently has no unresolved class/object gaps
  - Phase 4 preparation started:
    - v5 topology manifest created: `v5/topology/topology.yaml`
    - normalized instance export created: `v5/topology/instances/home-lab/instance-bindings.yaml`
    - export is generated from mapping via `v5/scripts/export_v5_instance_bindings.py`
    - v5 compiler/effective model now requires and carries explicit instance `layer`
    - v5 compiler introduced: `v5/topology-tools/compile-topology.py`
    - `validate-v5` now runs manifest/scaffold checks and strict model-lock compile into:
      - `v5-build/effective-topology.json`
      - `v5-build/diagnostics/report.json`
      - `v5-build/diagnostics/report.txt`
- class/object module coverage for mapped entities is complete at scaffold level; capability depth remains iterative
- v5-specific CI lane runs scaffold gate and compile gate (strict model-lock)

This snapshot is informational and must be updated at each phase gate review.

---

## v5 Migration Completion Criteria (100%)

Migration is considered 100% complete only when all criteria are true:

1. repository structure is fully dual-lane (`v4/` frozen, `v5/` active/default)
2. test suites are fully dual-lane (`v4/tests/` for legacy, `v5/tests/` for new system)
3. all production-relevant entities in v5 have explicit `class_ref` and `object_ref`
4. all production-relevant entities in v5 have explicit `layer` and pass layer policy checks
5. `v5/topology/layer-contract.yaml` has complete class layer coverage for active modules
6. runtime dependency rules (at least `runtime.target_ref`) pass direction and allowed-target checks
7. `v5/topology/model.lock.yaml` is complete and CI runs in strict mode
8. `v5/topology/profile-map.yaml` includes `production`, `modeled`, `test-real` and all pass
9. artifact roots are fully versioned (`v4-build`, `v4-dist`, `v4-generated`, `v5-build`, `v5-dist`, `v5-generated`)
10. moved v4 scripts write only to `v4-*` artifact roots
11. diagnostics schema validation passes on every v5 compile run
12. capability contract checks pass for all v5 class/object modules
13. production-critical generated artifacts reach approved parity vs v4 baseline
14. plugin microkernel migration phase (ADR 0063) is complete for v5 lane
15. v5 lane is default in CI and release workflow for at least one stabilization cycle
16. rollback procedure from v5 default back to v4 lane is documented and tested

---

## Validation and Quality Gates

Minimum gates:

1. v4 lane compile/validate (stability gate)
2. phase-1 mapping/backlog/bindings gate (`make phase1-gate`)
3. v5 layer contract gate (`make validate-v5-layers`)
4. v5 lane compile/validate (progress gate)
5. v4 test suite runs from `v4/tests/` only
6. v5 test suite runs from `v5/tests/` only
7. v4 lane writes artifacts only to `v4-build/`, `v4-dist/`, `v4-generated/`
8. v5 lane writes artifacts only to `v5-build/`, `v5-dist/`, `v5-generated/`
9. diagnostics report schema validation
10. strict model-lock validation on v5 lane
11. capability contract validation
12. profile matrix (`production`, `modeled`, `test-real`) on v5 lane
13. parity checks for production-critical generated artifacts

---

## Operational Guardrails (Normative)

### 1. CI Path Guard Enforcement

Dual-lane path policy is enforced in CI with blocking checks:

- v4-only changes are allowed under `v4/**`, `v4-build/**`, `v4-dist/**`, `v4-generated/**`
- v5-only changes are allowed under `v5/**`, `v5-build/**`, `v5-dist/**`, `v5-generated/**`
- PRs touching both lanes require explicit `dual-lane-approved` label and migration lead approval
- adding tests outside `v4/tests/**` or `v5/tests/**` is rejected

### 2. Parity Acceptance Criteria (Phase 6)

Parity is semantic, not byte-for-byte.

Critical artifacts (must pass with zero critical diffs):

1. Terraform (MikroTik)
2. Terraform (Proxmox)
3. Ansible inventory

High-priority artifacts (allowed only documented non-critical diffs):

1. network diagrams
2. topology documentation
3. bootstrap scripts

Escalation trigger:

- critical parity differences >5% blocks cutover and requires root-cause review

### 3. Rollback Trigger Criteria (Phase 8 and Stabilization)

Rollback to v4 default lane is mandatory when any trigger occurs:

1. production-profile v5 compile fails in 2 consecutive pipeline runs
2. critical parity differences exceed 5% after declared parity complete
3. production incident is traced to v5 lane output or runtime behavior

Rollback actions:

1. switch CI default lane back to v4
2. freeze further v5 cutover changes
3. open incident review with corrective action plan

---

## Consequences

### Positive

1. migration work is executable, phased, and auditable
2. teams can build v5 without destabilizing v4 operations
3. file-level separation removes ambiguity between old and new systems
4. plugin migration (ADR 0063) is sequenced after model stabilization

### Negative

1. temporary duplication of topology/runtime roots
2. CI complexity increases with dual lanes
3. parity management requires disciplined tracking

---

## Risks and Mitigations

1. Risk: accidental v5 logic added to v4 paths
   - Mitigation: explicit directory policy and CI path guards
2. Risk: v5 drift from operational reality
   - Mitigation: profile matrix validation + parity gates
3. Risk: capability sprawl during module expansion
   - Mitigation: catalog/packs policy + promotion rules
4. Risk: layer drift (class/object/instance mismatch or upward dependencies)
   - Mitigation: `layer-contract.yaml` + `validate-v5-layers` gate + explicit `instance.layer`
5. Risk: plugin migration destabilizes pipeline
   - Mitigation: ADR 0063 phased adoption after parity baseline

---

## Open Questions

1. stabilization cycle exact duration before final v4 retirement (recommended baseline: 1 release cycle)

---

## References

### Related ADRs

- ADR 0048: `adr/0048-topology-v4-architecture-consolidation.md`
- ADR 0058: `adr/0058-core-abstraction-layer.md` (superseded)
- ADR 0059: `adr/0059-repository-split-and-class-object-instance-module-contract.md` (superseded)
- ADR 0060: `adr/0060-yaml-to-json-compiler-diagnostics-contract.md` (superseded)
- ADR 0061: `adr/0061-base-repo-versioned-class-object-instance-and-test-profiles.md` (superseded)
- ADR 0063: `adr/0063-plugin-microkernel-for-compiler-validators-generators.md` (proposed)
- Analysis package: `adr/0062-analysis/`

### Runtime Contracts

- v5 compiler: `v5/topology-tools/compile-topology.py`
- v5 layer contract: `v5/topology/layer-contract.yaml`
- v5 layer validator: `v5/scripts/validate_v5_layer_contract.py`
- v5 phase1 gate: `v5/scripts/validate_phase1_gate.py`
- legacy compiler: `v4/topology-tools/compile-topology.py`
- Diagnostics schema: `v4/topology-tools/schemas/diagnostics.schema.json`
- Error catalog: `v4/topology-tools/data/error-catalog.yaml`
- model.lock schema: `v4/topology-tools/schemas/model-lock.schema.json`
- profile map schema: `v4/topology-tools/schemas/profile-map.schema.json`
- Capability checker: `v4/topology-tools/check-capability-contract.py`

### Register

- ADR register: `adr/REGISTER.md`
