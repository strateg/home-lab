# ADR 0059: Repository Split and Class-Object-Instance Module Contract

**Date:** 2026-03-06
**Status:** Superseded by ADR 0062 (Harmonized with ADR 0064 on 2026-03-09)
**Related:** ADR 0058 (Core Abstraction Layer and Device Module Architecture), ADR 0060 (YAML-to-JSON Compiler and Diagnostics Contract), ADR 0061 (Base Repo with Versioned Class-Object-Instance and Test Profiles)
**Supersedes:** ADR 0058 (model contract scope)
**Superseded By:** [ADR 0062](0062-modular-topology-architecture-consolidation.md)
**Harmonized With:** ADR 0064 (Firmware + OS Two-Entity Model)

---

## Context

ADR 0058 introduced the direction "core abstractions + device modules", but it did not yet fix:

1. The exact boundary for a future split into two repositories
2. The formal class-object-instance contract for topology entities
3. The transition model where both layers live in one repository first

The current codebase confirms the need for stronger boundaries:

- `topology-tools/regenerate-all.py` contains a hardcoded vendor pipeline (Proxmox, MikroTik, OrangePi5)
- `topology-tools/scripts/validators/checks/references.py` contains platform-specific rules (`expected 'proxmox'`)
- `topology-tools/scripts/generators/terraform/mikrotik/generator.py` binds logic to concrete object IDs (for example `mikrotik-chateau`)
- `topology-tools/scripts/generators/common/ip_resolver_v2.py` is still centered around specific workload object kinds (`lxc`, `vm`) instead of a generic compute target contract

At the same time, topology already models reusable concepts (`type: router`, `type: hypervisor`, `model`, `class`), so the project is ready to formalize:

- **Class layer**: abstract entities and semantics (router, switch, bridge, hypervisor, firmware, OS)
- **Object layer**: concrete implementations (MikroTik Chateau LTE7 ax, GL.iNet Slate AX1800, Proxmox, VMware, RouterOS firmware, Linux, Windows, macOS)
- **Instance layer**: deployed nodes in a concrete lab, inheriting class + object contracts with local overrides

Capability modeling introduces an additional complexity risk:

- over-fragmented class hierarchy
- duplicated capabilities across similar objects
- vendor-specific details leaking into class semantics

The model needs explicit simplification rules to stay maintainable.

---

## Decision

### 1. Adopt a Class-Object-Instance Architecture Contract

All infrastructure entities are split into:

- **Class (abstract)**: capability semantics and invariants
- **Object (concrete)**: implementation details, initialization model, generator behavior
- **Instance (deployment)**: concrete topology node with environment-specific values (addresses, bindings, role placement)

Canonical examples:

- `class.network.router` -> `obj.mikrotik.chateau_lte7_ax`, `obj.glinet.slate_ax1800` -> `inst.router.rtr-main-home`, `inst.router.rtr-travel`
- `class.compute.hypervisor` -> `obj.proxmox.hypervisor`, `obj.vmware.hypervisor` -> `inst.hypervisor.hv-gamayun`
- `class.firmware` -> `obj.firmware.mikrotik-routeros7`, `obj.firmware.kvm-ovmf` -> `inst.firmware.routeros-7-prod`, `inst.firmware.ovmf-lab`
- `class.os` -> `obj.os.routeros-7`, `obj.os.debian-12` -> `inst.os.routeros-7-prod`, `inst.os.debian-12-lab`

### 2. Establish Inheritance and Merge Rules

Resolution chain:

- `instance.object_ref` must resolve to an object
- object must declare or infer a class via `object.class_ref`
- instance class contract must match object class contract

Merge precedence for effective model:

- `class.defaults`
- `object.defaults`
- `instance.overrides`

Hard rule: instance overrides must not violate class invariants.

### 3. Define Target Two-Repository Topology

Planned split:

1. **Repository A: `topology-core`**
   - Abstract schema contracts
   - Core validation (class-level and cross-layer invariants)
   - Core generation protocols/interfaces
   - Core documentation generation
   - Shared loader/resolver primitives
2. **Repository B: `home-lab-topology`**
   - Concrete L0-L7 topology
   - Object modules (vendor/model specific)
   - Deployment wrappers and runtime assembly
   - Templates and scripts that depend on object-level behavior

### 4. Stage-1 Transitional Layout in Current Repository

Before split, both layers coexist in one repository:

- `abstract-topology/` - class and object catalogs for abstract planning and contracts
- `topology/` - concrete instance-level topology (existing structure)
- `topology-tools/` - core orchestration and validation/generation runtime
- `topology-tools/modules/` - object modules, each isolated by provider/device/runtime

No behavioral cutover is required at ADR acceptance; this ADR defines the migration contract.

### 5. Module Contract (Mandatory)

Each object module must provide a manifest (format TBD) containing:

- Module ID and version
- Supported class IDs
- Supported object IDs/models
- Optional instance constraints (for example required tags/roles/capabilities)
- Exposed generator entrypoints (`terraform`, `bootstrap`, `docs_ext`, etc.)
- Optional module validators
- Declared capabilities and prerequisites

Core runtime selects modules by object metadata, then validates instance compatibility.

### 6. Validation Boundary

- Core validators own class semantics and cross-layer invariants
- Modules own object-specific checks and object-instance compatibility checks
- Platform-specific checks currently in core validator flows are migrated to module validators in phases

Mandatory validation sequence:

1. Schema validation (class/object/instance documents)
2. Link validation (`instance -> object -> class`)
3. Inheritance validation (effective merge and invariant protection)
4. Layer validation (L0-L7 directional contracts)

### 7. Backward-Compatible Field Evolution

Existing fields (`type`, `class`, `model`, `role`) remain valid during migration.

Additive fields are introduced for explicit binding:

- `class_ref`
- `object_ref`
- `implementation.module`
- `implementation.object`
- `implementation.version` (optional)
- `firmware_ref`
- `os_refs[]`

Legacy software bindings are transitional and deprecated:

- `bindings.firmware`
- `os_primary`, `os_secondary`, `os_tertiary`

Modules may consume either legacy or new fields during transitional phases, but new onboarding must use explicit class-object-instance bindings.

### 8. Simplified Capability Model (Normative)

Capabilities are modeled with three explicit layers:

1. **Capability Catalog (class-module)**
   - Canonical capability IDs and semantics
   - Invariants and compatibility notes
2. **Class Capability Contract**
   - `required_capabilities`
   - `optional_capabilities`
   - `capability_packs` (predefined bundles such as `router-home`, `router-infra`)
3. **Object Capability Binding**
   - `enabled_capabilities` chosen from catalog/packs
   - optional `vendor.*` extensions for non-portable behavior

Complexity guardrails:

- Avoid deep class inheritance for capability reuse; prefer catalog + packs
- Keep capability identifiers flat and stable; no nested capability trees
- Vendor-specific capability keys must be namespaced (`vendor.<name>.*`)

Promotion/refactoring rule:

- keep capability object-local while used by one object only
- promote to class catalog/pack when reused by 2+ objects with same semantics

Validation requirements:

1. object must satisfy class `required_capabilities`
2. object may only enable catalog capabilities (plus `vendor.*`)
3. instance-level requests/overrides cannot require unsupported object capability
4. instance `firmware_ref`/`os_refs[]` must resolve to compatible `inst.firmware.*`/`inst.os.*` entities

---

## Migration Plan

### Phase 0: Boundary Baseline (analysis only)

- Classify scripts/checks into `core` vs `module`
- Map current hardcoded vendor/platform paths
- Publish ownership matrix

### Phase 1: In-Repo Scaffolding

- Create `abstract-topology/`
- Introduce `topology-tools/modules/` root
- Add module manifest schema and loader skeleton

### Phase 2: Class-Object-Instance Schema Rollout

- Extend topology schema with `class_ref`, `object_ref`, and `implementation.*`
- Keep legacy fields for compatibility
- Add validators for explicit class-object-instance consistency and invariant-safe overrides

### Phase 3: First Module Migration

- Move MikroTik, Proxmox, OrangePi5 specifics to modules
- Keep core orchestration unchanged except module dispatch
- Ensure generation output parity

### Phase 4: Pipeline Decoupling

- Replace hardcoded orchestration list with registry-driven execution
- Move object-specific validation paths from core checks to module checks

### Phase 5: Repository Extraction

- Extract `topology-core` as standalone package/repository
- Keep `home-lab-topology` as concrete implementation repository
- Pin dependency version and freeze compatibility contract

---

## Consequences

### Positive

1. New device/object onboarding without core code forks
2. Better reuse of core topology engine across multiple labs/projects
3. Cleaner testing strategy: core tests vs module tests
4. Clear governance boundary across abstraction, implementation, and deployment layers

### Negative

1. Temporary migration complexity and duplicate compatibility logic
2. Need to maintain two release/version streams after repo split
3. Higher discipline required for module and instance contract management

### Risks and Mitigations

1. Risk: abstraction too generic and loses real hardware constraints
   - Mitigation: keep constraints in module validators and capability declarations
2. Risk: pipeline breakage during hardcoded-to-registry migration
   - Mitigation: parity tests on generated outputs for each migrated module
3. Risk: schema churn affects current topology authoring
   - Mitigation: additive schema with deprecation window, not hard cutover

---

## References

- Existing decision: `adr/0058-core-abstraction-layer.md`
- Compiler/diagnostics execution contract: `adr/0060-yaml-to-json-compiler-diagnostics-contract.md`
- Current v5 compiler orchestration: `v5/topology-tools/compile-topology.py`
- Current v5 capability contract validator: `v5/topology-tools/check-capability-contract.py`
- Current v5 lane entrypoint: `v5/scripts/orchestration/lane.py`
- ADR register: `adr/REGISTER.md`
- Commit: harmonization pending
