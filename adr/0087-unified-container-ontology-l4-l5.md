# ADR 0087: Unified Container Ontology for L4/L5

| Field | Value |
|-------|-------|
| **Status** | Accepted |
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
