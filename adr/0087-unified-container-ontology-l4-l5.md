# ADR 0087: Unified Container Ontology for L4/L5

**Status:** Implemented (Phase 1 GATE PASSED; Phase 2 core complete; Phase 3-6 pending)
**Date:** 2026-04-03

| Field | Value |
|-------|-------|
| **Status** | Implemented (Phase 1 GATE PASSED; Phase 2 core complete; Phase 3-6 pending) |
| **Date** | 2026-04-03 |
| **Deciders** | dmpr |
| **Supersedes** | — |
| **Related** | ADR 0026 (L3/L4 taxonomy), ADR 0034 (L4 modularization), ADR 0042 (L5 services), ADR 0064 (firmware/OS taxonomy) |

## Context

The current topology models only LXC containers at L4 using a single class
`class.compute.workload.container`. Docker containers have no L4 representation —
services on Docker hosts reference L1 devices directly, breaking the uniform
L5→L4→L1 stack. VMs (QEMU/KVM) are not modeled at all despite Proxmox supporting
both CT and VM workloads.

As the infrastructure grows with more container types, hosts, and services,
the flat single-class model will not scale. Each container type (LXC, Docker, VM)
has fundamentally different isolation, lifecycle, storage, and networking models
that require distinct class definitions.

Additionally, containers are virtual computers with internal resources (networks,
volumes, DNS) that constitute a nested topology. The current model handles these
as flat inline properties, which will not scale to Docker Compose stacks or
multi-container deployments.

## Decision

### 1. Two-axis class hierarchy: hypervisor platforms (L1) + workload types (L4)

**L1 Hypervisor hierarchy** (WHERE workloads run):
```
class.compute.hypervisor              (abstract base, refactored from current)
├── class.compute.hypervisor.proxmox  (Proxmox VE — QEMU/KVM + LXC)
├── class.compute.hypervisor.vbox     (Oracle VirtualBox)
├── class.compute.hypervisor.hyperv   (Microsoft Hyper-V)
├── class.compute.hypervisor.vmware   (VMware ESXi / Workstation)
└── class.compute.hypervisor.xen      (Xen / XCP-ng)
```

Each hypervisor class declares constraints: `allowed_disk_formats`,
`allowed_disk_buses`, `allowed_firmware`, `platform_config_schema`.
These are validated against L4 VM objects at compile time.

Hypervisor hosting model is explicit:
- `execution_model: bare_metal | hosted`
- For `bare_metal`: `hardware_ref` is required (hypervisor runs directly on hardware)
- For `hosted`: `host_os_ref` is required (hypervisor runs on host OS)
- For mixed-mode platforms (for example Hyper-V/VMware), class may declare
  `execution_model_support: [bare_metal, hosted]`, but each instance must still
  satisfy one concrete mode with the corresponding required reference.

**L4 Workload hierarchy** (WHAT runs on the hypervisor):
```
class.compute.workload                (abstract base)
├── class.compute.workload.lxc        (LXC containers)
├── class.compute.workload.vm         (VMs — single class, hypervisor-agnostic)
├── class.compute.workload.docker     (Docker/OCI containers)
└── class.compute.workload.pod        (future: K8s pods)
```

The VM class carries common properties (disks, boot_order, cloud_init)
plus a `platform_config` extension bag validated by the host's hypervisor class.

### 2. Promote Docker containers to L4

Every Docker container gets an L4 instance with:
- `host_ref` → L1 device OR L4 LXC container (Docker-in-LXC)
- Image reference (repository, tag, digest)
- Port mappings, volumes, environment
- `compose_group` for stack grouping

L5 services reference L4 Docker containers (not L1 devices directly).
The old pattern (L5→L1) is deprecated with a WARNING.

### 3. Model container runtime as host capability

The container runtime (Docker Engine, LXC runtime, QEMU) is modeled as
a capability on the host:
- `cap.compute.runtime.container_host` — host can run container workloads
- `cap.compute.runtime.vm_host` — host can run VM workloads
- `vendor.runtime.docker.host` — host explicitly provides Docker engine semantics

Validators enforce: workload host must have matching runtime capability.
For `class.compute.workload.docker`, host must be a container host and expose
Docker runtime semantics.

### 4. L3↔L4 storage integration with disk image model

Extend `class.storage.volume` with:
- `format` (qcow2, vmdk, vdi, vhdx, raw, subvol, iso)
- `bus_attachment` (scsi0, virtio1 — for VMs)
- `role` (boot, data, rootfs, cdrom, efivars, cloudinit)
- `data_asset_ref` — links volume to L3 data_asset for governance (ADR 0026 D5)

Compile-time validation chain:
- `volume.format ∈ pool.supported_formats` (L3 internal)
- `volume.format ∈ hypervisor.allowed_disk_formats` (L3↔L1 cross-layer)
- `disk.bus ∈ hypervisor.allowed_disk_buses` (L4↔L1 cross-layer)

### 5. Introduce topology scope for nested resources (Phase 5)

Containers that host sub-containers (e.g., LXC with Docker inside) define
a `topology_scope` with internal networks and shared volumes. Scope resolution:
- External refs (`inst.*`) resolve in parent scope
- Internal refs (`scope.{container}.*`) resolve within container scope
- Maximum nesting depth: 2 levels
- Anti-cycle invariant: `host_ref` graph must be a DAG — validator runs
  DFS-based cycle detection at compile time and rejects any cycle
  (A.host_ref → B, B.host_ref → A) or depth > 2 (see `ONTOLOGY-PROPOSAL.md` §3.5)

### 5a. VM storage invariants

VM disk lists carry structural invariants enforced by validators:
- Each disk must have a unique `disk_id` within the VM instance
- Each `bus:slot` pair (e.g., `scsi:0`, `ide:2`) must be unique per VM
- Exactly one disk with `role: boot` must exist (zero or two+ is an error)
- `boot_order` list must reference only existing `disk_id` values
- Non-ephemeral disks (all except `cloudinit`) must have a `volume_ref`

### 5b. Deprecation policy

Pattern transitions follow a three-stage lifecycle:
1. **WARNING** — old pattern compiles but emits deprecation diagnostic
2. **ERROR** — old pattern fails compilation (enforced after stabilization window;
   `--allow-deprecated` flag available as temporary CI escape hatch)
3. **REMOVAL** — old alias/code deleted from codebase; escape hatch removed

Schedule is phase-relative (see `ONTOLOGY-PROPOSAL.md` §11.1 for full table):
- `class.compute.workload.container` alias: WARNING at Phase 1, ERROR at Phase 3
- L5→L1 Docker target_ref: WARNING at Phase 1, ERROR at Phase 3
- `L4-platform/vms/` alias: WARNING at Phase 3, ERROR at Phase 4
- All deprecated patterns removed at Phase 6 GA

### 5c. Path contract migration

Current runtime validates `<layer-bucket>/<group>/<instance>.yaml` (3 segments).
Host-sharded layout is `<layer-bucket>/<group>/<host-shard>/<instance>.yaml` (4 segments).
Migration approach:
- Loader accepts both 3-segment and 4-segment paths during transition
- `group` field in YAML payload remains the canonical group (`lxc`, `docker`, `vm`)
- `host-shard` segment is validated against `host_ref` but is NOT a group
- After cutover: 3-segment paths for L4/L5 sharded groups emit ERROR

### 5d. Docker host_ref semantics

Docker class defines `host_ref` inherited from base `class.compute.workload`.
For Docker containers the host may be:
- L1 device (direct Docker host, e.g., `srv-orangepi5`)
- L4 LXC container (Docker-in-LXC, e.g., `lxc-docker`)

Validators resolve `host_ref` target and check it exposes both
`cap.compute.runtime.container_host` and `vendor.runtime.docker.host`.

### 5e. Mixed-mode hypervisor instance selection

For platforms with `execution_model_support: [bare_metal, hosted]`,
each hypervisor **instance** must declare `execution_model` explicitly
(choosing one of the supported values). The corresponding linkage ref
(`hardware_ref` or `host_os_ref`) is then validated as required.

### 5f. Runtime capability schema contract

Runtime capabilities follow a two-tier schema:
- **Common capability** (`cap.compute.runtime.container_host`,
  `cap.compute.runtime.vm_host`) — framework-defined with required fields:
  `runtime_type`, `runtime_version`, `api_endpoint`, optional `features[]`.
- **Vendor capability** (`vendor.runtime.docker.host`,
  `vendor.runtime.routeros.container`, etc.) — extends the common capability
  with platform-specific properties (socket, compose_version, etc.).

Vendor capabilities implicitly satisfy their parent common capability.
Validators resolve this inheritance chain when checking workload host
requirements. Full schema definitions: `ONTOLOGY-PROPOSAL.md` §5.3.

### 5g. Ownership proof contract

Before deleting or moving class/object/instance files, ownership must be proven
using one of three methods (in priority order):

1. **State file match** — previous compilation state contains the file with
   matching content hash
2. **Path prefix match** — file path falls under a known module prefix owned
   by the current operation (e.g., `topology/class-modules/compute/`)
3. **Ownership marker** — file contains `# owner: <module-id>` comment (fallback)

CI gate blocks delete/move operations without ownership proof. Ownership
conflicts (overlapping prefixes from different modules) are hard errors.

### 5h. Migration state model

Each workload family tracks migration progress via `migration_mode` in its
manifest or feature flag:

| State | Meaning | Behavior |
|-------|---------|----------|
| `legacy` | Not yet migrated | Old patterns accepted, no warnings |
| `migrating` | Migration in progress | Old patterns emit WARNING |
| `migrated` | Migration complete | Old patterns emit ERROR |
| `rollback` | Temporary reversion | Old patterns accepted, escalation timer starts |

State transitions:
- `legacy` → `migrating`: Phase starts
- `migrating` → `migrated`: Phase gate passed
- `migrated` → `rollback`: Emergency reversion (requires justification)
- `rollback` → `migrating`: Resume migration (resets escalation timer)

### 5i. Sunset policy

Deprecated patterns follow phase-relative sunset schedule:

| Pattern | WARNING | ERROR | REMOVAL |
|---------|---------|-------|---------|
| `class.compute.workload.container` alias | Phase 1 + 0d | Phase 3 + 0d | Phase 6 GA |
| L5→L1 Docker target_ref | Phase 1 + 0d | Phase 3 + 0d | Phase 6 GA |
| `L4-platform/vms/` path alias | Phase 3 + 0d | Phase 4 + 0d | Phase 6 GA |
| 3-segment L4/L5 paths | Phase 1 + 14d | Phase 3 + 14d | Phase 6 GA |

Grace period: 14 days between phase gate and ERROR promotion for path-based
patterns. `--allow-deprecated` CI flag available during grace period only.

### 5j. Rollback escalation policy

Rollback mode is intended for emergency reversion, not permanent state.

| Duration | Action |
|----------|--------|
| 0-7 days | Rollback accepted silently |
| 7-14 days | CI emits WARNING: "Rollback exceeds 7 days, plan migration resume" |
| 14+ days | CI emits BLOCKING WARNING (requires `--force-rollback` to proceed) |
| 30+ days | Escalation to architecture review required |

Rollback events are logged to audit trail with timestamp and justification.

### 5k. Schema versioning policy

Class definitions include `version` field following semver:
- **Major**: Breaking changes to required properties or validation rules
- **Minor**: New optional properties, new enum values
- **Patch**: Documentation, comments, non-functional changes

Example: `class.compute.hypervisor` base class is `version: 2.0.0` after
the platform split refactoring (was implicit v1.x before ADR 0087).

Runtime validates that object `class_ref` targets a compatible class version.
Incompatible version references (major mismatch) are compile-time errors.

### 6. Organize L4 and L5 by host/device sharding

```
projects/home-lab/topology/instances/L4-platform/
  lxc/
    srv-gamayun/
      lxc-postgresql.yaml
      lxc-redis.yaml
      lxc-nginx-proxy.yaml
    rtr-mikrotik-chateau/
      lxc-*.yaml (if used)
  docker/
    srv-orangepi5/
      docker-grafana.yaml
      docker-prometheus.yaml
    lxc-docker/                   ← nested host shard (L4 host)
      docker-*.yaml
    rtr-mikrotik-chateau/
      docker-adguard.yaml
      docker-mosquitto.yaml
  vm/
    srv-gamayun/
      vm-*.yaml

projects/home-lab/topology/instances/L5-application/services/
  srv-gamayun/
    svc-grafana@lxc.lxc-grafana.yaml
    svc-prometheus@lxc.lxc-prometheus.yaml
  srv-orangepi5/
    svc-grafana@docker.srv-orangepi5.yaml
    svc-nextcloud@docker.srv-orangepi5.yaml
  rtr-mikrotik-chateau/
    svc-adguard.yaml
    svc-mosquitto.yaml

Sharding rule:
- L4 path format: `L4-platform/<workload-kind>/<host-shard>/<instance>.yaml`
  (canonical workload-kind is `vm`; legacy `vms` accepted only during transition)
- L5 path format: `L5-application/services/<host-shard>/<service>.yaml`
- `host-shard` maps to `host_ref` for L4 workloads and runtime host target for L5 services.
- Legacy flat layout remains supported only during transition and emits warnings.
```

## Implementation Plan

| Phase | Scope | Dependencies |
|-------|-------|-------------|
| **Phase 1**: Docker Promotion (MVP) | New L4 workload classes, Docker at L4, L5 rewiring | None |
| **Phase 2**: Hypervisor Platform Split | Split `class.compute.hypervisor` into platform subclasses | None (parallel with Phase 1) |
| **Phase 3**: Multi-Hypervisor VM Support | VM class + objects + hypervisor↔VM validation | Phase 2 |
| **Phase 4**: L3 Storage Integration | Volume format/role/data_asset_ref, cross-layer validation | Phase 1 + 3 |
| **Phase 5**: Nested Topology | topology_scope mechanism | Phase 1 |
| **Phase 6**: Stack Objects | Docker Compose generation | Phase 1 + 5 |

Detailed implementation plan: `adr/0087-analysis/IMPLEMENTATION-PLAN.md`

### Phase Gate Requirements

Each phase gate requires:

| Phase | Test Requirements |
|-------|-------------------|
| Phase 1 | Unit tests for new workload classes; integration test for L5→L4 Docker ref; negative test for host_ref cycle |
| Phase 2 | Unit tests for hypervisor subclasses; integration test for execution_model linkage |
| Phase 3 | Cross-layer validation tests (VM↔hypervisor); negative tests for format/bus mismatch |
| Phase 4 | Volume↔pool format validation tests; data_asset_ref resolution tests |
| Phase 5 | Scope resolution tests; depth limit enforcement tests |
| Phase 6 | Docker Compose generation tests; stack grouping tests |

All phases: `pytest tests -q` must pass; `compile-topology.py` exit 0; `lane.py validate-v5` exit 0.

## Out of Scope

The following items are explicitly deferred to future ADRs:

| Item | Reason | Future ADR |
|------|--------|------------|
| Resource profile class hierarchy (GAP-7) | Orthogonal concern, scope creep risk | TBD |
| Multi-host container orchestration (GAP-8) | Enterprise scope, home lab is single-host | TBD |
| Kubernetes pod class implementation | Future workload type, Phase 1-6 focus on LXC/Docker/VM | TBD |

## Acceptance Criteria

### Phase 1: Docker Promotion

- **AC-1**: `class.compute.workload.lxc` exists and validates
- **AC-2**: `class.compute.workload.docker` exists and validates
- **AC-3**: All existing LXC instances compile with new class
- **AC-4**: Docker containers have L4 instances (not L5→L1 direct)
- **AC-5**: L5→L1 Docker refs emit WARNING
- **AC-6**: `host_ref` cycle detected and rejected
- **AC-7**: Host-sharded L4/L5 paths accepted by loader

### Phase 2: Hypervisor Platform Split

- **AC-8**: `class.compute.hypervisor.proxmox` exists with vm_constraints
- **AC-9**: `obj.proxmox.ve` references new hypervisor class
- **AC-10**: execution_model linkage validated (bare_metal→hardware_ref)
- **AC-11**: Other hypervisor classes (vbox, hyperv, vmware, xen) exist

### Phase 3: Multi-Hypervisor VM Support

- **AC-12**: `class.compute.workload.vm` exists with disk/boot_order schema
- **AC-13**: VM disk format validated against hypervisor.allowed_disk_formats
- **AC-14**: VM disk bus validated against hypervisor.allowed_disk_buses
- **AC-15**: disk_id uniqueness enforced
- **AC-16**: bus:slot uniqueness enforced
- **AC-17**: Exactly one boot disk enforced
- **AC-18**: boot_order references validated

### Phase 4: L3 Storage Integration

- **AC-19**: Volume format property added to class.storage.volume
- **AC-20**: Volume↔pool format compatibility validated
- **AC-21**: data_asset_ref resolves to valid L3 entity
- **AC-22**: Cross-layer volume↔hypervisor format validated

### Phase 5: Nested Topology

- **AC-23**: topology_scope property accepted on workload instances
- **AC-24**: Scope reference resolution works (scope.* vs inst.*)
- **AC-25**: Nesting depth > 2 rejected

### Phase 6: Stack Objects

- **AC-26**: compose_group property groups Docker containers
- **AC-27**: Docker Compose generator produces valid YAML
- **AC-28**: `docker compose config` validates generated files

### Migration Governance

- **AC-29**: migration_mode tracked per workload family
- **AC-30**: Ownership proof blocks unproven delete/move
- **AC-31**: Rollback escalation warnings emitted after 7 days
- **AC-32**: Sunset schedule enforced (WARNING→ERROR transitions)

## Consequences

### Positive
- Uniform L5→L4→L1 reference chain for ALL container types
- Type-safe validation per container kind
- Docker containers visible in inventory, targetable by L6/L7
- Hypervisor platform constraints declared once at L1, validated at compile time against L4 VMs
- Multi-hypervisor support (Proxmox, VirtualBox, Hyper-V, VMware, Xen) without L4 class explosion
- L3↔L4 governance chain: data_asset criticality → backup policy → volume placement
- Extensible to pods and future container runtimes
- Nested topology enables Docker Compose generation from topology

### Negative
- More L4 files (estimated +12 Docker containers, +3 VMs)
- More L3 files for VM disk volumes (~2 per VM)
- Migration effort to rewire L5 Docker services from L1 to L4
- Class rename (`container` → `lxc`) requires global search-replace
- Hypervisor class split requires updating `obj.proxmox.ve` class_ref

### Risks
- Topology file count grows ~30% at L3+L4 (mitigated by defaults inheritance)
- Nested topology scope adds reference resolution complexity (mitigated by depth limit)
- `platform_config` bag validation requires per-hypervisor schema maintenance
- Migration is not purely additive because class rename and hypervisor split touch existing refs
- Host-based sharding requires validator/runtime path policy updates

## Analysis Artifacts

- `adr/0087-analysis/GAP-ANALYSIS.md` — AS-IS vs TO-BE, 11 identified gaps
- `adr/0087-analysis/ONTOLOGY-PROPOSAL.md` — Full ontology design with class definitions, examples, scaling analysis
- `adr/0087-analysis/IMPLEMENTATION-PLAN.md` — Phase-by-phase implementation tasks
- `adr/0087-analysis/VALIDATION-PLUGIN-GAP-ANALYSIS.md` — Validator plugin migration analysis
- `adr/0087-analysis/SWOT-ANALYSIS.md` — SWOT matrix and risk assessment
- `adr/0087-analysis/PRE-IMPLEMENTATION-REVIEW.md` — Pre-implementation checklist and review gate

## References

- [ADR 0026](0026-l3-l4-taxonomy-refactoring-storage-chain-and-platform-separation.md) — L3/L4 taxonomy baseline
- [ADR 0034](0034-l4-platform-modularization-and-runtime-taxonomy.md) — L4 platform modularization (superseded by 0062)
- [ADR 0042](0042-l5-services-modularization.md) — L5 services modularization
- [ADR 0062](0062-modular-topology-architecture-consolidation.md) — Modular Class-Object-Instance architecture
- [ADR 0064](0064-os-taxonomy-object-property-model.md) — Firmware/OS taxonomy (two-entity model)
- [ADR 0074](0074-v5-generator-architecture.md) — V5 Generator architecture contract
- Schemas: `schemas/class.compute.workload.*.schema.json` (to be created)
- Docs: `docs/guides/CONTAINER-ONTOLOGY.md` (to be created)
