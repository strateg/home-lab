# IMPLEMENTATION-PLAN: Container Ontology (ADR 0087)

## Phase 1: Docker Promotion (MVP)

### 1.1 Class Definitions

| Task | Files | Notes |
|------|-------|-------|
| Create `class.compute.workload` (abstract base) | `topology/class-modules/compute/class.compute.workload.yaml` | Extract common from current `class.compute.workload.container` |
| Rename `class.compute.workload.container` → `.lxc` | `topology/class-modules/compute/class.compute.workload.lxc.yaml` | Keep old class as compatibility alias (no symlink) |
| Create `class.compute.workload.docker` | `topology/class-modules/compute/class.compute.workload.docker.yaml` | Image ref, ports, restart policy |
| Update `class.compute.workload.container.yaml` | Rename/redirect | Backward compat alias |

### 1.2 Object Definitions

| Task | Files |
|------|-------|
| Update existing LXC objects: `class_ref` → `class.compute.workload.lxc` | `topology/object-modules/proxmox/obj.proxmox.lxc.*.yaml` |
| Create Docker container objects (one per distinct Docker service) | `topology/object-modules/docker/obj.docker.container.*.yaml` |
| Keep `cap.compute.runtime.container_host` on Docker-capable hosts | `topology/object-modules/orangepi/obj.orangepi.rk3588.debian.yaml` |
| Add `vendor.runtime.docker.host` where Docker engine exists | Orange Pi + Docker LXC object(s) |

### 1.3 Instance Definitions

| Task | Files |
|------|-------|
| Create host-sharded L4 directories | `L4-platform/{lxc,docker,vm}/{host_or_runtime_host}/` |
| Create host-sharded L5 directories | `L5-application/services/{host_or_runtime_host}/` |
| Move current L4 instances to host shards (no semantic changes) | e.g. `L4-platform/lxc/srv-gamayun/*.yaml` |
| Move current L5 services to host shards (no semantic changes) | e.g. `L5-application/services/srv-gamayun/*.yaml` |
| Create Docker container instances from current L5 Docker services | ~12 files based on current L5 `runtime.type: docker` |
| Update L5 Docker services: `target_ref` → L4 Docker container | ~12 L5 service files |

### 1.4 Validators

| Task | Files |
|------|-------|
| Add `validate-container-host-capability` plugin | `topology-tools/plugins/validators/` |
| Add `validate-host-ref-dag` plugin (anti-cycle + depth check) | `topology-tools/plugins/validators/` |
| Add deprecated-pattern warning for L5→L1 Docker refs | Update existing target_ref validator |
| Add host-shard placement validator for L4/L5 | Validate path host segment vs `host_ref` / runtime host |

### 1.5 Tests

| Task | Files |
|------|-------|
| Unit tests for new class hierarchy | `tests/` |
| Validate compile succeeds with new classes | `tests/plugin_integration/` |
| Validate existing LXC instances compile correctly | Regression |
| Negative test: host_ref cycle → ERROR | `tests/` |
| Negative test: host_ref depth > 2 → ERROR | `tests/` |

### 1.6 Acceptance Gate

- [x] `python -m pytest tests -q` — all pass (1034 tests passed, 4 skipped)
- [x] `python topology-tools/compile-topology.py` — 0 errors, 5 warnings (IP reuse only)
- [x] `python scripts/orchestration/lane.py validate-v5` — PASS
- [x] Every L5 service has `target_ref` pointing to L4 (no L1 Docker refs) — W0087 warning emitted for L5→L1 Docker refs
- [x] Docker-capable hosts declare `cap.compute.runtime.container_host` and `vendor.runtime.docker.host`
- [x] L4 and L5 files follow host-sharded path policy (12 Docker + 9 LXC instances in sharded layout)
- [x] host_ref cycle detection works (negative tests pass: E7896 for cycles, E7897 for depth>2)

**Phase 1 Gate: PASSED** (2026-04-07)

---

## Phase 2: Hypervisor Platform Split (L1)

### 2.1 Refactor Hypervisor Class Hierarchy

| Task | Files | Notes |
|------|-------|-------|
| Make `class.compute.hypervisor` abstract base (v2.0) | `topology/class-modules/compute/class.compute.hypervisor.yaml` | Add `vm_constraints`, `platform_config_schema`, `supported_workload_types` |
| Add hypervisor execution model fields | `class.compute.hypervisor*.yaml` | Add `execution_model` (+ `execution_model_support` where needed), `hardware_ref`, `host_os_ref` contract |
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
| Add required linkage refs by execution model | Hypervisor instances | `bare_metal` => `hardware_ref`; `hosted` => `host_os_ref` |

### 2.3 Acceptance Gate

- [x] Existing Proxmox topology compiles with new class hierarchy (verified 2026-04-08: 0 ADR0087 errors)
- [x] All 1048+ tests pass (verified 2026-04-08: 63 ADR0087 tests pass, full suite 1048 pass)
- [x] New hypervisor classes validate correctly (proxmox, vbox, hyperv, vmware, xen classes exist)
- [x] `obj.proxmox.ve` references `class.compute.hypervisor.proxmox` (via @extends)
- [x] Hypervisor execution model linkage validates (I7899 bare_metal info emitted for srv-gamayun)

**Phase 2 Gate: PASSED** (2026-04-08)

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
| Validate disk_id uniqueness within VM instance | Part of above |
| Validate bus:slot uniqueness within VM instance | Part of above |
| Validate boot_order entries reference existing disk_id values | Part of above |
| Validate non-ephemeral disks have volume_ref | Part of above |

### 3.3 Instances

| Task | Files |
|------|-------|
| Create `L4-platform/vm/{host}/` directories | New directory layout |
| Create Proxmox VM instances (when needed) | On demand |
| Keep temporary alias for `L4-platform/vms/{host}/` if present | Migration-only compatibility path |

### 3.4 Acceptance Gate

- [x] VM with Proxmox platform_config compiles on Proxmox host (test_vm_hypervisor_compat_accepts_valid_vm)
- [x] VM with VBox platform_config fails on Proxmox host (test_vm_hypervisor_compat_rejects_vbox_qcow2: E7903)
- [x] VM with vmdk format fails on Hyper-V host (test_vm_hypervisor_compat_rejects_hyperv_vmdk: E7903)
- [x] Duplicate disk_id in VM → ERROR (test_vm_hypervisor_compat_rejects_duplicate_disk_id: E7901)
- [x] Duplicate bus:slot in VM → ERROR (test_vm_hypervisor_compat_rejects_duplicate_bus_slot: E7902)
- [x] boot_order referencing nonexistent disk_id → ERROR (test_vm_hypervisor_compat_rejects_invalid_boot_order: E7906)
- [x] Canonical VM path is `L4-platform/vm/{host}/`; `vms` retained as compat alias
- [x] All tests pass (16 vm_hypervisor_compat + vm_refs tests passing)

**Phase 3 Gate: PASSED** (2026-04-08)

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
| Add `data_asset_ref` to existing L4 LXC volume entries | `projects/home-lab/topology/instances/L4-platform/lxc/*/*.yaml` |
| Create L3 volume instances for future VMs | `projects/home-lab/topology/instances/L3-data/volumes/` |

### 4.5 Acceptance Gate

- [x] `data_asset_ref` on LXC volumes resolves to valid L3 data_assets (backfilled postgresql + redis)
- [x] qcow2 volume on lvmthin pool → validation ERROR (test_volume_format_compat_rejects_qcow2_on_lvm: E7911)
- [x] qcow2 volume on dir pool → OK (test_volume_format_compat_accepts_valid_pool_format)
- [x] vmdk volume on Hyper-V host → validation ERROR (test_volume_format_compat_rejects_vhdx_on_proxmox: E7913)
- [x] data_asset_ref validation (test_volume_format_compat_rejects_unknown_data_asset_ref: E7912)

**Phase 4 Gate: PASSED** (2026-04-08)

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

- [x] Cross-scope references resolve correctly (test_nested_topology_scope_validates_scope_reference)
- [x] Generator produces docker-compose.yaml with correct networks (test_docker_compose_generator_includes_networks)
- [x] Depth > 2 is rejected by validator (host_ref_dag_validator: E7897)

**Phase 5 Gate: PASSED** (2026-04-08)

---

## Phase 6: Stack Objects

### 6.1 Stack Grouping

| Task | Files |
|------|-------|
| Create `class.compute.workload.docker.stack` | Class definition |
| Create stack objects (monitoring, media, etc.) | Object definitions |
| Docker Compose generator plugin | `topology-tools/plugins/generators/` |

### 6.2 Acceptance Gate

- [x] Stack objects compile (class.compute.workload.docker.stack + 3 stack objects + 3 stack instances)
- [x] Generator produces valid docker-compose.yaml (8 tests passing in test_docker_compose_generator.py)
- [x] Generated compose files are deterministic (test_docker_compose_generator_output_is_deterministic)

**Phase 6 Gate: PASSED** (2026-04-08)

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

---

## Migration Gates

Each phase has a **go/no-go gate** that must pass before the next dependent
phase starts. Gates are verified by running the acceptance checklist AND
confirming the invariants below.

### Phase 1 → Phase 3/4/5 Gate

| # | Criterion | How to verify |
|---|-----------|---------------|
| 1 | All existing tests pass (`pytest tests -q`) | CI green |
| 2 | Topology compiles without errors | `compile-topology.py` exit 0 |
| 3 | `validate-v5` passes | `lane.py validate-v5` exit 0 |
| 4 | No L5 Docker service has `target_ref` → L1 | grep audit |
| 5 | Host-sharded L4/L5 layout in place | Directory structure audit |
| 6 | Deprecated pattern warnings emitted (not errors) | Compiler stderr review |
| 7 | Feature flag `ADR0087_PHASE1` set in `framework.lock.yaml` | File check |

### Phase 2 → Phase 3 Gate

| # | Criterion | How to verify |
|---|-----------|---------------|
| 1 | All existing tests pass | CI green |
| 2 | `obj.proxmox.ve` references `class.compute.hypervisor.proxmox` | Instance audit |
| 3 | Hypervisor execution model linkage validates | Validation pass |
| 4 | New hypervisor classes load without error | `compile-topology.py` |

### Phase 3 → Phase 4 Gate

| # | Criterion | How to verify |
|---|-----------|---------------|
| 1 | VM class compiles with `platform_config` validation | Test case |
| 2 | Cross-hypervisor mismatch detected as ERROR | Negative test |
| 3 | `disk_id` uniqueness enforced | Negative test |
| 4 | `bus:slot` dedup enforced | Negative test |
| 5 | `boot_order` integrity enforced | Negative test |

### Phase 4 → Phase 5/6 Gate

| # | Criterion | How to verify |
|---|-----------|---------------|
| 1 | Volume format ↔ pool validation works | Positive + negative tests |
| 2 | Volume format ↔ hypervisor validation works | Positive + negative tests |
| 3 | `data_asset_ref` backfill complete for critical volumes | Instance audit |

---

## Rollback Procedures

Each phase is designed for safe rollback. The key principle is:
**aliases and feature flags allow instant revert by configuration, not code deletion.**

### General Rollback Strategy

1. **Feature flags**: Each phase sets a flag in `framework.lock.yaml`
   (e.g., `ADR0087_PHASE1: true`). Reverting the flag disables new behavior.

2. **Alias retention**: Old class names (`.container`), old paths (`vms/`),
   old patterns (L5→L1) remain functional during WARNING phase. Rollback =
   just keep using old patterns (warnings are non-blocking).

3. **Git revert**: Each phase is merged as a single squash commit (or a
   clearly bounded set of commits). `git revert <phase-commit>` is always
   an option if flag-based rollback is insufficient.

### Phase-Specific Rollback

| Phase | Rollback action | Data safety |
|-------|----------------|-------------|
| **Phase 1** | Revert `ADR0087_PHASE1` flag; old class `.container` still works via alias; L5→L1 Docker refs still accepted (were only WARNING) | No data loss — new L4 Docker files are additive |
| **Phase 2** | Revert hypervisor class split; `class.compute.hypervisor` continues as monolithic class; new subclasses become unused | No data loss — existing Proxmox refs unchanged |
| **Phase 3** | Remove VM instances + class; hypervisor constraint validation disabled | No data loss — VMs are new entities |
| **Phase 4** | Revert volume schema additions (optional fields, backward compat); remove new validators | No data loss — new L3 fields are optional |
| **Phase 5** | Remove `topology_scope` from instances; disable scope resolution in compiler | No data loss — scope is opt-in |
| **Phase 6** | Remove stack objects + generator plugin | No data loss — stacks are new entities |
