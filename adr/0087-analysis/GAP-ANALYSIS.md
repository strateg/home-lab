# GAP-ANALYSIS: Container Ontology for L4/L5

**Last updated:** 2026-04-06
**Status:** Gaps addressed in ADR update

## Gap Status Summary

| Gap | Description | Status | Addressed By |
|-----|-------------|--------|--------------|
| GAP-1 | No unified container taxonomy | **CLOSED** | D1 (two-axis hierarchy) |
| GAP-2 | Docker containers have no L4 representation | **CLOSED** | D2 (Docker promotion) |
| GAP-3 | No nested topology / recursive composition | **CLOSED** | D5 (topology_scope) |
| GAP-4 | No container runtime as first-class entity | **CLOSED** | D3 (runtime capabilities) |
| GAP-5 | Inconsistent host reference pattern | **CLOSED** | D2 + §5d (host_ref semantics) |
| GAP-6 | No container image / template abstraction | **PARTIAL** | D2 (image ref in Docker class) |
| GAP-7 | Resource profile not structured | **DEFERRED** | Out of Scope (future ADR) |
| GAP-8 | No multi-host orchestration | **DEFERRED** | Out of Scope (home lab single-host) |
| GAP-9 | No multi-hypervisor VM taxonomy | **CLOSED** | D1 (hypervisor hierarchy) |
| GAP-10 | L3 storage ↔ VM disk disconnect | **CLOSED** | D4 (L3↔L4 storage integration) |
| GAP-11 | L4 ↔ L3 data_asset mapping not implemented | **CLOSED** | D4 (data_asset_ref) |

**Summary:** 9/11 gaps closed, 2 explicitly deferred.

---

## 1. AS-IS: Current Container Modeling

### 1.1 Current Stack

```
L5: svc-*         (service)  →  runtime.target_ref  →  L4 or L1
L4: lxc-*         (workload) →  host_ref            →  L1
L1: srv-gamayun   (device)   →  firmware_ref, os_refs
```

### 1.2 Current Classes

| Class | Layer | Purpose | firmware_policy | os_policy |
|-------|-------|---------|-----------------|-----------|
| `class.compute.hypervisor` | L1 | Proxmox VE host | required | required |
| `class.compute.edge_node` | L1 | Orange Pi / SBC | required | required |
| `class.compute.cloud_vm` | L1 | Hetzner/Oracle VPS | required | required |
| `class.compute.workload.container` | L4 | LXC container | **forbidden** | required |
| `class.router` | L1 | MikroTik/GL.iNet | required | required |

### 1.3 Current Object Patterns

**LXC containers** (`obj.proxmox.lxc.debian12.*`):
- 10 objects, all same class `class.compute.workload.container`
- `software_contract.os_obj_refs` → `obj.os.debian.12.proxmox.lxc`
- capabilities: `cap.compute.workload.container`, `cap.compute.workload.linux_base`
- vendor: `vendor.proxmox.runtime.lxc`

**Docker on LXC** (`obj.proxmox.lxc.debian12.docker`):
- Same class as regular LXC
- Extra vendor capability: `vendor.runtime.docker.host`

### 1.4 Current Instance Patterns

```yaml
# L4 LXC instance pattern
instance: lxc-postgresql
object_ref: obj.proxmox.lxc.debian12.postgresql
host_ref: srv-gamayun           # → L1 physical host
os_refs: [inst.os.debian.12.proxmox.lxc]
storage:
  rootfs: { pool_ref: inst.storage.pool.local_lvm }
  volumes: [...]                # mount points with pool_ref
network:
  bridge_ref: inst.bridge.vmbr0
  vlan_ref: inst.vlan.servers
  ip: 10.0.30.10/24
```

```yaml
# L5 service on LXC
instance: svc-postgresql
runtime:
  type: lxc
  target_ref: lxc-postgresql    # → L4
  network_binding_ref: inst.vlan.servers
```

```yaml
# L5 service on Docker (skips L4)
instance: svc-grafana@docker.srv-orangepi5
runtime:
  type: docker
  target_ref: srv-orangepi5     # → L1 directly!
```

### 1.5 Layer Contract (runtime_target_rules)

```
L5 services → target L1 devices or L4 workloads
L4 workloads → bind to L3 storage, L2 network
L6 observability → monitor L1/L4/L5
L7 operations → target L1/L4/L5/L6
```

---

## 2. IDENTIFIED GAPS

### GAP-1: No Unified Container Taxonomy

**Problem**: All containers use ONE class `class.compute.workload.container`.
LXC, Docker, VM (QEMU/KVM) — fundamentally different isolation/resource models —
are flattened into one class. The `vms/` directory exists but is empty.

**Impact**: Cannot enforce VM-specific invariants (firmware required, disk images vs
rootfs), cannot model Docker containers at L4, cannot distinguish privileged vs
unprivileged LXC.

**Containers differ by:**

| Property | LXC | Docker | VM (QEMU/KVM) |
|----------|-----|--------|---------------|
| Isolation | namespace + cgroup | namespace + cgroup | full hardware virtualization |
| Kernel | shared with host | shared with host | own kernel |
| Firmware | none | none | virtual (SeaBIOS/OVMF) |
| OS | full OS (systemd) | minimal (often no init) | full OS |
| Disk model | rootfs (directory/LVM) | layers/overlay | disk image (qcow2/raw) |
| Network | veth pair to bridge | docker bridge / macvlan | virtio NIC to bridge |
| Lifecycle | long-lived, mutable | ephemeral, immutable | long-lived, mutable |
| Boot | init process | entrypoint/cmd | BIOS/UEFI → bootloader → kernel |

### GAP-2: Docker Containers Have No L4 Representation

**Problem**: Docker services on `srv-orangepi5` and `rtr-mikrotik-chateau` point
directly to L1 devices (`runtime.type: docker, target_ref: srv-orangepi5`).
The Docker container itself (with its image, volumes, network) has NO L4 entity.

**Impact**:
- Cannot model Docker container resources (CPU/memory limits, volumes, ports)
- Cannot track Docker container state independently from host
- No unified inventory of all containers across all hosts
- L6 healthchecks/L7 backups cannot target Docker containers specifically

### GAP-3: No Nested Topology / Recursive Composition

**Problem**: A container IS a virtual computer with its own:
- Network interfaces (veth, docker0, macvlan)
- Storage volumes (bind mounts, named volumes, overlayfs layers)
- DNS, hostname, IP address
- OS-level resources (users, packages, systemd units)

The current model treats containers as flat entities with `network:` and `storage:`
inline blocks. But as topology grows, each container needs its own mini-topology.

**Impact**: No way to model:
- Container-internal networks (Docker Compose networks, inter-container communication)
- Volume sharing between containers (e.g., shared nginx configs)
- Nested container runtimes (Docker-in-LXC, Kubernetes pods)
- Container-to-container connectivity without L2 VLAN participation

### GAP-4: No Container Runtime as First-Class Entity

**Problem**: The container runtime (Proxmox LXC runtime, Docker Engine, containerd,
Kubernetes kubelet) is implicit. It's encoded as:
- vendor capabilities (`vendor.proxmox.runtime.lxc`, `vendor.runtime.docker.host`)
- runtime type in L5 services (`runtime.type: lxc | docker | baremetal`)

But the runtime itself — its version, configuration, socket path, capabilities —
is not a modeled entity.

**Impact**: Cannot:
- Track Docker Engine version across hosts
- Model runtime-specific constraints (Docker requires cgroupv2, LXC needs kernel features)
- Generate runtime-specific configuration (daemon.json for Docker, pct.conf for LXC)

### GAP-5: Inconsistent Host Reference Pattern

**Problem**: Three different patterns coexist:

| Pattern | Where | Semantics |
|---------|-------|-----------|
| `host_ref: srv-gamayun` | L4 LXC instances | Container runs on this host |
| `runtime.target_ref: lxc-docker` | L5 services | Service runs in this container |
| `runtime.target_ref: srv-orangepi5` | L5 Docker services | Service runs on host (no L4!) |

Docker services skip L4 entirely, creating an asymmetry. Some services point to L4
(LXC), others to L1 (Docker hosts).

### GAP-6: No Container Image / Template Abstraction

**Problem**: LXC templates and Docker images are not modeled entities. The OS object
(`obj.os.debian.12.proxmox.lxc`) fills this role for LXC but there's no equivalent
for Docker images (`grafana/grafana:latest`, `prom/prometheus:v2.50`).

**Impact**: Cannot track image versions, registry sources, vulnerability status,
update policies.

### GAP-7: Resource Profile is Reference, Not Structured

**Problem**: `resource_profile_ref: rp.lxc.balanced` exists but resource profiles
are referenced by name. There's no class/object/instance hierarchy for resource
profiles with CPU, memory, I/O constraints.

### GAP-8: No Multi-Host Container Orchestration Model

**Problem**: All LXC containers run on single host `srv-gamayun`. No model for:
- Container migration between hosts
- Placement constraints/affinity
- Multi-host networking (VXLAN, WireGuard mesh between container networks)

Lower priority for a home lab but important for ontology completeness.

### GAP-9: No Multi-Hypervisor VM Taxonomy

**Problem**: The current model only accounts for Proxmox QEMU/KVM VMs. Real-world
infrastructure uses diverse hypervisors with fundamentally different:
- Disk image formats (qcow2, vmdk, vdi, vhdx, raw)
- Virtual hardware models (Q35, i440fx, PIIX4, Generation 1/2)
- Network virtualization (virtio, e1000, vmxnet3, Hyper-V synthetic)
- Management APIs (Proxmox REST, VirtualBox COM/SOAP, Hyper-V WMI/PowerShell, vSphere API)
- Firmware models (SeaBIOS, OVMF, Hyper-V Gen2 UEFI)

**Hypervisor platforms to model:**

| Platform | VM Type | Disk Formats | Firmware | Network |
|----------|---------|-------------|----------|---------|
| **Proxmox QEMU/KVM** | Full virt (KVM accel) | qcow2, raw, vmdk | SeaBIOS, OVMF | virtio, e1000 |
| **Oracle VirtualBox** | Full virt (VT-x) | vdi, vmdk, vhd | VirtualBox EFI, legacy BIOS | virtio, e1000, PCnet |
| **Microsoft Hyper-V** | Full virt (Gen1/Gen2) | vhd, vhdx | Gen1 BIOS, Gen2 UEFI | synthetic, legacy |
| **VMware ESXi/Workstation** | Full virt (VT-x) | vmdk | legacy BIOS, EFI | vmxnet3, e1000e |
| **Xen / XCP-ng** | Para/Full virt (PV/HVM) | qcow2, vhd, raw | SeaBIOS, OVMF | xen-netfront, e1000 |
| **Cloud (AWS/GCP/Azure)** | Provider-managed | provider-specific | provider UEFI | provider VPC NIC |

**Impact**: Cannot model dev workstations (VirtualBox), enterprise migration paths
(VMware→Proxmox), or multi-platform VM portability without hypervisor-specific classes.

### GAP-10: L3 Storage ↔ VM Disk Image Disconnect

**Problem**: The L3 storage model (pool → volume → data_asset) was designed primarily
for LXC container rootfs and mount points. VMs have a fundamentally different storage
model:

**LXC storage pattern (current):**
```
L3 pool (local_lvm) → L4 container rootfs (subvol/raw in pool)
L3 pool (local_lvm) → L4 container volume (mount point)
```

**VM storage pattern (needed):**
```
L3 pool → L3 volume (disk image: qcow2/vmdk/vdi) → L4 VM disk (scsi0/ide0/virtio0)
L3 pool → L3 volume (ISO image) → L4 VM CD-ROM (ide2)
L3 pool → L3 volume (cloud-init drive) → L4 VM cloud-init
L3 pool → L3 volume (EFI vars) → L4 VM efidisk0
```

**Key differences:**

| Property | LXC Volumes | VM Disks |
|----------|-------------|----------|
| Format | raw/subvol (pool-native) | qcow2/vmdk/vdi/vhdx/raw |
| Attachment | mount_point (Linux path) | bus:slot (scsi0, virtio0, ide2) |
| Boot role | rootfs (always first) | boot order configurable |
| Snapshots | pool-level | image-level (qcow2 backing chain) |
| Live resize | pool-dependent | format-dependent + guest agent |
| ISO attach | N/A | CD-ROM drive (ide2) |
| EFI vars | N/A | efidisk0 (OVMF only) |
| Cloud-init | N/A | separate drive (ide2/scsi1) |

**Impact**:
- `class.storage.volume` needs `format` + `bus_attachment` + `boot_role` properties
- L4 VMs need multi-disk model (boot, data, ISO, EFI, cloud-init)
- Volume → pool relationship needs format compatibility validation
  (e.g., LVM thin pools support raw only, directory pools support qcow2)

### GAP-11: L4 ↔ L3 Data Asset Mapping Not Implemented

**Problem**: ADR 0026 Phase 4 defined `data_asset_ref` on L4 volumes to link
governance (criticality, backup policy) from L3 data_assets to L4 placement.
This is NOT yet implemented in any instance file.

Current state:
```yaml
# L4 instance — only pool_ref, no data_asset_ref
storage:
  rootfs:
    pool_ref: inst.storage.pool.local_lvm
    size_gb: 8
  volumes:
    - mount_path: /var/lib/postgresql/data
      pool_ref: inst.storage.pool.local_lvm
      size_gb: 20
      # data_asset_ref: inst.data_asset.postgresql_db  ← MISSING
```

**Impact**: L3 data_assets and L4 volumes exist as disconnected entities.
No compile-time validation that critical data is on appropriate storage.
Backup policies in L3 cannot be automatically enforced on L4 volumes.

---

## 3. INDUSTRY REFERENCE MODELS

### 3.1 TOSCA (OASIS Standard v2.0, Sep 2025)

TOSCA defines topology as **nodes** + **relationships** + **capabilities** + **requirements**.

Key concepts applicable here:
- **Node Types** with inheritance: `tosca.nodes.Compute` → `tosca.nodes.Container.Runtime` → `tosca.nodes.Container.Application`
- **Capabilities**: `host`, `network`, `storage` — match our capability model
- **Requirements**: `host` requirement on Container links to Compute node — analogous to `host_ref`
- **Substitution mappings**: A service template can substitute a single node — **directly models nested topology**

### 3.2 DMTF CIM (Common Information Model)

- `CIM_ComputerSystem` → `CIM_VirtualComputerSystem` → container
- Explicit **HostedDependency** association between virtual and physical
- `CIM_ResourcePool` → `CIM_ResourceAllocationSettingData`

### 3.3 Kubernetes Resource Model

- **Pod** = smallest deployable unit (1+ containers sharing network namespace)
- **Node** = physical/virtual host
- **Container** = OCI runtime inside Pod
- Nested: Pod.spec.containers[], Pod.spec.volumes[], Pod.spec.networks[]

### 3.4 OpenStack / Proxmox Model

Proxmox itself models:
- **Node** → **VM** (QEMU) or **CT** (LXC)
- VM has: disk images, network interfaces, BIOS/UEFI, assigned resources
- CT has: rootfs, mount points, network interfaces, features (nesting, keyctl)

---

## 4. RISK SUMMARY

| Risk | Severity | Mitigation |
|------|----------|-----------|
| Topology explosion (100+ files per container type) | HIGH | Inheritance via class→object→instance + defaults merging |
| Breaking existing L4/L5 contracts | HIGH | Backward-compatible evolution, not replacement |
| Over-engineering for home lab scale | MEDIUM | MVP-first: model what we deploy today, extensibility for tomorrow |
| Nested topology complexity | MEDIUM | Bounded nesting: max 2 levels (host→container→container) |
| Plugin/validator impact | MEDIUM | New validators for new classes, existing ones stay |
| Multi-hypervisor class sprawl | MEDIUM | Shared abstract base; hypervisor-specific only where format/bus differ |
| L3 volume format incompatibility | HIGH | Compile-time validation: volume format must match pool type capabilities |
| VM disk model complexity (multi-disk, boot order) | MEDIUM | Ordered disk list with explicit bus_attachment + role enum |
| data_asset_ref backfill effort | LOW | Incremental: add refs as L4 instances are touched |
