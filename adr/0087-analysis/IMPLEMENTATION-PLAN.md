# IMPLEMENTATION-PLAN: Container Ontology (ADR 0087)

## Phase 1: Docker Promotion (MVP)

### 1.1 Class Definitions

| Task | Files | Notes |
|------|-------|-------|
| Create `class.compute.workload` (abstract base) | `topology/class-modules/compute/class.compute.workload.yaml` | Extract common from current `class.compute.workload.container` |
| Rename `class.compute.workload.container` → `.lxc` | `topology/class-modules/compute/class.compute.workload.lxc.yaml` | Keep old filename as symlink (transition) |
| Create `class.compute.workload.docker` | `topology/class-modules/compute/class.compute.workload.docker.yaml` | Image ref, ports, restart policy |
| Update `class.compute.workload.container.yaml` | Rename/redirect | Backward compat alias |

### 1.2 Object Definitions

| Task | Files |
|------|-------|
| Update existing LXC objects: `class_ref` → `class.compute.workload.lxc` | `topology/object-modules/proxmox/obj.proxmox.lxc.*.yaml` |
| Create Docker container objects (one per distinct Docker service) | `topology/object-modules/docker/obj.docker.container.*.yaml` |
| Add `cap.runtime.docker` to `obj.device.orangepi5` | `topology/object-modules/devices/obj.device.orangepi5.yaml` |
| Add `cap.runtime.docker` to `obj.proxmox.lxc.debian12.docker` | Already has `vendor.runtime.docker.host` — formalize |

### 1.3 Instance Definitions

| Task | Files |
|------|-------|
| Create `L4-platform/docker/` directory | New directory |
| Create Docker container instances from current L5 Docker services | ~12 files based on current L5 `runtime.type: docker` |
| Update L5 Docker services: `target_ref` → L4 Docker container | ~12 L5 service files |

### 1.4 Validators

| Task | Files |
|------|-------|
| Add `validate-container-host-capability` plugin | `topology-tools/plugins/validators/` |
| Add deprecated-pattern warning for L5→L1 Docker refs | Update existing target_ref validator |

### 1.5 Tests

| Task | Files |
|------|-------|
| Unit tests for new class hierarchy | `tests/` |
| Validate compile succeeds with new classes | `tests/plugin_integration/` |
| Validate existing LXC instances compile correctly | Regression |

### 1.6 Acceptance Gate

- [ ] `python -m pytest tests -q` — all pass
- [ ] `python topology-tools/compile-topology.py` — no errors
- [ ] `python scripts/orchestration/lane.py validate-v5` — pass
- [ ] Every L5 service has `target_ref` pointing to L4 (no L1 Docker refs)
- [ ] Docker hosts declare `cap.runtime.docker`

---

## Phase 2: Hypervisor Platform Split (L1)

### 2.1 Refactor Hypervisor Class Hierarchy

| Task | Files | Notes |
|------|-------|-------|
| Make `class.compute.hypervisor` abstract base (v2.0) | `topology/class-modules/compute/class.compute.hypervisor.yaml` | Add `vm_constraints`, `platform_config_schema`, `supported_workload_types` |
| Create `class.compute.hypervisor.proxmox` | `topology/class-modules/compute/class.compute.hypervisor.proxmox.yaml` | qcow2/raw/vmdk, scsi/virtio/ide/sata, seabios/ovmf |
| Create `class.compute.hypervisor.vbox` | `topology/class-modules/compute/class.compute.hypervisor.vbox.yaml` | vdi/vmdk/vhd/raw, sata/ide/scsi/nvme |
| Create `class.compute.hypervisor.hyperv` | `topology/class-modules/compute/class.compute.hypervisor.hyperv.yaml` | vhd/vhdx, ide/scsi, Gen1/Gen2 |
| Create `class.compute.hypervisor.vmware` | `topology/class-modules/compute/class.compute.hypervisor.vmware.yaml` | vmdk only, pvscsi/lsilogic, hw_version |
| Create `class.compute.hypervisor.xen` | `topology/class-modules/compute/class.compute.hypervisor.xen.yaml` | qcow2/vhd/raw, xvd/ide/scsi, PV/HVM/PVH |

### 2.2 Update Existing Objects and Instances

| Task | Files |
|------|-------|
| Update `obj.proxmox.ve`: `class_ref` → `class.compute.hypervisor.proxmox` | `topology/object-modules/proxmox/obj.proxmox.ve.yaml` |
| Update `srv-gamayun` instance if needed | `projects/home-lab/topology/instances/L1-foundation/devices/srv-gamayun.yaml` |
| Add hypervisor objects for other platforms (when hosts exist) | `topology/object-modules/<platform>/` |

### 2.3 Acceptance Gate

- [ ] Existing Proxmox topology compiles with new class hierarchy
- [ ] All 871+ tests pass
- [ ] New hypervisor classes validate correctly
- [ ] `obj.proxmox.ve` references `class.compute.hypervisor.proxmox`

---

## Phase 3: Multi-Hypervisor VM Support (L4)

### 3.1 VM Class and Objects

| Task | Files | Notes |
|------|-------|-------|
| Create `class.compute.workload.vm` | `topology/class-modules/compute/class.compute.workload.vm.yaml` | Single class: disks[], boot_order, cloud_init, platform_config |
| Create Proxmox VM objects | `topology/object-modules/proxmox/obj.proxmox.vm.*.yaml` | `platform_config: {machine_type, scsi_controller, ...}` |
| Create VirtualBox VM objects | `topology/object-modules/vbox/obj.vbox.vm.*.yaml` | `platform_config: {chipset, paravirt_provider, ...}` |
| Create Hyper-V VM objects | `topology/object-modules/hyperv/obj.hyperv.vm.*.yaml` | `platform_config: {generation, secure_boot, ...}` |
| Create VMware VM objects | `topology/object-modules/vmware/obj.vmware.vm.*.yaml` | `platform_config: {hw_version, guest_os_id, ...}` |
| Create Xen VM objects | `topology/object-modules/xen/obj.xen.vm.*.yaml` | `platform_config: {virt_mode, viridian, ...}` |

### 3.2 Cross-Layer Validators

| Task | Files |
|------|-------|
| Add `validate-vm-hypervisor-compat` plugin | `topology-tools/plugins/validators/` |
| Validate disk.format ∈ hypervisor.allowed_disk_formats | Part of above |
| Validate disk.bus ∈ hypervisor.allowed_disk_buses | Part of above |
| Validate platform_config against hypervisor.platform_config_schema | Part of above |
| Validate boot disk presence (exactly 1 disk with role: boot) | Part of above |

### 3.3 Instances

| Task | Files |
|------|-------|
| Create `L4-platform/vm/` directory | New directory |
| Create Proxmox VM instances (when needed) | On demand |

### 3.4 Acceptance Gate

- [ ] VM with Proxmox platform_config compiles on Proxmox host
- [ ] VM with VBox platform_config fails on Proxmox host (expected error)
- [ ] VM with vmdk format fails on Hyper-V host (expected error)
- [ ] All tests pass

---

## Phase 4: L3 Storage Integration

### 4.1 Extend L3 Volume Class

| Task | Files |
|------|-------|
| Add `format` enum to `class.storage.volume` | `topology/class-modules/storage/class.storage.volume.yaml` |
| Add `bus_attachment` property | Same file |
| Add `role` enum (rootfs, boot, data, cdrom, efivars, cloudinit, swap) | Same file |
| Add `data_asset_ref` reference | Same file |
| Add `snapshot_capable` boolean | Same file |

### 4.2 New L3 Objects

| Task | Files |
|------|-------|
| Create `obj.storage.volume.vm_disk` (generic VM disk template) | `topology/object-modules/storage/obj.storage.volume.vm_disk.yaml` |
| Create format-specific variants if needed | e.g., `obj.storage.volume.vm_disk.qcow2` |

### 4.3 Cross-Layer Validation

| Task | Files |
|------|-------|
| Add `validate-volume-pool-format-compat` | `topology-tools/plugins/validators/` |
| Add `validate-volume-hypervisor-format-compat` | Same or separate plugin |
| Add `validate-data-asset-criticality-pool` | Enforce critical data on reliable pools |

### 4.4 Backfill Existing Instances

| Task | Files |
|------|-------|
| Add `data_asset_ref` to existing L4 LXC volume entries | `projects/home-lab/topology/instances/L4-platform/lxc/*.yaml` |
| Create L3 volume instances for future VMs | `projects/home-lab/topology/instances/L3-data/volumes/` |

### 4.5 Acceptance Gate

- [ ] `data_asset_ref` on LXC volumes resolves to valid L3 data_assets
- [ ] qcow2 volume on lvmthin pool → validation ERROR (format incompatible)
- [ ] qcow2 volume on dir pool → OK
- [ ] vmdk volume on Hyper-V host → validation ERROR
- [ ] Critical data_asset on unreliable pool → WARNING

---

## Phase 5: Nested Topology

### 5.1 Scope Mechanism

| Task | Files |
|------|-------|
| Define `topology_scope` schema in class base | `class.compute.workload.yaml` |
| Implement scope resolution in compiler | `topology-tools/kernel/` |
| Add `internal_networks` property to LXC/Docker classes | Class definitions |

### 5.2 Docker-in-LXC

| Task | Files |
|------|-------|
| `lxc-docker` declares scope with Docker networks | L4 instance update |
| Docker containers reference scope networks | L4 Docker instances |

### 5.3 Acceptance Gate

- [ ] Cross-scope references resolve correctly
- [ ] Generator produces docker-compose.yaml with correct networks
- [ ] Depth > 2 is rejected by validator

---

## Phase 6: Stack Objects

### 6.1 Stack Grouping

| Task | Files |
|------|-------|
| Create `class.compute.workload.docker.stack` | Class definition |
| Create stack objects (monitoring, media, etc.) | Object definitions |
| Docker Compose generator plugin | `topology-tools/plugins/generators/` |

### 6.2 Acceptance Gate

- [ ] Stack objects compile
- [ ] Generator produces valid docker-compose.yaml
- [ ] `docker compose config` validates generated files

---

## Dependency Graph

```
Phase 1 (Docker MVP)          Phase 2 (Hypervisor Split)
    │                              │
    │                              ▼
    │                     Phase 3 (VM Support)
    │                              │
    ├──────────────┬───────────────┤
    │              │               │
    ▼              ▼               ▼
Phase 5       Phase 4          (complete)
(Nested)   (L3 Storage)
    │
    ▼
Phase 6
(Stacks)
```

Phase 1 and Phase 2 can run in **parallel** (independent axes).
Phase 3 requires Phase 2 (hypervisor classes needed for VM validation).
Phase 4 requires Phase 1 + Phase 3 (volumes need both workload types and hypervisor constraints).
Phase 5 requires Phase 1 only.
Phase 6 requires Phase 5.
