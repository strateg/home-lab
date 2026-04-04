# ONTOLOGY-PROPOSAL: Unified Container Taxonomy for L4/L5 + L3 Storage Integration

## Executive Summary

This document proposes a container ontology that:
1. Introduces a **3-tier compute class hierarchy** (runtime → container type → workload profile)
2. Models Docker containers as **first-class L4 entities** (closing GAP-2)
3. Adds **nested topology references** for container-internal resources (GAP-3)
4. Supports **multi-hypervisor VM platforms** (Proxmox, VirtualBox, Hyper-V, VMware, Xen) (GAP-9)
5. Defines **L3↔L4 storage integration** with disk image format model (GAP-10, GAP-11)
6. Preserves backward compatibility with existing L4/L5 contracts
7. Includes a **worked end-to-end example** of nginx on MikroTik containerD (§8A)
8. Includes a **worked end-to-end example** of nginx on Proxmox — LXC native vs Docker-in-LXC (§8B)

---

## 1. PROPOSED CLASS HIERARCHY

### 1.1 Current vs Proposed

```
CURRENT (flat):
  class.compute.workload.container  ← LXC only, all types share one class

PROPOSED (two-axis hierarchy — hypervisor at L1, workload at L4):

  L1 Hypervisor Platform (WHERE workloads run):
  class.compute.hypervisor                    ← abstract base (current, now becomes parent)
  ├── class.compute.hypervisor.proxmox        ← Proxmox VE (QEMU/KVM + LXC)
  ├── class.compute.hypervisor.vbox           ← Oracle VirtualBox
  ├── class.compute.hypervisor.hyperv         ← Microsoft Hyper-V
  ├── class.compute.hypervisor.vmware         ← VMware ESXi / Workstation / Fusion
  ├── class.compute.hypervisor.xen            ← Xen / XCP-ng
  └── (class.compute.cloud_vm stays separate — cloud manages hypervisor)

  L4 Workload Type (WHAT runs on the hypervisor):
  class.compute.workload                      ← abstract base (never instantiated)
  ├── class.compute.workload.lxc              ← LXC container (shared kernel)
  ├── class.compute.workload.vm               ← VM (full virtualization, single class)
  ├── class.compute.workload.docker           ← Docker/OCI container
  └── class.compute.workload.pod              ← future: K8s pod

  KEY INSIGHT: The VM class is ONE class. Hypervisor-specific
  properties (machine_type, generation, chipset) live at the
  OBJECT layer (obj.proxmox.vm.*, obj.vbox.vm.*, obj.hyperv.vm.*).
  The hypervisor HOST (L1) declares constraints (allowed formats,
  buses, firmware). Compile-time validation bridges L1↔L4.
```

### 1.2 Class Definitions

#### class.compute.workload (abstract base)

```yaml
class: class.compute.workload
description: >
  Abstract base for any compute workload that runs ON a host (L1 device).
  Not instantiated directly — use type-specific subclasses.
layer: L4
abstract: true

properties:
  host_ref:
    type: reference
    target_layer: L1
    required: true
    description: Physical/virtual host that runs this workload

  resource_profile:
    type: object
    properties:
      cpu_cores: { type: integer, min: 1 }
      memory_mb: { type: integer, min: 64 }
      swap_mb: { type: integer, default: 0 }
      cpu_units: { type: integer, default: 1024 }
    description: Compute resources allocated to this workload

  network:
    type: object
    properties:
      interfaces:
        type: list
        items:
          type: object
          properties:
            name: { type: string }
            bridge_ref: { type: reference, target_layer: L2 }
            vlan_ref: { type: reference, target_layer: L2 }
            ip: { type: string, format: cidr }
            gateway: { type: string, format: ipv4 }
            mac: { type: string, format: mac, required: false }
            firewall: { type: boolean, default: true }

  storage:
    type: object
    properties:
      root:
        type: object
        properties:
          pool_ref: { type: reference, target_layer: L3 }
          size_gb: { type: number }
      volumes:
        type: list
        items:
          type: object
          properties:
            name: { type: string }
            pool_ref: { type: reference, target_layer: L3 }
            mount_point: { type: string }
            size_gb: { type: number }
            readonly: { type: boolean, default: false }

capabilities:
  - cap.compute.workload.base

lifecycle:
  states: [defined, provisioned, running, stopped, destroyed]
```

#### class.compute.workload.lxc

```yaml
class: class.compute.workload.lxc
inherits: class.compute.workload
description: LXC/Proxmox CT — OS-level virtualization with shared kernel.

firmware_policy: forbidden     # LXC has no firmware
os_policy: required            # full OS with init system

properties:
  unprivileged: { type: boolean, default: true }
  features:
    type: object
    properties:
      nesting: { type: boolean, default: false }
      keyctl: { type: boolean, default: false }
      fuse: { type: boolean, default: false }
  start_on_boot: { type: boolean, default: true }
  template_ref:
    type: reference
    description: OS template object (e.g., obj.os.debian.12.proxmox.lxc)

capabilities:
  - cap.compute.workload.container    # backward compat
  - cap.compute.workload.lxc
  - cap.compute.workload.linux_base

vendor_capabilities:
  - vendor.proxmox.runtime.lxc
```

#### class.compute.workload.vm (single VM class — hypervisor-agnostic)

```yaml
class: class.compute.workload.vm
inherits: class.compute.workload
description: >
  Virtual machine workload — full hardware virtualization with own kernel,
  virtual firmware, and disk images. Runs on a hypervisor host (L1).
  Hypervisor-specific properties (machine_type, generation, chipset)
  are defined at the OBJECT layer, not the class layer. Compile-time
  validation enforces compatibility between VM objects and their host's
  hypervisor class.

firmware_policy: required      # All VMs have virtual firmware
os_policy: required            # All VMs boot a full OS

properties:
  cpu_type: { type: string, default: "host" }
  cpu_sockets: { type: integer, default: 1 }
  numa: { type: boolean, default: false }
  agent:
    type: object
    description: Guest agent (QEMU GA, VBox GA, Hyper-V IC, VMware Tools)
    properties:
      enabled: { type: boolean, default: true }
      type:
        type: enum
        values: [qemu, virtualbox, hyperv_ic, vmware_tools, xe_guest, none]

  boot_order:
    type: list
    items: { type: string }
    description: Ordered list of boot devices (hypervisor-specific syntax)

  disks:
    type: list
    description: Virtual disk attachments. Each references an L3 volume.
    items:
      type: object
      properties:
        role:
          type: enum
          values: [boot, data, cdrom, efivars, cloudinit, swap, scratch]
        volume_ref:
          type: reference
          target_layer: L3
          target_class: class.storage.volume
        bus:
          type: enum
          values: [scsi, virtio, ide, sata, nvme, xvd]
          description: Virtual bus (validated against hypervisor.allowed_disk_buses)
        slot: { type: string, description: "Bus slot ID (e.g., scsi0, sata1)" }
        cache:
          type: enum
          values: [none, writeback, writethrough, directsync, unsafe]
          default: none
        bootable: { type: boolean, default: false }

  cloud_init:
    type: object
    required: false
    properties:
      enabled: { type: boolean }
      user_data_ref: { type: reference }
      network_config_ref: { type: reference }

  # Hypervisor-specific extension point (validated by host's hypervisor class)
  platform_config:
    type: object
    description: >
      Opaque bag for hypervisor-specific properties. Contents are validated
      against the host's hypervisor class at compile time. Typically set
      at the object layer, not the instance layer.
    # Examples of what goes here (per hypervisor):
    # Proxmox:  { machine_type: q35, scsi_controller: virtio-scsi-single, os_type: l26 }
    # VBox:     { chipset: ich9, paravirt_provider: kvm, graphics: vmsvga }
    # Hyper-V:  { generation: 2, secure_boot: false, checkpoint_type: production }
    # VMware:   { hw_version: 21, guest_os_id: debian12_64Guest, scsi: pvscsi }
    # Xen:      { virt_mode: hvm, viridian: false }

capabilities:
  - cap.compute.workload.vm
  - cap.compute.workload.linux_base

lifecycle:
  states: [defined, provisioned, running, paused, stopped, destroyed]
```

---

## 1A. HYPERVISOR CLASS HIERARCHY (L1 — NEW)

The current single `class.compute.hypervisor` becomes an abstract base with
platform-specific subclasses. Each subclass declares what workload types,
disk formats, bus types, and firmware it supports.

### class.compute.hypervisor (abstract base — refactored from current)

```yaml
class: class.compute.hypervisor
version: 2.0.0
abstract: true
description: >
  Abstract hypervisor host platform. Subclasses define platform-specific
  constraints that L4 VM workloads are validated against.

os_policy: required
firmware_policy: required

properties:
  # --- Hypervisor execution model ---
  execution_model:
    type: enum
    values: [bare_metal, hosted]
    description: >
      bare_metal = hypervisor installed directly on hardware.
      hosted = hypervisor installed on top of a host operating system.

  execution_model_support:
    type: list
    items: { type: enum, values: [bare_metal, hosted] }
    required: false
    description: >
      Optional for platforms that exist in multiple modes (for example Hyper-V
      and VMware). If omitted, assumed to be the single `execution_model` value.

  hardware_ref:
    type: reference
    required_if:
      execution_model: bare_metal
    description: >
      Reference to underlying hardware/device instance for bare-metal hypervisors.

  host_os_ref:
    type: reference
    required_if:
      execution_model: hosted
    description: >
      Reference to host OS instance when hypervisor runs on top of OS (Type-2).

  # --- Workload support declarations ---
  supported_workload_types:
    type: list
    items:
      type: enum
      values: [vm, lxc, docker, pod]
    description: Which L4 workload classes can target this hypervisor

  # --- VM constraints (checked by validators at compile time) ---
  vm_constraints:
    type: object
    properties:
      allowed_disk_formats:
        type: list
        items: { type: enum, values: [qcow2, raw, vmdk, vdi, vhd, vhdx, iso] }
      allowed_disk_buses:
        type: list
        items: { type: enum, values: [scsi, virtio, ide, sata, nvme, xvd] }
      allowed_firmware:
        type: list
        items: { type: enum, values: [seabios, ovmf, vbox_efi, vbox_bios, hyperv_gen1, hyperv_gen2, vmware_bios, vmware_efi, xen_bios, xen_uefi, xen_pv] }
      allowed_nic_types:
        type: list
        items: { type: string }
      max_disks_per_bus: { type: integer }
      supports_live_migration: { type: boolean, default: false }
      supports_snapshot: { type: boolean, default: true }
      supports_nested_virt: { type: boolean, default: false }

  # --- Platform-config schema (validates VM's platform_config bag) ---
  platform_config_schema:
    type: object
    description: >
      JSON Schema that validates the `platform_config` property on
      class.compute.workload.vm objects targeting this hypervisor.

required_capabilities:
  - cap.compute.host.hypervisor
```

### class.compute.hypervisor.proxmox

```yaml
class: class.compute.hypervisor.proxmox
inherits: class.compute.hypervisor
description: Proxmox VE hypervisor — QEMU/KVM VMs and LXC containers.

execution_model: bare_metal

supported_workload_types: [vm, lxc]

vm_constraints:
  allowed_disk_formats: [qcow2, raw, vmdk]
  allowed_disk_buses: [scsi, virtio, ide, sata]
  allowed_firmware: [seabios, ovmf]
  allowed_nic_types: [virtio, e1000, rtl8139]
  max_disks_per_bus: 16
  supports_live_migration: true
  supports_snapshot: true
  supports_nested_virt: true

platform_config_schema:
  type: object
  properties:
    machine_type: { type: enum, values: [q35, i440fx, pc], default: q35 }
    scsi_controller: { type: enum, values: [virtio-scsi-single, virtio-scsi-pci, lsi, megasas] }
    os_type: { type: enum, values: [l26, l24, win11, win10, win2k22, other] }
    vga: { type: enum, values: [std, virtio, qxl, serial0, none] }
    hotplug: { type: list, items: { type: enum, values: [network, disk, cpu, memory, usb] } }
    vmid: { type: integer, min: 100 }

required_capabilities:
  - cap.compute.host.hypervisor
  - cap.compute.runtime.container_host
  - cap.compute.runtime.vm_host

vendor_capabilities:
  - vendor.proxmox.cluster.node
  - vendor.proxmox.runtime.lxc
  - vendor.proxmox.runtime.qemu
```

### class.compute.hypervisor.vbox

```yaml
class: class.compute.hypervisor.vbox
inherits: class.compute.hypervisor
description: >
  Oracle VirtualBox — Type 2 hypervisor for development/testing.
  Runs on Windows, macOS, Linux host OS. Managed via VBoxManage CLI.

execution_model: hosted

supported_workload_types: [vm]

vm_constraints:
  allowed_disk_formats: [vdi, vmdk, vhd, raw]
  allowed_disk_buses: [sata, ide, scsi, nvme]
  allowed_firmware: [vbox_bios, vbox_efi]
  allowed_nic_types: [virtio, e1000, e1000e, pcnet_pci_ii, pcnet_fast_iii]
  max_disks_per_bus: 30
  supports_live_migration: false
  supports_snapshot: true          # VirtualBox snapshots (differencing images)
  supports_nested_virt: true

platform_config_schema:
  type: object
  properties:
    chipset: { type: enum, values: [piix3, ich9], default: ich9 }
    paravirt_provider: { type: enum, values: [none, default, legacy, minimal, hyperv, kvm] }
    graphics_controller: { type: enum, values: [vboxvga, vmsvga, vboxsvga, none] }
    audio_controller: { type: enum, values: [hda, ac97, sb16, none] }
    usb_controller: { type: enum, values: [none, ohci, ehci, xhci] }
    nested_virtualization: { type: boolean }
    guest_additions: { type: object, properties: { installed: boolean, version: string } }

vendor_capabilities:
  - vendor.oracle.runtime.virtualbox
```

### class.compute.hypervisor.hyperv

```yaml
class: class.compute.hypervisor.hyperv
inherits: class.compute.hypervisor
description: >
  Microsoft Hyper-V — Type 1 hypervisor (Server) or Type 1.5 (Windows client).
  Gen 1 (legacy BIOS, IDE boot) vs Gen 2 (UEFI, SCSI boot, Secure Boot).
  Managed via PowerShell Hyper-V module or WMI.

execution_model_support: [hosted, bare_metal]

supported_workload_types: [vm]

vm_constraints:
  allowed_disk_formats: [vhd, vhdx]
  allowed_disk_buses: [ide, scsi]        # Gen1: IDE boot. Gen2: SCSI boot.
  allowed_firmware: [hyperv_gen1, hyperv_gen2]
  allowed_nic_types: [synthetic, legacy]
  max_disks_per_bus: 64                  # SCSI: 4 controllers × 64 disks
  supports_live_migration: true          # Hyper-V Live Migration
  supports_snapshot: true                # Hyper-V checkpoints
  supports_nested_virt: true

platform_config_schema:
  type: object
  properties:
    generation: { type: enum, values: [1, 2], default: 2 }
    secure_boot: { type: boolean, default: true }
    tpm: { type: boolean, default: false }
    dynamic_memory:
      type: object
      properties:
        enabled: { type: boolean }
        min_mb: { type: integer }
        max_mb: { type: integer }
        buffer_percent: { type: integer }
    integration_services:
      type: list
      items: { type: enum, values: [guest_service, heartbeat, kvp_exchange, shutdown, time_sync, vss] }
    checkpoint_type: { type: enum, values: [standard, production, disabled] }

vendor_capabilities:
  - vendor.microsoft.runtime.hyperv
```

### class.compute.hypervisor.vmware

```yaml
class: class.compute.hypervisor.vmware
inherits: class.compute.hypervisor
description: >
  VMware hypervisor — ESXi (Type 1), Workstation/Fusion (Type 2).
  Uses VMDK disk format. Managed via vSphere API, govc CLI, PowerCLI.

execution_model_support: [bare_metal, hosted]

supported_workload_types: [vm]

vm_constraints:
  allowed_disk_formats: [vmdk]
  allowed_disk_buses: [scsi, sata, ide, nvme]
  allowed_firmware: [vmware_bios, vmware_efi]
  allowed_nic_types: [vmxnet3, e1000e, e1000, vmxnet2]
  max_disks_per_bus: 15                  # SCSI: 4 controllers × 15 disks
  supports_live_migration: true          # vMotion (ESXi only)
  supports_snapshot: true                # VMware snapshots (delta vmdk)
  supports_nested_virt: true

platform_config_schema:
  type: object
  properties:
    hardware_version: { type: integer, default: 21, description: "v21=ESXi 8.0U3" }
    guest_os_id: { type: string, description: "e.g., debian12_64Guest" }
    scsi_controller: { type: enum, values: [pvscsi, lsilogic, lsilogic_sas, buslogic] }
    disk_provisioning: { type: enum, values: [thin, thick_lazy, thick_eager] }
    vmtools: { type: object, properties: { installed: boolean, version: string } }
    vtpm: { type: boolean }
    vbs: { type: boolean, description: "Virtualization-Based Security" }

vendor_capabilities:
  - vendor.vmware.runtime.esxi
  # or: vendor.vmware.runtime.workstation
```

### class.compute.hypervisor.xen

```yaml
class: class.compute.hypervisor.xen
inherits: class.compute.hypervisor
description: >
  Xen / XCP-ng hypervisor — Type 1. Supports PV, HVM, PVH modes.
  Managed via xe CLI, XenAPI, or Xen Orchestra.

execution_model: bare_metal

supported_workload_types: [vm]

vm_constraints:
  allowed_disk_formats: [qcow2, vhd, raw]
  allowed_disk_buses: [xvd, ide, scsi]   # xvd = Xen virtual disk (PV/PVH)
  allowed_firmware: [xen_bios, xen_uefi, xen_pv]  # PV has no firmware
  allowed_nic_types: [xen_netfront, e1000, rtl8139]
  max_disks_per_bus: 16
  supports_live_migration: true
  supports_snapshot: true
  supports_nested_virt: false            # limited Xen nested virt support

platform_config_schema:
  type: object
  properties:
    virt_mode: { type: enum, values: [hvm, pv, pvh], default: hvm }
    viridian: { type: boolean, default: false, description: "Hyper-V enlightenments" }
    pae: { type: boolean, default: true }
    acpi: { type: boolean, default: true }

vendor_capabilities:
  - vendor.xen.runtime.xen
  # or: vendor.xcp.runtime.xcpng
```

### Validation Bridge: L1 Hypervisor ↔ L4 VM

```
Compile-time cross-layer validation:

1. RESOLVE HOST:
   vm_instance.host_ref → L1 host_instance → host_object → hypervisor_class

2. VALIDATE DISK FORMATS:
   FOR each disk in vm_instance.disks[]:
     disk.volume_ref → L3 volume → volume.format
     ASSERT volume.format ∈ hypervisor_class.vm_constraints.allowed_disk_formats

3. VALIDATE DISK BUSES:
   FOR each disk in vm_instance.disks[]:
     ASSERT disk.bus ∈ hypervisor_class.vm_constraints.allowed_disk_buses

4. VALIDATE FIRMWARE:
   vm_instance.firmware_ref → firmware_object → firmware.family
   ASSERT firmware.family ∈ hypervisor_class.vm_constraints.allowed_firmware

5. VALIDATE PLATFORM_CONFIG:
   vm_object.platform_config VALIDATES AGAINST
     hypervisor_class.platform_config_schema

6. VALIDATE WORKLOAD TYPE:
   ASSERT "vm" ∈ hypervisor_class.supported_workload_types

7. VALIDATE EXECUTION MODEL LINKAGE:
   IF hypervisor.execution_model == bare_metal:
     ASSERT hypervisor.hardware_ref exists
   IF hypervisor.execution_model == hosted:
     ASSERT hypervisor.host_os_ref exists
   IF hypervisor.execution_model_support includes both values:
     ASSERT one of {hardware_ref, host_os_ref} exists per instance mode
```

#### class.compute.workload.docker

```yaml
class: class.compute.workload.docker
inherits: class.compute.workload
description: >
  Docker/OCI container — image-based, typically ephemeral, application-scoped.
  Runs on a Docker Engine host (L1 device or L4 LXC with Docker installed).

firmware_policy: forbidden
os_policy: forbidden           # Docker containers don't have a full OS

properties:
  image:
    type: object
    required: true
    properties:
      repository: { type: string }
      tag: { type: string, default: "latest" }
      registry: { type: string, default: "docker.io" }
      digest: { type: string, required: false }

  runtime_host_ref:
    type: reference
    description: >
      The Docker Engine host. Can be L1 device (srv-orangepi5) or
      L4 LXC container with Docker (lxc-docker). Replaces host_ref
      from base class with Docker-specific semantics.

  restart_policy:
    type: enum
    values: [no, always, unless-stopped, on-failure]
    default: unless-stopped

  ports:
    type: list
    items:
      type: object
      properties:
        host_port: { type: integer }
        container_port: { type: integer }
        protocol: { type: enum, values: [tcp, udp], default: tcp }

  environment:
    type: map
    key_type: string
    value_type: string
    description: Environment variables (non-sensitive)

  secrets_refs:
    type: list
    items: { type: reference }
    description: SOPS-encrypted secret references

  compose_group:
    type: string
    required: false
    description: >
      Groups Docker containers that belong to the same docker-compose stack.
      All containers in a group share a Docker network.

  healthcheck:
    type: object
    required: false
    properties:
      test: { type: string }
      interval: { type: string, default: "30s" }
      timeout: { type: string, default: "10s" }
      retries: { type: integer, default: 3 }

capabilities:
  - cap.compute.workload.docker

vendor_capabilities:
  - vendor.runtime.docker.container

# Network override: Docker containers use Docker networking, not VLANs
network:
  type: object
  properties:
    mode:
      type: enum
      values: [bridge, host, macvlan, none]
      default: bridge
    docker_network: { type: string, required: false }
    interfaces: []  # inherits but typically empty — Docker manages networking

# Storage override: Docker uses volumes/bind mounts
storage:
  type: object
  properties:
    volumes:
      type: list
      items:
        type: object
        properties:
          name: { type: string }
          type: { type: enum, values: [volume, bind, tmpfs] }
          source: { type: string, description: "Host path or volume name" }
          target: { type: string, description: "Container mount path" }
          readonly: { type: boolean, default: false }
```

---

## 2. OBJECT LAYER PATTERNS

### 2.1 Naming Convention

```
obj.<platform>.<type>.<os>.<profile>

Examples (LXC — existing, kept):
  obj.proxmox.lxc.debian12.postgresql
  obj.proxmox.lxc.debian12.docker

Examples (VMs — new, multi-hypervisor):
  obj.proxmox.vm.debian12.standard        # Proxmox QEMU/KVM, Debian 12
  obj.proxmox.vm.debian12.cloud-init      # Proxmox with cloud-init
  obj.vbox.vm.debian12.dev                 # VirtualBox dev workstation
  obj.vbox.vm.win11.desktop               # VirtualBox Windows 11
  obj.hyperv.vm.debian12.wsl-adjacent     # Hyper-V Linux VM
  obj.hyperv.vm.win2022.server            # Hyper-V Windows Server
  obj.vmware.vm.debian12.esxi             # VMware ESXi VM
  obj.vmware.vm.debian12.workstation      # VMware Workstation VM
  obj.xen.vm.debian12.hvm                 # Xen HVM guest
  obj.xen.vm.debian12.pv                  # Xen PV guest

Examples (Docker — new):
  obj.docker.container.grafana
  obj.docker.container.prometheus
  obj.docker.stack.monitoring             # compose stack group
```

### 2.2 Object Template: Proxmox VM

```yaml
object: obj.proxmox.vm.debian12.standard
class_ref: class.compute.workload.vm     # one VM class for all hypervisors
description: Standard Debian 12 VM on Proxmox VE (QEMU/KVM)

software_contract:
  firmware_obj_ref: obj.firmware.proxmox.seabios
  os_obj_refs: [obj.os.debian.12.proxmox.vm]
  os_cardinality: { min: 1, max: 1 }
  multi_boot: false

agent:
  enabled: true
  type: qemu

# Proxmox-specific properties in platform_config
platform_config:
  machine_type: q35
  scsi_controller: virtio-scsi-single
  os_type: l26
  vga: std

capabilities:
  - cap.compute.workload.vm
  - cap.compute.workload.linux_base

vendor_capabilities:
  - vendor.proxmox.runtime.qemu
```

### 2.3 Object Template: VirtualBox VM

```yaml
object: obj.vbox.vm.debian12.dev
class_ref: class.compute.workload.vm     # same VM class
description: VirtualBox Debian 12 development VM

software_contract:
  firmware_obj_ref: obj.firmware.vbox.efi64
  os_obj_refs: [obj.os.debian.12.generic.x86_64]
  os_cardinality: { min: 1, max: 1 }
  multi_boot: false

agent:
  enabled: true
  type: virtualbox

# VirtualBox-specific properties in platform_config
platform_config:
  chipset: ich9
  paravirt_provider: kvm
  graphics_controller: vmsvga
  nested_virtualization: false
  guest_additions:
    installed: true

capabilities:
  - cap.compute.workload.vm
  - cap.compute.workload.linux_base

vendor_capabilities:
  - vendor.oracle.runtime.virtualbox
```

### 2.4 Object Template: Hyper-V VM

```yaml
object: obj.hyperv.vm.debian12.server
class_ref: class.compute.workload.vm     # same VM class
description: Hyper-V Generation 2 Debian 12 VM

software_contract:
  firmware_obj_ref: obj.firmware.hyperv.gen2.uefi
  os_obj_refs: [obj.os.debian.12.generic.x86_64]
  os_cardinality: { min: 1, max: 1 }

agent:
  enabled: true
  type: hyperv_ic

# Hyper-V-specific properties in platform_config
platform_config:
  generation: 2
  secure_boot: false
  tpm: false
  dynamic_memory:
    enabled: true
    min_mb: 512
    max_mb: 4096
    buffer_percent: 20
  integration_services: [guest_service, heartbeat, kvp_exchange, shutdown, time_sync]
  checkpoint_type: production

capabilities:
  - cap.compute.workload.vm
  - cap.compute.workload.linux_base

vendor_capabilities:
  - vendor.microsoft.runtime.hyperv
```

### 2.5 Object Template: VMware VM

```yaml
object: obj.vmware.vm.debian12.esxi
class_ref: class.compute.workload.vm     # same VM class
description: VMware ESXi Debian 12 VM

software_contract:
  firmware_obj_ref: obj.firmware.vmware.efi
  os_obj_refs: [obj.os.debian.12.generic.x86_64]
  os_cardinality: { min: 1, max: 1 }

agent:
  enabled: true
  type: vmware_tools

# VMware-specific properties in platform_config
platform_config:
  hardware_version: 21
  guest_os_id: debian12_64Guest
  scsi_controller: pvscsi
  disk_provisioning: thin
  vmtools:
    installed: true

capabilities:
  - cap.compute.workload.vm
  - cap.compute.workload.linux_base

vendor_capabilities:
  - vendor.vmware.runtime.esxi
```

### 2.6 Object Template: Xen VM

```yaml
object: obj.xen.vm.debian12.hvm
class_ref: class.compute.workload.vm     # same VM class
description: Xen HVM Debian 12 VM

software_contract:
  firmware_obj_ref: obj.firmware.xen.bios
  os_obj_refs: [obj.os.debian.12.generic.x86_64]
  os_cardinality: { min: 1, max: 1 }

agent:
  enabled: true
  type: xe_guest

# Xen-specific properties in platform_config
platform_config:
  virt_mode: hvm
  viridian: false
  pae: true
  acpi: true

capabilities:
  - cap.compute.workload.vm
  - cap.compute.workload.linux_base

vendor_capabilities:
  - vendor.xen.runtime.xen
```

---

## 3. NESTED TOPOLOGY MODEL

### 3.1 The Problem

A container is a computer-within-a-computer. It has:
- Network (interfaces, IPs, routes, DNS)
- Storage (rootfs, volumes, mounts)
- Compute (CPU/memory allocation)
- Software (OS packages, services)

Currently these are flat properties on the container instance.
As containers grow, we need composable nested topology.

### 3.2 Proposed: Topology Scope

Instead of full recursive topology (which would be unmanageable),
we introduce **topology scope** — a bounded reference namespace.

```yaml
# Container defines its own scope
instance: lxc-docker
topology_scope: scope.lxc-docker
  network:
    interfaces:
      - name: eth0
        bridge_ref: inst.bridge.vmbr0      # ← resolves in PARENT scope (L2)
        vlan_ref: inst.vlan.servers         # ← resolves in PARENT scope (L2)
        ip: 10.0.30.20/24
    internal_networks:                       # ← NEW: container-internal
      - name: docker0
        subnet: 172.17.0.0/16
        driver: bridge
      - name: monitoring-net
        subnet: 172.18.0.0/16
        driver: bridge

  storage:
    root: { pool_ref: inst.storage.pool.local_lvm, size_gb: 16 }
    volumes:
      - name: docker-data
        mount_point: /var/lib/docker
        pool_ref: inst.storage.pool.local_lvm
        size_gb: 50
```

### 3.3 Scope Resolution Rules

```
1. References to parent scope: use standard inst.* refs
   (bridge_ref, vlan_ref, pool_ref resolve at host level)

2. References within container scope: use scope.{container_id}.* prefix
   scope.lxc-docker.net.docker0
   scope.lxc-docker.vol.docker-data

3. Docker containers ON this container reference internal scope:
   runtime_host_ref: lxc-docker                        # L4 container
   network.docker_network: scope.lxc-docker.net.monitoring-net
```

### 3.4 Nesting Depth Limit

Maximum 2 levels:
```
L1 host → L4 container → L4 nested container (Docker-in-LXC)
```

No further nesting. This covers all practical home lab scenarios:
- Proxmox → LXC → Docker containers
- Proxmox → VM → Docker containers (future)
- MikroTik → containerD containers

---

## 4. DOCKER AT L4: MIGRATION PATTERN

### 4.1 Before (current)

```yaml
# L5 service directly references L1
instance: svc-grafana@docker.srv-orangepi5
runtime:
  type: docker
  target_ref: srv-orangepi5
```

### 4.2 After (proposed)

```yaml
# NEW L4 Docker container
instance: docker-grafana
object_ref: obj.docker.container.grafana
host_ref: srv-orangepi5              # or host_ref: lxc-docker
image:
  repository: grafana/grafana
  tag: "11.4"
# ... resource profile, ports, volumes

# L5 service references L4 container (uniform pattern)
instance: svc-grafana
runtime:
  type: docker
  target_ref: docker-grafana          # → L4 (not L1!)
  network_binding_ref: inst.vlan.servers
```

### 4.3 Migration Strategy

Phase 1: Add new Docker L4 instances alongside existing L5 services.
Phase 2: Update L5 `target_ref` to point at L4 Docker containers.
Phase 3: Remove inline Docker config from L5 services.

Backward compatibility: L5 `target_ref` pointing to L1 continues to
work (validated but deprecated). Validator emits WARNING, not ERROR.

---

## 5. RUNTIME HOST ABSTRACTION

### 5.1 Container Runtime as Capability

Rather than a separate entity, we model the container runtime as a
**capability** on the host that provides it:

```yaml
# L1 device (Orange Pi) declares Docker runtime capability
instance: srv-orangepi5
capabilities:
  - cap.compute.edge_node
  - cap.compute.runtime.container_host
  - vendor.runtime.docker.host   # ← "I can run Docker containers"
    properties:
      engine_version: "27.5"
      socket: /var/run/docker.sock
      storage_driver: overlay2

# L4 LXC container declares Docker runtime capability
instance: lxc-docker
capabilities:
  - cap.compute.workload.lxc
  - cap.compute.runtime.container_host
  - vendor.runtime.docker.host   # ← "I can run Docker containers too"
    properties:
      engine_version: "27.5"
      socket: /var/run/docker.sock
```

### 5.2 Runtime Validation Rule

```
For class.compute.workload.docker:
  host_ref target MUST have cap.compute.runtime.container_host
  AND vendor.runtime.docker.host
  
For class.compute.workload.lxc:
  host_ref target MUST have cap.compute.runtime.container_host
  (or class.compute.hypervisor.*)
  
For class.compute.workload.vm:
  host_ref target MUST have cap.compute.runtime.vm_host
  (or class.compute.hypervisor.*)
```

---

## 6. COMPOSE STACK GROUPING

### 6.1 Problem

Docker containers often deploy as a group (docker-compose stack).
We need to model this grouping without a new layer.

### 6.2 Proposed: Stack Object

```yaml
object: obj.docker.stack.monitoring
class_ref: class.compute.workload.docker.stack    # lightweight grouping class
description: Monitoring stack (Prometheus + Grafana + Node Exporter)

members:
  - docker-prometheus
  - docker-grafana
  - docker-node-exporter

shared_network: monitoring-net
restart_policy: unless-stopped
```

This is optional sugar — the individual containers work without it.
Stack objects enable generators to produce docker-compose.yaml files.

---

## 7. L3 ↔ L4 STORAGE INTEGRATION

### 7.1 The Problem

L3 storage (pools, volumes, data_assets) and L4 workloads (containers, VMs)
have different storage attachment models. The current LXC model is simple:
`pool_ref` + `size_gb` + `mount_point`. VMs need a richer model with disk
image formats, bus attachments, boot ordering, and multi-disk support.

Additionally, L3 `data_asset` instances exist but are NOT linked to L4 volumes,
breaking the governance chain (criticality → backup policy → volume placement).

### 7.2 Existing L3 Classes (No Changes Needed)

The current L3 class hierarchy is well-designed:

```
class.storage.pool       — physical/logical storage pool (dir, lvm, zfs, nfs, ceph)
class.storage.volume     — logical volume in a pool
class.storage.data_asset — named data entity with governance (backup, retention)
class.storage.media      — physical media (L1, foundational)
```

### 7.3 Proposed: Extend class.storage.volume

The `class.storage.volume` needs new properties to support VM disk images:

```yaml
class: class.storage.volume
# ... existing properties (name, size_bytes, pool_ref, mount_point, readonly) ...

# NEW properties for VM disk support:
properties:
  format:
    type: enum
    values: [raw, qcow2, vmdk, vdi, vhd, vhdx, subvol, iso]
    default: raw
    description: >
      Disk image format. 'raw' and 'subvol' for LXC.
      'qcow2' for Proxmox VMs. 'vmdk' for VMware.
      'vdi' for VirtualBox. 'vhd'/'vhdx' for Hyper-V.
      'iso' for CD-ROM images.

  bus_attachment:
    type: string
    required: false
    description: >
      Virtual bus slot when attached to a VM (e.g., scsi0, virtio1, ide2).
      Null for LXC volumes (which use mount_point instead).

  role:
    type: enum
    values: [rootfs, data, boot, cdrom, efivars, cloudinit, swap, backup, scratch]
    default: data
    description: >
      Semantic role of this volume:
      - rootfs: LXC container root filesystem
      - boot: VM primary boot disk
      - data: additional data storage
      - cdrom: ISO image for VM CD-ROM
      - efivars: OVMF/UEFI variable store
      - cloudinit: cloud-init configuration drive
      - swap: swap partition/file
      - backup: backup destination

  data_asset_ref:
    type: reference
    target_layer: L3
    target_class: class.storage.data_asset
    required: false
    description: >
      Links this volume to an L3 data_asset for governance.
      Enables: criticality tracking, backup policy inheritance,
      retention enforcement. (ADR 0026 D5)

  snapshot_capable:
    type: boolean
    default: false
    description: Whether this volume supports snapshots (format/pool dependent)
```

### 7.4 Format ↔ Pool Compatibility Matrix

Not all formats work on all pool types. Compile-time validation:

```
┌─────────────┬───────┬──────┬─────────┬─────┬─────┬──────┬──────┐
│ Pool Type   │  raw  │qcow2 │  vmdk   │ vdi │ vhd │ vhdx │subvol│
├─────────────┼───────┼──────┼─────────┼─────┼─────┼──────┼──────┤
│ dir         │  ✓    │  ✓   │   ✓     │  ✓  │  ✓  │  ✓   │  ✗  │
│ lvm         │  ✓    │  ✗   │   ✗     │  ✗  │  ✗  │  ✗   │  ✗  │
│ lvmthin     │  ✓    │  ✗   │   ✗     │  ✗  │  ✗  │  ✗   │  ✗  │
│ zfspool     │  ✓    │  ✗   │   ✗     │  ✗  │  ✗  │  ✗   │  ✓  │
│ nfs         │  ✓    │  ✓   │   ✓     │  ✓  │  ✓  │  ✓   │  ✗  │
│ cifs        │  ✓    │  ✓   │   ✓     │  ✓  │  ✓  │  ✓   │  ✗  │
│ cephfs      │  ✓    │  ✗   │   ✗     │  ✗  │  ✗  │  ✗   │  ✗  │
│ iscsi       │  ✓    │  ✗   │   ✗     │  ✗  │  ✗  │  ✗   │  ✗  │
└─────────────┴───────┴──────┴─────────┴─────┴─────┴──────┴──────┘
```

**Validation rule**: `volume.format ∈ pool.supported_formats`

### 7.5 Format ↔ Hypervisor Compatibility Matrix

Each hypervisor supports only certain disk formats:

```
┌────────────────────┬───────┬──────┬──────┬─────┬─────┬──────┐
│ Hypervisor         │  raw  │qcow2 │ vmdk │ vdi │ vhd │ vhdx │
├────────────────────┼───────┼──────┼──────┼─────┼─────┼──────┤
│ Proxmox QEMU/KVM   │  ✓    │  ✓   │  ✓*  │  ✗  │  ✗  │  ✗  │
│ Oracle VirtualBox   │  ✓    │  R   │  ✓   │  ✓  │  ✓  │  ✗  │
│ Microsoft Hyper-V   │  ✗    │  ✗   │  ✗   │  ✗  │  ✓  │  ✓  │
│ VMware ESXi         │  ✗    │  ✗   │  ✓   │  ✗  │  ✗  │  ✗  │
│ VMware Workstation  │  ✗    │  ✗   │  ✓   │  ✗  │  ✗  │  ✗  │
│ Xen / XCP-ng        │  ✓    │  ✓   │  ✗   │  ✗  │  ✓  │  ✗  │
│ LXC (Proxmox)       │  ✓    │  ✗   │  ✗   │  ✗  │  ✗  │  ✗  │
└────────────────────┴───────┴──────┴──────┴─────┴─────┴──────┘
✓* = import only (converted to qcow2/raw internally)
R  = read-only
```

**Validation rule**: `volume.format ∈ hypervisor_class.allowed_disk_formats`

### 7.6 L4 → L3 Storage Reference Patterns

#### LXC Container (existing, add data_asset_ref)

```yaml
instance: lxc-postgresql
storage:
  rootfs:
    pool_ref: inst.storage.pool.local_lvm     # L3 pool
    size_gb: 8
    # role: rootfs (implicit for rootfs)
  volumes:
    - mount_path: /var/lib/postgresql/data
      pool_ref: inst.storage.pool.local_lvm   # L3 pool
      size_gb: 20
      data_asset_ref: inst.data_asset.postgresql_db   # ← NEW: L3 governance link
    - mount_path: /var/backups/postgresql
      pool_ref: inst.storage.pool.local_hdd   # L3 pool (HDD for backups)
      size_gb: 50
      data_asset_ref: inst.data_asset.postgresql_dumps # ← NEW
```

#### Proxmox VM (new)

```yaml
instance: vm-k3s-master
object_ref: obj.proxmox.vm.debian12.cloud-init
host_ref: srv-gamayun

disks:
  - role: boot
    volume_ref: inst.vol.vm-k3s-master.boot   # L3 volume (qcow2, 32GB)
    bus: scsi
    slot: scsi0
    cache: writeback
    iothread: true
    discard: true
    bootable: true

  - role: data
    volume_ref: inst.vol.vm-k3s-master.data   # L3 volume (qcow2, 100GB)
    bus: scsi
    slot: scsi1
    data_asset_ref: inst.data_asset.k3s_data  # L3 data asset

  - role: cloudinit
    bus: ide
    slot: ide2
    # cloud-init drive auto-generated, no volume_ref needed
```

#### VirtualBox VM (example — dev workstation)

```yaml
instance: vm-dev-debian
object_ref: obj.vbox.vm.debian12.dev
host_ref: dev-workstation

disks:
  - role: boot
    volume_ref: inst.vol.vm-dev.boot           # L3 volume (vdi, 50GB)
    bus: sata
    slot: sata0
    bootable: true

  - role: data
    volume_ref: inst.vol.vm-dev.home           # L3 volume (vdi, 200GB)
    bus: sata
    slot: sata1
```

#### Hyper-V VM (example)

```yaml
instance: vm-hyperv-webserver
object_ref: obj.hyperv.vm.debian12.server
host_ref: dev-workstation-win

disks:
  - role: boot
    volume_ref: inst.vol.hyperv-web.boot       # L3 volume (vhdx, 40GB)
    bus: scsi                                   # Gen2 boots from SCSI
    slot: scsi0
    bootable: true

  - role: data
    volume_ref: inst.vol.hyperv-web.data       # L3 volume (vhdx, 100GB)
    bus: scsi
    slot: scsi1
    data_asset_ref: inst.data_asset.webserver_data
```

### 7.7 L3 Volume Instances for VMs (New Pattern)

```yaml
# L3 volume instance — VM boot disk
instance: inst.vol.vm-k3s-master.boot
object_ref: obj.storage.volume.vm_disk
pool_ref: inst.storage.pool.local_lvm
layer: L3
format: qcow2
size_bytes: 34359738368           # 32 GB
role: boot
snapshot_capable: true

# L3 volume instance — VM data disk with governance link
instance: inst.vol.vm-k3s-master.data
object_ref: obj.storage.volume.vm_disk
pool_ref: inst.storage.pool.local_lvm
layer: L3
format: qcow2
size_bytes: 107374182400          # 100 GB
role: data
data_asset_ref: inst.data_asset.k3s_data
snapshot_capable: true
```

### 7.8 L3 Storage Object: VM Disk Template (New)

```yaml
object: obj.storage.volume.vm_disk
class_ref: class.storage.volume
description: Virtual machine disk image volume

# Default properties — overridden by instances
format: qcow2                    # most common for Proxmox
role: data
readonly: false
snapshot_capable: true

capabilities:
  - cap.storage.volume.persistent
  - cap.storage.volume.snapshot
```

### 7.9 Validation Chain (L3 ↔ L4)

```
Compile-time validations:

1. FORMAT ↔ POOL:
   volume.format ∈ pool_type.supported_formats[]
   Example: qcow2 NOT allowed on lvmthin pool → ERROR

2. FORMAT ↔ HYPERVISOR:
   volume.format ∈ vm_class.allowed_disk_formats[]
   Example: vmdk on Hyper-V → ERROR

3. DATA_ASSET GOVERNANCE:
   IF volume.data_asset_ref.criticality == "critical"
   THEN volume.pool_ref.type ∈ [lvmthin, zfspool]  # reliable pools only
   AND  volume.snapshot_capable == true

4. BOOT DISK REQUIRED:
   FOR each VM instance:
     disks[] MUST contain exactly 1 disk with role: boot AND bootable: true

5. BUS ↔ HYPERVISOR:
   disk.bus ∈ vm_class.allowed_disk_buses[]
   Example: nvme bus on VirtualBox → ERROR (not supported)

6. LXC ROOTFS REQUIRED:
   FOR each LXC instance:
     storage.rootfs MUST be present with pool_ref
```

### 7.10 Docker Volume → L3 Integration

Docker volumes use a simpler model (no disk images), but still link to L3:

```yaml
# Docker container at L4
instance: docker-grafana
storage:
  volumes:
    - name: grafana-data
      type: volume                           # Docker named volume
      source: grafana-data
      target: /var/lib/grafana
      data_asset_ref: inst.data_asset.grafana # ← L3 governance link

    - name: grafana-config
      type: bind                             # Bind mount from host
      source: /opt/grafana/provisioning
      target: /etc/grafana/provisioning
      readonly: true
      # No data_asset_ref — config managed by provisioning, not backed up as data
```

**Docker volume types and L3 mapping:**

| Docker Type | L3 Equivalent | Backed by |
|------------|---------------|-----------|
| `volume` (named) | L3 volume on host pool | Docker storage driver (overlay2) |
| `bind` | Host filesystem path | L3 volume containing the host path |
| `tmpfs` | N/A (ephemeral) | RAM — no L3 reference needed |
| `nfs` | L3 NFS pool → volume | External NFS server |

---

## 8. REFERENCE ARCHITECTURE (FULL PICTURE)

```
┌─────────────────────────────────────────────────────────────────┐
│  L7: Operations (backup, deploy, automation)                    │
│    target_refs → L1, L4, L5, L6                                 │
├─────────────────────────────────────────────────────────────────┤
│  L6: Observability (monitoring, logging, alerts)                │
│    monitor_refs → L1, L4, L5                                    │
├─────────────────────────────────────────────────────────────────┤
│  L5: Application (services)                                     │
│    svc-postgresql     → target_ref: lxc-postgresql   (L4 LXC)  │
│    svc-grafana        → target_ref: docker-grafana   (L4 Docker)│
│    svc-nextcloud      → target_ref: lxc-nextcloud    (L4 LXC)  │
│    svc-k3s            → target_ref: vm-k3s-master    (L4 VM)   │
├─────────────────────────────────────────────────────────────────┤
│  L4: Platform (ALL workload types)                              │
│    ┌──────────────────────────────────────────────────────┐     │
│    │  LXC Containers  (class.compute.workload.lxc)        │     │
│    │  lxc-postgresql, lxc-nextcloud, lxc-docker, ...      │     │
│    │  host_ref → srv-gamayun (L1)                         │     │
│    │  storage.rootfs.pool_ref → inst.storage.pool.* (L3)  │     │
│    │  storage.volumes[].data_asset_ref → L3 assets        │     │
│    ├──────────────────────────────────────────────────────┤     │
│    │  Docker Containers (class.compute.workload.docker)    │     │
│    │  docker-grafana, docker-prometheus, ...        ← NEW  │     │
│    │  host_ref → srv-orangepi5 (L1) or lxc-docker (L4)   │     │
│    │  storage.volumes[].data_asset_ref → L3 assets        │     │
│    ├──────────────────────────────────────────────────────┤     │
│    │  VMs (class.compute.workload.vm)               ← NEW  │     │
│    │  host_ref → L1 hypervisor (determines platform)       │     │
│    │  platform_config validated by hypervisor class         │     │
│    │  ┌─ Proxmox: vm-k3s-master → srv-gamayun             │     │
│    │  ├─ VBox: vm-dev-sandbox → dev-workstation            │     │
│    │  ├─ Hyper-V: vm-hyperv-web → dev-workstation-win      │     │
│    │  └─ VMware: vm-vmware-db → esxi-host                  │     │
│    │  disks[].volume_ref → inst.vol.* (L3 volumes)        │     │
│    │  disks[].data_asset_ref → L3 assets                  │     │
│    └──────────────────────────────────────────────────────┘     │
├─────────────────────────────────────────────────────────────────┤
│  L3: Data (storage chain)                                       │
│    ┌─────────────────────────────────────────────┐              │
│    │  Pools: local, local_lvm, local_hdd         │              │
│    │    ← pool_ref from L4 containers            │              │
│    │    ← pool_ref from L3 volumes               │              │
│    ├─────────────────────────────────────────────┤              │
│    │  Volumes: inst.vol.vm-*.boot (qcow2/vmdk/   │  ← NEW      │
│    │    vdi/vhdx), inst.vol.vm-*.data, ...       │              │
│    │    ← volume_ref from L4 VM disks            │              │
│    ├─────────────────────────────────────────────┤              │
│    │  Data Assets: postgresql_db, grafana,        │              │
│    │    redis, nextcloud, wireguard, ...          │              │
│    │    ← data_asset_ref from L4 volumes/disks   │  ← NEW link │
│    └─────────────────────────────────────────────┘              │
├─────────────────────────────────────────────────────────────────┤
│  L2: Network (bridges, VLANs, firewall)                         │
│    bridge_ref, vlan_ref ← L4 containers/VMs                    │
├─────────────────────────────────────────────────────────────────┤
│  L1: Foundation (physical/cloud devices + hypervisor platforms)  │
│    class.compute.hypervisor.proxmox: srv-gamayun                │
│    class.compute.hypervisor.vbox: dev-workstation               │
│    class.compute.hypervisor.hyperv: dev-workstation-win         │
│    class.compute.edge_node: srv-orangepi5 [cap.compute.runtime.container_host + vendor.runtime.docker.host] │
│    class.router: rtr-mikrotik-chateau [cap.compute.runtime.container_host]   │
│    host_ref ← L4 workloads                                      │
├─────────────────────────────────────────────────────────────────┤
│  L0: Meta (site, naming, conventions)                           │
└─────────────────────────────────────────────────────────────────┘
```

### 8.1 Cross-Layer Reference Flow (Complete)

```
L5 svc-postgresql
  └─ runtime.target_ref ──→ L4 lxc-postgresql
       ├─ host_ref ──→ L1 srv-gamayun
       ├─ network.bridge_ref ──→ L2 inst.bridge.vmbr0
       ├─ network.vlan_ref ──→ L2 inst.vlan.servers
       ├─ storage.rootfs.pool_ref ──→ L3 inst.storage.pool.local_lvm
       └─ storage.volumes[0]
            ├─ pool_ref ──→ L3 inst.storage.pool.local_lvm
            └─ data_asset_ref ──→ L3 inst.data_asset.postgresql_db  ← NEW
                                      └─ criticality: critical
                                      └─ backup_policy: daily

L5 svc-k3s
  └─ runtime.target_ref ──→ L4 vm-k3s-master
       ├─ host_ref ──→ L1 srv-gamayun
       ├─ network.interfaces[0].bridge_ref ──→ L2 inst.bridge.vmbr0
       ├─ disks[0] (boot)
       │    └─ volume_ref ──→ L3 inst.vol.vm-k3s.boot (qcow2, 32GB)
       │         └─ pool_ref ──→ L3 inst.storage.pool.local_lvm
       └─ disks[1] (data)
            ├─ volume_ref ──→ L3 inst.vol.vm-k3s.data (qcow2, 100GB)
            │    └─ pool_ref ──→ L3 inst.storage.pool.local_lvm
            └─ data_asset_ref ──→ L3 inst.data_asset.k3s_data       ← NEW
```

---

## 8A. WORKED EXAMPLE: NGINX CONTAINER ON MIKROTIK

This section provides a **complete end-to-end example** of modeling an nginx
reverse proxy running as a RouterOS containerD container on MikroTik Chateau.
It demonstrates all layers (L1–L7), the new L4 Docker entity, RouterOS
platform-specific `platform_config`, and cross-layer reference flow.

### 8A.1 AS-IS Pattern (Current — GAP-2)

Currently Docker services on MikroTik skip L4 entirely:

```yaml
# L5 service references L1 device directly — NO L4 entity exists
instance: svc-adguard
runtime:
  type: docker
  target_ref: rtr-mikrotik-chateau    # ← L5 → L1 (gap)
  image: adguard/adguardhome
```

The container (CPU, RAM, veth, mounts) is invisible to the topology.
Only the application-level service is modeled.

### 8A.2 TO-BE Pattern (ADR 0087 — Full Chain)

#### L1: MikroTik Runtime Capability Declaration

The existing `rtr-mikrotik-chateau` instance is extended with a
unified runtime capability (see §5 Runtime Host Abstraction):

```yaml
# Дополнение к rtr-mikrotik-chateau.yaml
runtime_capabilities:
  - capability: cap.compute.runtime.container_host
    engine: containerD                  # RouterOS containerD (not full Docker)
    engine_version: "7.22"              # RouterOS version = containerD version
    storage_backend: usb                # /usb1/containers/
    max_containers: 10                  # practical limit with 1GB RAM
    registry_url: https://registry-1.docker.io
    supported_architectures: [arm64]    # IPQ-6010 = ARM64 only
    networking_mode: veth               # RouterOS veth → bridge
    port_mapping: dst-nat               # DST-NAT firewall rules (not Docker -p)
```

Key RouterOS constraints:
- No CPU cgroup limits (all containers share 4× ARM cores)
- veth interface per container, bridged to existing bridge
- Ports exposed via `/ip/firewall/nat` DST-NAT rules
- USB storage for container rootfs and bind mounts

#### L3: Data Asset for Nginx Configuration

```yaml
# projects/home-lab/topology/instances/L3-data/data-assets/inst.data_asset.nginx_config.yaml
instance: inst.data_asset.nginx_config
object_ref: obj.storage.data_asset.config
group: data-assets
layer: L3
version: 1.0.0
source_id: data-nginx-config
status: planned
notes: Nginx configuration and static site content on MikroTik USB storage

host_ref: rtr-mikrotik-chateau
criticality: normal
backup_policy: weekly

properties:
  storage_path: /usb1/nginx
  content_type: configuration
  includes:
    - nginx.conf
    - conf.d/*.conf
    - html/*
```

#### Object: Docker Container Nginx

```yaml
# topology/object-modules/docker/obj.docker.container.nginx.yaml
object: obj.docker.container.nginx
class_ref: class.compute.workload.docker
version: 1.0.0
title: Nginx Reverse Proxy Container
vendor: nginx_inc
model: nginx-alpine

description: >
  Nginx reverse proxy / web server — lightweight Alpine-based container
  suitable for ARM64 edge devices with limited RAM (MikroTik, Orange Pi).

image_contract:
  repository: library/nginx
  supported_tags: ["1.27-alpine", "1.27", "stable-alpine", "mainline-alpine"]
  architectures: [amd64, arm64, arm/v7]
  min_memory_mb: 16
  recommended_memory_mb: 32

capabilities:
  - cap.compute.workload.docker
  - cap.service.web.reverse_proxy
  - cap.service.web.static_content
  - cap.service.web.tls_termination

vendor_capabilities:
  - vendor.nginx.http_server
  - vendor.nginx.stream_proxy

defaults:
  restart_policy: unless-stopped
  healthcheck:
    test: "wget -q --spider http://127.0.0.1/health || exit 1"
    interval: "30s"
```

#### L4: Docker Container Instance (NEW ENTITY)

```yaml
# projects/home-lab/topology/instances/L4-platform/docker/rtr-mikrotik-chateau/docker-nginx.yaml
instance: docker-nginx
object_ref: obj.docker.container.nginx
group: containers
layer: L4
version: 1.0.0
source_id: docker-nginx
status: planned
notes: >
  Nginx reverse proxy running as RouterOS containerD container.
  Serves as HTTPS frontend for MikroTik-hosted services (AdGuard, Mosquitto).

# ─── Host binding (L1) ───
host_ref: rtr-mikrotik-chateau

# ─── OCI image ───
image:
  registry: docker.io
  repository: library/nginx
  tag: "1.27-alpine"
  digest: null                           # pin later for immutability
  platform: linux/arm64                  # MikroTik IPQ-6010 = ARM64

# ─── Resource profile ───
resource_profile:
  cpu_cores: 0                           # no CPU limit (RouterOS limitation)
  memory_mb: 32
  memory_limit_mb: 64                    # OOM kill threshold
  rootfs_size_mb: 50                     # container filesystem on USB

# ─── Network (RouterOS veth) ───
network:
  mode: veth                              # RouterOS containers use veth interface
  veth_interface: veth-nginx              # /interface/veth add name=veth-nginx
  bridge_ref: bridge                      # /interface/bridge/port add bridge=bridge
  ip_address: 192.168.88.250/24          # static IP in LAN segment
  gateway: 192.168.88.1                  # MikroTik gateway
  dns: 192.168.88.1                      # MikroTik DNS resolver
  vlan_ref: inst.vlan.lan                # topology VLAN reference

# ─── Ports (via DST-NAT, not Docker -p) ───
ports:
  - host_port: 8080
    container_port: 80
    protocol: tcp
    description: HTTP reverse proxy
  - host_port: 8443
    container_port: 443
    protocol: tcp
    description: HTTPS reverse proxy

# ─── Environment variables ───
environment:
  TZ: "Europe/Moscow"
  NGINX_WORKER_PROCESSES: "1"            # save RAM on arm64/1GB device

# ─── Volumes (bind mounts on USB) ───
storage:
  volumes:
    - name: nginx-config
      type: bind
      source: /usb1/nginx/nginx.conf     # host path (MikroTik USB)
      target: /etc/nginx/nginx.conf      # container path
      readonly: true
    - name: nginx-conf-d
      type: bind
      source: /usb1/nginx/conf.d
      target: /etc/nginx/conf.d
      readonly: true
    - name: nginx-html
      type: bind
      source: /usb1/nginx/html
      target: /usr/share/nginx/html
      readonly: true
    - name: nginx-logs
      type: bind
      source: /usb1/nginx/logs
      target: /var/log/nginx
      readonly: false
  data_asset_refs:
    - inst.data_asset.nginx_config

# ─── Lifecycle ───
restart_policy: unless-stopped

healthcheck:
  test: "wget -q --spider http://127.0.0.1:80/health || exit 1"
  interval: "30s"
  timeout: "5s"
  retries: 3

# ─── RouterOS platform_config (containerD specifics) ───
platform_config:
  routeros:
    interface: veth-nginx
    envlist: nginx-envs                  # /container/envs name group
    root_dir: /usb1/containers/nginx     # container rootfs on USB
    mounts:
      - name: nginx-config
        src: /usb1/nginx/nginx.conf
        dst: /etc/nginx/nginx.conf
      - name: nginx-html
        src: /usb1/nginx/html
        dst: /usr/share/nginx/html
      - name: nginx-logs
        src: /usb1/nginx/logs
        dst: /var/log/nginx
    # Terraform resource mapping
    terraform_resource: routeros_container
    terraform_provider: terraform-routeros/routeros

depends_on: []
```

#### L5: Application Service (references L4, not L1)

```yaml
# projects/home-lab/topology/instances/L5-application/services/rtr-mikrotik-chateau/svc-nginx.yaml
instance: svc-nginx
object_ref: obj.service.web.reverse_proxy
group: services
layer: L5
version: 1.0.0
source_id: svc-nginx
status: planned
notes: >
  Nginx reverse proxy fronting AdGuard, Mosquitto WebSocket, and static
  status page on MikroTik Chateau.

ports:
  http: 8080
  https: 8443
protocol: http
trust_zone_ref: inst.trust_zone.servers
description: Nginx reverse proxy for MikroTik-hosted services
critical: false

# ─── KEY CHANGE: target_ref → L4 container, not L1! ───
runtime:
  type: docker
  target_ref: docker-nginx                # ← L4 (NEW!)
  network_binding_ref: inst.vlan.lan

features:
  - Reverse proxy for AdGuard WebUI
  - HTTPS termination (self-signed / Let's Encrypt)
  - Static status page
  - WebSocket proxy for Mosquitto

upstreams:
  - name: adguard
    service_ref: svc-adguard
    backend: "192.168.88.251:3000"
    path_prefix: /adguard/
  - name: mosquitto-ws
    service_ref: svc-mosquitto
    backend: "192.168.88.252:9001"
    path_prefix: /mqtt/
    websocket: true

security:
  ssl_certificate: self-signed
  https_redirect: true
  allowed_from:
    - inst.vlan.lan
    - inst.vlan.servers

data_asset_refs:
  - inst.data_asset.nginx_config
```

#### L6: Observability

```yaml
# projects/home-lab/topology/instances/L6-observability/observability/health-docker-nginx.yaml
instance: health-docker-nginx
object_ref: obj.observability.healthcheck.service
group: observability
layer: L6
version: 1.0.0
source_id: health-docker-nginx
status: planned
notes: Nginx container health monitoring

name: Nginx Container Health
description: Monitor Nginx reverse proxy container on MikroTik
target_ref: docker-nginx                  # ← L4 container reference
enabled: true
critical: false

checks:
  - type: http
    url: "http://192.168.88.250:80/health"
    expected_status: 200
    timeout_ms: 3000
  - type: container_status
    method: routeros_api                  # /container/print where name=nginx
    expected_state: running

interval: 60s
timeout: 10s

notification:
  on_warning: true
  on_critical: true
  channels:
    - channel-telegram
```

#### L7: Operations (Backup)

```yaml
# projects/home-lab/topology/instances/L7-operations/operations/backup-nginx-config.yaml
instance: backup-nginx-config
object_ref: obj.operations.backup.file_copy
group: operations
layer: L7
version: 1.0.0
source_id: backup-nginx-config
status: planned
notes: Backup nginx config from MikroTik USB to Git

name: Nginx Config Backup
description: Copy nginx config from MikroTik USB storage to backup repo
schedule: "0 4 * * 0"                    # weekly Sunday 4:00

target_ref: rtr-mikrotik-chateau
data_asset_ref: inst.data_asset.nginx_config

source:
  type: sftp
  path: /usb1/nginx/
  include: ["nginx.conf", "conf.d/*"]

destination:
  type: git
  repository: /home/dmpr/workspaces/projects/home-lab/backups/mikrotik
  subdir: nginx/
  branch: main
```

### 8A.3 Cross-Layer Reference Graph

```
L7 backup-nginx-config
  ├─ data_asset_ref ──→ L3 inst.data_asset.nginx_config
  └─ target_ref ──→ L1 rtr-mikrotik-chateau

L6 health-docker-nginx
  └─ target_ref ──→ L4 docker-nginx

L5 svc-nginx
  ├─ runtime.target_ref ──→ L4 docker-nginx          ← NEW (was → L1)
  └─ data_asset_refs ──→ L3 inst.data_asset.nginx_config

L4 docker-nginx
  ├─ host_ref ──→ L1 rtr-mikrotik-chateau
  │     └─ runtime_capabilities: cap.compute.runtime.container_host (containerD)
  ├─ network.bridge_ref ──→ L2 bridge (MikroTik bridge)
  ├─ network.vlan_ref ──→ L2 inst.vlan.lan
  ├─ storage.data_asset_refs ──→ L3 inst.data_asset.nginx_config
  └─ image: docker.io/library/nginx:1.27-alpine (linux/arm64)

L3 inst.data_asset.nginx_config
  └─ host_ref ──→ L1 rtr-mikrotik-chateau (USB storage)

L1 rtr-mikrotik-chateau
  └─ cap.compute.runtime.container_host (containerD, arm64, USB, max_containers=10)
```

### 8A.4 Generated RouterOS CLI (Terraform Output)

The Terraform MikroTik generator produces these RouterOS commands:

```routeros
# 1. veth interface
/interface/veth add name=veth-nginx address=192.168.88.250/24 gateway=192.168.88.1

# 2. Bridge port
/interface/bridge/port add bridge=bridge interface=veth-nginx

# 3. Environment variables
/container/envs add name=nginx-envs key=TZ value="Europe/Moscow"
/container/envs add name=nginx-envs key=NGINX_WORKER_PROCESSES value="1"

# 4. Bind mounts
/container/mounts add name=nginx-config src=/usb1/nginx/nginx.conf dst=/etc/nginx/nginx.conf
/container/mounts add name=nginx-html src=/usb1/nginx/html dst=/usr/share/nginx/html
/container/mounts add name=nginx-logs src=/usb1/nginx/logs dst=/var/log/nginx

# 5. Container
/container add remote-image=docker.io/library/nginx:1.27-alpine \
  interface=veth-nginx root-dir=/usb1/containers/nginx \
  envlist=nginx-envs mounts=nginx-config,nginx-html,nginx-logs \
  hostname=nginx start-on-boot=yes

# 6. DST-NAT port mapping (RouterOS doesn't have Docker -p)
/ip/firewall/nat add chain=dstnat protocol=tcp dst-port=8080 \
  action=dst-nat to-addresses=192.168.88.250 to-ports=80 \
  comment="nginx HTTP reverse proxy"
/ip/firewall/nat add chain=dstnat protocol=tcp dst-port=8443 \
  action=dst-nat to-addresses=192.168.88.250 to-ports=443 \
  comment="nginx HTTPS reverse proxy"
```

### 8A.5 RouterOS vs Standard Docker — Key Differences

| Aspect | Standard Docker | RouterOS containerD |
|--------|----------------|---------------------|
| Networking | `docker network`, bridge driver | veth interface → MikroTik bridge |
| Port mapping | `-p 8080:80` (userspace proxy) | DST-NAT firewall rule |
| CPU limits | `--cpus`, cgroups | Not supported (shared ARM cores) |
| Memory limits | `--memory`, cgroups | Memory limit field in /container |
| Storage driver | overlay2, btrfs | Flat directory on USB/disk |
| Compose | docker-compose.yaml | Not available (individual /container commands) |
| Image pull | `docker pull` | `/container add remote-image=...` |
| Healthcheck | HEALTHCHECK in Dockerfile | External (API poll or /container/print) |
| Architecture | amd64, arm64, arm/v7 | ARM64 only (device-specific) |

This table drives the `platform_config.routeros` bag in the L4 instance,
ensuring the Terraform generator produces RouterOS-native commands rather
than docker-compose artifacts.

---

## 8B. WORKED EXAMPLE: NGINX ON PROXMOX (srv-gamayun)

This section provides a **complete end-to-end example** of modeling nginx on
Proxmox VE running on srv-gamayun. It demonstrates **two deployment variants**
using the ADR 0087 ontology:

- **Variant A**: Nginx as a **native LXC container** (baremetal nginx in Debian LXC)
- **Variant B**: Nginx as a **Docker container inside an LXC-Docker host** (Docker-in-LXC)

Both variants show all layers (L1–L7), the renamed class hierarchy
(`class.compute.workload.lxc`), L3↔L4 storage integration with the
new `format`, `role`, and `data_asset_ref` fields, and cross-layer
validation with `class.compute.hypervisor.proxmox`.

### 8B.1 AS-IS Pattern (Current)

The existing `lxc-nginx-proxy` (vmid 207) uses the old class name and
lacks L3 storage enrichment:

```yaml
# Current L4 — uses old class name, no format/role on storage
instance: lxc-nginx-proxy
object_ref: obj.proxmox.lxc.debian12.nginx    # class: class.compute.workload.container
storage:
  rootfs:
    pool_ref: inst.storage.pool.local_lvm
    size_gb: 4                                 # no format, no role, no data_asset_ref

# Current L5 — already correct (target_ref → L4)
instance: svc-nginx-proxy
runtime:
  type: lxc
  target_ref: lxc-nginx-proxy
```

### 8B.2 Host Infrastructure (L1 + L3 — shared by both variants)

#### L1: Proxmox Hypervisor with Runtime Capabilities

```yaml
# Existing: srv-gamayun.yaml — extended with runtime capabilities
instance: srv-gamayun
object_ref: obj.proxmox.ve
# ...existing fields...

# ─── NEW: explicit runtime capability declarations ───
runtime_capabilities:
  - capability: cap.compute.runtime.container_host
    engine: proxmox-lxc
    engine_version: "9.0"
    max_containers: 20                   # practical limit with 8GB RAM
    supported_os_templates:
      - debian-12-standard
      - ubuntu-24.04-standard
      - alpine-3.20-default

  - capability: cap.compute.runtime.vm_host
    engine: qemu-kvm
    engine_version: "8.2"
    machine_types: [q35, i440fx]
    firmware: [seabios, ovmf]
```

#### L3: Storage Pools (enriched per ADR 0087 §7)

```yaml
# inst.storage.pool.local_lvm — existing, enriched
instance: inst.storage.pool.local_lvm
object_ref: obj.storage.pool.local_lvm
host_ref: srv-gamayun
# ─── NEW fields from ADR 0087 ───
properties:
  type: lvmthin
  vg_name: pve
  thinpool: data
  total_size_gb: 150
  supported_formats: [raw]               # lvmthin = raw only
  supported_content: [images, rootdir]
  snapshot_capable: true

# inst.storage.pool.local — existing, enriched
instance: inst.storage.pool.local
object_ref: obj.storage.pool.local
host_ref: srv-gamayun
properties:
  type: dir
  path: /var/lib/vz
  total_size_gb: 30
  supported_formats: [qcow2, raw, vmdk, subvol]  # dir supports all
  supported_content: [images, rootdir, vztmpl, iso, backup, snippets]
  snapshot_capable: false

# inst.storage.pool.local_hdd — existing, enriched
instance: inst.storage.pool.local_hdd
object_ref: obj.storage.pool.local_hdd
host_ref: srv-gamayun
properties:
  type: dir
  path: /mnt/hdd
  total_size_gb: 450
  supported_formats: [qcow2, raw, vmdk, subvol]
  supported_content: [backup, iso, vztmpl, images]
  snapshot_capable: false
```

### 8B.3 Variant A: Nginx as Native LXC Container

This is the **existing deployment pattern** upgraded to ADR 0087 ontology.
Nginx runs as a Debian package inside a Proxmox LXC container.

#### L3: Data Asset for Nginx Config

```yaml
# projects/home-lab/topology/instances/L3-data/data-assets/inst.data_asset.nginx_proxy_config.yaml
instance: inst.data_asset.nginx_proxy_config
object_ref: obj.storage.data_asset.config
group: data-assets
layer: L3
version: 1.0.0
source_id: data-nginx-proxy-config
status: mapped
notes: Nginx reverse proxy configuration on Proxmox LXC

host_ref: srv-gamayun
criticality: high
backup_policy: daily

properties:
  storage_path: /var/lib/vz/lxc/207/rootfs/etc/nginx
  content_type: configuration
  includes:
    - nginx.conf
    - conf.d/*.conf
    - sites-enabled/*
    - ssl/certs/*
```

#### L4: LXC Container Instance (upgraded ontology)

```yaml
# projects/home-lab/topology/instances/L4-platform/lxc/srv-gamayun/lxc-nginx-proxy.yaml
# ─── UPGRADED from current model ───
instance: lxc-nginx-proxy
object_ref: obj.proxmox.lxc.debian12.nginx
group: lxc
layer: L4
version: 2.0.0                            # bumped for ADR 0087
source_id: lxc-nginx-proxy
status: mapped
notes: >
  Nginx reverse proxy as native LXC container on Proxmox.
  Fronts Grafana, Nextcloud, Gitea, Prometheus dashboards.

vmid: 207
hostname: nginx-proxy
description: Nginx reverse proxy for server VLAN services
tags:
  - proxy
  - production

# ─── Host binding → L1 Proxmox hypervisor ───
host_ref: srv-gamayun

# ─── OS reference ───
os_refs:
  - inst.os.debian.12.proxmox.lxc

# ─── Resource profile ───
resource_profile:
  cpu_cores: 1
  memory_mb: 256
  memory_limit_mb: 512
  swap_mb: 256

# ─── Boot ───
boot:
  onboot: true
  startup_order: 15

# ─── Storage (ENRICHED per ADR 0087 §7) ───
storage:
  rootfs:
    pool_ref: inst.storage.pool.local_lvm
    size_gb: 4
    format: raw                            # ← NEW: lvmthin → raw only
    role: rootfs                           # ← NEW: explicit role
  volumes: []                              # nginx config lives on rootfs

# ─── Network ───
network:
  interface: eth0
  bridge_ref: inst.bridge.vmbr0
  vlan_ref: inst.vlan.servers
  ip: 10.0.30.80/24
  gateway: 10.0.30.1
  firewall: false

# ─── DNS ───
dns:
  nameserver: 192.168.88.1
  searchdomain: home.local

# ─── Proxmox platform_config (validated against hypervisor class) ───
platform_config:
  proxmox:
    arch: amd64
    ostype: debian
    unprivileged: true
    features: []                           # no nesting, no fuse
    # Terraform resource mapping
    terraform_resource: proxmox_virtual_environment_container
    terraform_provider: bpg/proxmox

# ─── Trust zone ───
trust_zone_ref: inst.trust_zone.servers

# ─── Provisioning ───
cloudinit:
  enabled: true
  user: root

ansible:
  enabled: true
  playbook: nginx-proxy.yml

# ─── Data asset references ───
data_asset_refs:
  - inst.data_asset.nginx_proxy_config
```

#### L5: Application Service

```yaml
# projects/home-lab/topology/instances/L5-application/services/srv-gamayun/svc-nginx-proxy.yaml
instance: svc-nginx-proxy
object_ref: obj.service.nginx_proxy
group: services
layer: L5
version: 1.0.0
source_id: svc-nginx-proxy
status: mapped
notes: >
  Nginx reverse proxy fronting all server-VLAN web services.
  Managed by Ansible (nginx-proxy.yml playbook).

ports:
  http: 80
  https: 443
protocol: http
trust_zone_ref: inst.trust_zone.servers
description: Nginx reverse proxy for Proxmox-hosted web services
critical: true

# ─── target_ref → L4 LXC (already correct in current model) ───
runtime:
  type: lxc
  target_ref: lxc-nginx-proxy            # → L4
  network_binding_ref: inst.vlan.servers

features:
  - TLS termination (Let's Encrypt via certbot)
  - Reverse proxy for Grafana, Nextcloud, Gitea, Prometheus
  - HTTP/2 support
  - Rate limiting
  - WebSocket proxy

upstreams:
  - name: grafana
    service_ref: svc-grafana@lxc.lxc-grafana
    backend: "10.0.30.60:3000"
    path_prefix: /grafana/
  - name: nextcloud
    service_ref: svc-nextcloud@lxc.lxc-nextcloud
    backend: "10.0.30.30:80"
    path_prefix: /
    subdomain: cloud.home.local
  - name: gitea
    service_ref: svc-gitea@lxc.lxc-gitea
    backend: "10.0.30.40:3000"
    path_prefix: /gitea/
  - name: prometheus
    service_ref: svc-prometheus@lxc.lxc-prometheus
    backend: "10.0.30.70:9090"
    path_prefix: /prometheus/

security:
  ssl_certificate: letsencrypt
  https_redirect: true
  hsts: true
  allowed_from:
    - inst.vlan.servers
    - inst.vlan.lan

data_asset_refs:
  - inst.data_asset.nginx_proxy_config
```

### 8B.4 Variant B: Nginx as Docker Container in LXC-Docker

This pattern uses the **Docker-in-LXC** approach: an LXC container
(`lxc-docker`, vmid 208) runs Docker Engine, and nginx runs as a
Docker container inside it. This is the new ADR 0087 pattern with
a **nested L4 entity** referencing another L4 entity.

#### L4 Host: LXC-Docker Container (enriched)

```yaml
# projects/home-lab/topology/instances/L4-platform/lxc/srv-gamayun/lxc-docker.yaml
# ─── ENRICHED for Docker-in-LXC pattern ───
instance: lxc-docker
object_ref: obj.proxmox.lxc.debian12.docker
group: lxc
layer: L4
version: 2.0.0
source_id: lxc-docker
status: mapped
notes: >
  Docker Engine host running as privileged Proxmox LXC container.
  Hosts Docker containers for services that benefit from OCI image model.

vmid: 208
hostname: docker-host
description: Docker container host (Docker-in-LXC)
tags:
  - docker
  - production

host_ref: srv-gamayun

os_refs:
  - inst.os.debian.12.proxmox.lxc

resource_profile:
  cpu_cores: 2
  memory_mb: 1024
  memory_limit_mb: 2048
  swap_mb: 512

boot:
  onboot: true
  startup_order: 25

storage:
  rootfs:
    pool_ref: inst.storage.pool.local_lvm
    size_gb: 20
    format: raw
    role: rootfs
  volumes:
    - name: docker-data
      mount_path: /var/lib/docker
      pool_ref: inst.storage.pool.local_lvm
      size_gb: 50
      format: raw
      role: data
      data_asset_ref: null               # Docker runtime data, not governed

network:
  interface: eth0
  bridge_ref: inst.bridge.vmbr0
  vlan_ref: inst.vlan.servers
  ip: 10.0.30.90/24
  gateway: 10.0.30.1
  firewall: false

platform_config:
  proxmox:
    arch: amd64
    ostype: debian
    unprivileged: false                  # Docker requires privileged LXC!
    features:
      - nesting=1                        # required for Docker-in-LXC
      - keyctl=1                         # required for Docker overlay2
    terraform_resource: proxmox_virtual_environment_container
    terraform_provider: bpg/proxmox

# ─── Nested topology scope (ADR 0087 §3) ───
topology_scope: scope.lxc-docker
  network:
    internal_networks:
      - name: docker0
        subnet: 172.17.0.0/16
        driver: bridge
      - name: web-services
        subnet: 172.20.0.0/16
        driver: bridge

  storage:
    volumes:
      - name: docker-data
        mount_point: /var/lib/docker

# ─── Runtime capability declaration (this LXC CAN host Docker) ───
runtime_capabilities:
  - capability: cap.compute.runtime.container_host
    engine: docker-ce
    engine_version: "27.5"
    socket: /var/run/docker.sock
    storage_driver: overlay2
    supported_architectures: [amd64]
    max_containers: 15
  - capability: vendor.runtime.docker.host
    engine: docker-ce
    engine_version: "27.5"
    socket: /var/run/docker.sock
    storage_driver: overlay2
    supported_architectures: [amd64]
    max_containers: 15

trust_zone_ref: inst.trust_zone.servers

dns:
  nameserver: 192.168.88.1
  searchdomain: home.local

cloudinit:
  enabled: true
  user: root

ansible:
  enabled: true
  playbook: docker.yml
```

#### L4 Nested: Docker Container Nginx (inside LXC-Docker)

```yaml
# projects/home-lab/topology/instances/L4-platform/docker/lxc-docker/docker-nginx-proxy.yaml
instance: docker-nginx-proxy
object_ref: obj.docker.container.nginx         # same object as MikroTik variant
group: containers
layer: L4
version: 1.0.0
source_id: docker-nginx-proxy
status: planned
notes: >
  Nginx reverse proxy running as Docker container inside lxc-docker (vmid 208).
  Alternative to native LXC nginx (lxc-nginx-proxy vmid 207).
  Demonstrates Docker-in-LXC nesting pattern.

# ─── Host binding → L4 LXC (not L1 directly!) ───
host_ref: lxc-docker                          # ← L4 nesting!

# ─── OCI image ───
image:
  registry: docker.io
  repository: library/nginx
  tag: "1.27-alpine"
  platform: linux/amd64                       # Proxmox = x86_64

# ─── Resource profile ───
resource_profile:
  cpu_cores: 1                                # Docker CPU limit
  memory_mb: 128
  memory_limit_mb: 256

# ─── Network (Docker bridge) ───
network:
  mode: bridge
  docker_network: scope.lxc-docker.net.web-services  # ← scope reference!
  ip_address: 172.20.0.10
  # External access via Docker port mapping on lxc-docker host:
  # lxc-docker (10.0.30.90) port 80 → docker-nginx-proxy port 80
  external_ip: 10.0.30.90                    # for L5 service binding

# ─── Ports (standard Docker -p mapping) ───
ports:
  - host_port: 80
    container_port: 80
    protocol: tcp
    description: HTTP reverse proxy
  - host_port: 443
    container_port: 443
    protocol: tcp
    description: HTTPS reverse proxy

# ─── Environment ───
environment:
  TZ: "Europe/Moscow"
  NGINX_WORKER_PROCESSES: "auto"             # x86_64, more cores available

# ─── Volumes (Docker volumes + bind mounts) ───
storage:
  volumes:
    - name: nginx-config
      type: bind
      source: /opt/nginx/nginx.conf          # host path inside lxc-docker
      target: /etc/nginx/nginx.conf
      readonly: true
    - name: nginx-conf-d
      type: bind
      source: /opt/nginx/conf.d
      target: /etc/nginx/conf.d
      readonly: true
    - name: nginx-certs
      type: bind
      source: /opt/nginx/certs
      target: /etc/nginx/certs
      readonly: true
    - name: nginx-logs
      type: volume
      source: nginx-logs                     # Docker named volume
      target: /var/log/nginx
      readonly: false
  data_asset_refs:
    - inst.data_asset.nginx_docker_config

# ─── Lifecycle ───
restart_policy: unless-stopped

healthcheck:
  test: "curl -sf http://127.0.0.1/health || exit 1"
  interval: "15s"
  timeout: "5s"
  retries: 3

# ─── Compose group (optional) ───
compose_group: web-proxy                     # docker-compose stack name

depends_on: []
```

#### L3: Data Asset for Docker Nginx Config

```yaml
# projects/home-lab/topology/instances/L3-data/data-assets/inst.data_asset.nginx_docker_config.yaml
instance: inst.data_asset.nginx_docker_config
object_ref: obj.storage.data_asset.config
group: data-assets
layer: L3
version: 1.0.0
source_id: data-nginx-docker-config
status: planned
notes: Nginx Docker config stored on lxc-docker filesystem

host_ref: srv-gamayun                        # physical host
container_ref: lxc-docker                    # logical host (LXC)
criticality: high
backup_policy: daily

properties:
  storage_path: /var/lib/vz/lxc/208/rootfs/opt/nginx
  content_type: configuration
  includes:
    - nginx.conf
    - conf.d/*.conf
    - certs/*.pem
```

#### L5: Service (references Docker L4)

```yaml
# projects/home-lab/topology/instances/L5-application/services/lxc-docker/svc-nginx-proxy-docker.yaml
instance: svc-nginx-proxy-docker
object_ref: obj.service.nginx_proxy
group: services
layer: L5
version: 1.0.0
source_id: svc-nginx-proxy-docker
status: planned
notes: >
  Nginx reverse proxy running as Docker container in lxc-docker.
  Variant B — for comparison with native LXC (svc-nginx-proxy).

ports:
  http: 80
  https: 443
protocol: http
trust_zone_ref: inst.trust_zone.servers
description: Nginx reverse proxy (Docker-in-LXC variant)
critical: true

# ─── target_ref → L4 Docker container (not L1, not LXC directly) ───
runtime:
  type: docker
  target_ref: docker-nginx-proxy         # ← L4 Docker entity
  network_binding_ref: inst.vlan.servers

features:
  - TLS termination (Let's Encrypt via certbot-docker)
  - Reverse proxy for Grafana, Nextcloud, Gitea, Prometheus
  - HTTP/2 support
  - Auto-reload on config change (inotify)

upstreams:
  - name: grafana
    service_ref: svc-grafana@lxc.lxc-grafana
    backend: "10.0.30.60:3000"
    path_prefix: /grafana/
  - name: nextcloud
    service_ref: svc-nextcloud@lxc.lxc-nextcloud
    backend: "10.0.30.30:80"
    subdomain: cloud.home.local
  - name: gitea
    service_ref: svc-gitea@lxc.lxc-gitea
    backend: "10.0.30.40:3000"
    path_prefix: /gitea/

security:
  ssl_certificate: letsencrypt
  https_redirect: true
  hsts: true

data_asset_refs:
  - inst.data_asset.nginx_docker_config
```

### 8B.5 Cross-Layer Reference Graphs

#### Variant A: Native LXC

```
L7 backup-nginx-proxy-config
  ├─ data_asset_ref ──→ L3 inst.data_asset.nginx_proxy_config
  └─ target_ref ──→ L1 srv-gamayun

L6 health-lxc-nginx-proxy
  └─ target_ref ──→ L4 lxc-nginx-proxy

L5 svc-nginx-proxy
  ├─ runtime.target_ref ──→ L4 lxc-nginx-proxy
  └─ data_asset_refs ──→ L3 inst.data_asset.nginx_proxy_config

L4 lxc-nginx-proxy (vmid 207)
  ├─ host_ref ──→ L1 srv-gamayun
  │     └─ runtime_capabilities: cap.compute.runtime.container_host (proxmox-lxc 9.0)
  │     └─ class_ref: class.compute.hypervisor.proxmox ← vm_constraints
  ├─ network.bridge_ref ──→ L2 inst.bridge.vmbr0
  ├─ network.vlan_ref ──→ L2 inst.vlan.servers
  ├─ storage.rootfs.pool_ref ──→ L3 inst.storage.pool.local_lvm
  │     └─ format: raw (validated: raw ∈ lvmthin.supported_formats ✓)
  │     └─ role: rootfs
  └─ data_asset_refs ──→ L3 inst.data_asset.nginx_proxy_config
       └─ criticality: high, backup_policy: daily

L3 inst.storage.pool.local_lvm
  └─ host_ref ──→ L1 srv-gamayun (SSD, lvmthin, 150GB)

L1 srv-gamayun
  └─ class.compute.hypervisor.proxmox (QEMU/KVM + LXC)
```

#### Variant B: Docker-in-LXC (2-level nesting)

```
L5 svc-nginx-proxy-docker
  ├─ runtime.target_ref ──→ L4 docker-nginx-proxy
  └─ data_asset_refs ──→ L3 inst.data_asset.nginx_docker_config

L4 docker-nginx-proxy (Docker container)
  ├─ host_ref ──→ L4 lxc-docker (vmid 208)         ← NESTING!
  │     └─ runtime_capabilities: cap.compute.runtime.container_host + vendor.runtime.docker.host
  │     └─ topology_scope: scope.lxc-docker
  ├─ network.docker_network ──→ scope.lxc-docker.net.web-services (172.20.0.0/16)
  ├─ storage.data_asset_refs ──→ L3 inst.data_asset.nginx_docker_config
  └─ image: docker.io/library/nginx:1.27-alpine (linux/amd64)

L4 lxc-docker (vmid 208, LXC container)
  ├─ host_ref ──→ L1 srv-gamayun
  │     └─ runtime_capabilities: cap.compute.runtime.container_host
  ├─ network.bridge_ref ──→ L2 inst.bridge.vmbr0
  ├─ network.vlan_ref ──→ L2 inst.vlan.servers
  ├─ storage.rootfs.pool_ref ──→ L3 inst.storage.pool.local_lvm (raw)
  ├─ storage.volumes[docker-data].pool_ref ──→ L3 inst.storage.pool.local_lvm
  └─ platform_config.proxmox: unprivileged=false, nesting=1, keyctl=1

L3 inst.storage.pool.local_lvm
  └─ host_ref ──→ L1 srv-gamayun

L1 srv-gamayun
  └─ class.compute.hypervisor.proxmox
```

### 8B.6 Variant Comparison: LXC Native vs Docker-in-LXC

| Aspect | Variant A: Native LXC | Variant B: Docker-in-LXC |
|--------|----------------------|--------------------------|
| L4 entity | `lxc-nginx-proxy` (vmid 207) | `docker-nginx-proxy` inside `lxc-docker` (vmid 208) |
| Host chain | L4 → L1 (single hop) | L4 → L4 → L1 (2-level nesting) |
| OS | Full Debian 12 (apt, systemd) | Alpine minimal (no init, no apt) |
| RAM overhead | ~150MB (OS + nginx) | ~30MB (nginx only) + LXC-Docker shared |
| Config management | Ansible playbook | Dockerfile / bind mounts |
| Update model | `apt upgrade nginx` | `docker pull nginx:1.27-alpine` + restart |
| TLS certs | certbot on host | certbot-docker sidecar or bind mount |
| Storage format | raw (lvmthin rootfs) | raw (lvmthin LXC rootfs) + overlay2 (Docker) |
| Terraform resource | `proxmox_virtual_environment_container` | `proxmox_virtual_environment_container` (LXC) + docker-compose |
| Isolation | LXC namespace (good) | LXC + Docker namespace (better) |
| Portability | Proxmox-specific | Any Docker host (portable) |
| Best for | Long-lived, Ansible-managed services | Ephemeral, image-versioned microservices |

### 8B.7 Generated Terraform (Variant A — LXC)

```hcl
resource "proxmox_virtual_environment_container" "lxc_nginx_proxy" {
  node_name   = "srv-gamayun"
  vm_id       = 207
  description = "Nginx reverse proxy"
  tags        = ["proxy", "production"]

  started     = true
  start_on_boot = true
  startup {
    order = 15
  }

  unprivileged = true

  operating_system {
    template_file_id = "local:vztmpl/debian-12-standard_12.7-1_amd64.tar.zst"
    type             = "debian"
  }

  cpu {
    cores = 1
  }

  memory {
    dedicated = 256
    swap      = 256
  }

  disk {
    datastore_id = "local-lvm"
    size         = 4
  }

  network_interface {
    name     = "eth0"
    bridge   = "vmbr0"
    vlan_id  = 30
    ip_config {
      ipv4 {
        address = "10.0.30.80/24"
        gateway = "10.0.30.1"
      }
    }
  }

  initialization {
    dns {
      servers = ["192.168.88.1"]
      domain  = "home.local"
    }
    user_account {
      keys = [var.ssh_public_key]
    }
  }
}
```

### 8B.8 Cross-Reference: MikroTik vs Proxmox Deployment

| Dimension | MikroTik (§8A) | Proxmox Variant A | Proxmox Variant B |
|-----------|----------------|-------------------|--------------------|
| L1 host | rtr-mikrotik-chateau | srv-gamayun | srv-gamayun |
| L1 class | class.router | class.compute.hypervisor.proxmox | class.compute.hypervisor.proxmox |
| Runtime | containerD (RouterOS) | proxmox-lxc | proxmox-lxc + docker-ce |
| L4 class | class.compute.workload.docker | class.compute.workload.lxc | class.compute.workload.docker |
| Architecture | arm64 | amd64 | amd64 |
| Port mapping | DST-NAT firewall rules | Direct (container has own IP) | Docker -p (inside LXC) |
| Storage | USB bind mounts | lvmthin raw rootfs | lvmthin + overlay2 |
| Provisioning | Terraform (routeros provider) | Terraform (bpg/proxmox) + Ansible | Terraform + docker-compose |
| L5 pattern | svc → L4 Docker | svc → L4 LXC | svc → L4 Docker → L4 LXC |
| Nesting depth | 1 (L1 → L4) | 1 (L1 → L4) | 2 (L1 → L4 → L4) |

This comparison demonstrates that the **same L5 service contract** (`obj.service.nginx_proxy`)
can be deployed on fundamentally different infrastructure through different L4 workload
types, while the ontology maintains uniform cross-layer references.

---

## 9. SCALING STRATEGY

### 9.1 Why Topology Explodes

Adding one Docker service currently requires:
- 0 L4 entities (Docker skips L4)
- 1 L5 service file

Under new ontology, adding one Docker service requires:
- 1 L4 Docker container instance
- 1 L5 service instance (unchanged)

Adding one VM requires:
- 1+ L3 volume instances (boot disk, data disks)
- 1 L4 VM instance
- 1 L5 service instance

But thanks to **class defaults + object templates + merge inheritance**:
- Most properties come from class defaults (restart_policy, healthcheck interval)
- Image/disk format come from object template
- Instance only overrides: host_ref, specific ports/environment, disk sizes

### 9.2 Minimal Instance Examples

```yaml
# Docker container — ~5 lines
instance: docker-grafana
object_ref: obj.docker.container.grafana
host_ref: srv-orangepi5
environment:
  GF_SECURITY_ADMIN_PASSWORD_REF: secrets.grafana.admin_password
```

```yaml
# Proxmox VM — ~12 lines (disks need explicit volume_ref)
instance: vm-k3s-master
object_ref: obj.proxmox.vm.debian12.cloud-init
host_ref: srv-gamayun
resource_profile: { cpu_cores: 2, memory_mb: 4096 }
disks:
  - role: boot
    volume_ref: inst.vol.vm-k3s.boot
    bus: scsi
    slot: scsi0
    bootable: true
  - role: data
    volume_ref: inst.vol.vm-k3s.data
    bus: scsi
    slot: scsi1
cloud_init: { enabled: true }
```

### 9.3 Batch Grouping + Host Sharding

Multiple instances per file when they belong to a logical group:

```
projects/home-lab/topology/instances/
  L3-data/
    pools/                       ← existing
    data-assets/                 ← existing
    volumes/                     ← NEW: VM disk volumes
      vol.vm-k3s-master.yaml
      vol.vm-dev.yaml
  L4-platform/
    lxc/
      srv-gamayun/               ← host shard
        lxc-postgresql.yaml
        lxc-grafana.yaml
      rtr-mikrotik-chateau/      ← host shard (if LXC used)
        lxc-*.yaml
    vm/
      srv-gamayun/               ← host shard
        vm-k3s-master.yaml
    docker/
      srv-orangepi5/             ← host shard
        docker-grafana.yaml
        docker-homeassistant.yaml
      rtr-mikrotik-chateau/      ← host shard
        docker-adguard.yaml
        docker-mosquitto.yaml
      lxc-docker/                ← nested runtime host shard
        docker-*.yaml
  L5-application/
    services/
      srv-gamayun/
        svc-grafana@lxc.lxc-grafana.yaml
      srv-orangepi5/
        svc-grafana@docker.srv-orangepi5.yaml
      rtr-mikrotik-chateau/
        svc-adguard.yaml
```

Sharding policy:
- L4 path format: `L4-platform/<workload-kind>/<host-shard>/<instance>.yaml`
- L5 path format: `L5-application/services/<host-shard>/<service>.yaml`
- `host-shard` must match L4 `host_ref` (or L4 runtime host) and L5 runtime target host.
- Flat legacy paths are transition-only and should emit warnings until cutover.

For existing project constraints (group directory remains required by compiler),
L4 uses group-compatible host sharding in migration phase:
- `L4-platform/lxc/<host-shard>/<instance>.yaml`
- `L4-platform/docker/<host-shard>/<instance>.yaml`
- `L4-platform/vm/<host-shard>/<instance>.yaml` (canonical)
- `L4-platform/vms/<host-shard>/<instance>.yaml` (legacy alias during transition)

### 9.4 File Count Projection

| Layer | Current | + Docker (Ph1) | + VMs (Ph2) | + L3 Volumes |
|-------|---------|---------------|-------------|--------------|
| L3 instances | 19 | 19 | 19 + ~6 vol = 25 | ~25 |
| L4 instances | 9 | 9 + ~12 docker = 21 | + ~3 VM = 24 | 24 |
| L5 instances | 35 | 35 (unchanged) | 35 | 35 |
| **Total delta** | **63** | **+12** | **+9** | **+6** |

Growth is linear and manageable (~30% increase); host sharding keeps per-directory
cognitive load bounded as topology grows.

> **Errata alignment note**: This section uses the canonical phase map from
> ADR 0087 / IMPLEMENTATION-PLAN (Phase 5 = Nested Topology, Phase 6 = Stacks).

---

## 10. IMPLEMENTATION PHASES

### Phase 1: Docker Promotion (MVP)

1. Create `class.compute.workload.lxc` (rename from `container`)
2. Create `class.compute.workload.docker`
3. Add Docker container objects (`obj.docker.container.*`)
4. Add Docker container instances to L4
5. Update L5 service `target_ref` to point at L4 Docker containers
6. Ensure Docker hosts expose `cap.compute.runtime.container_host` and `vendor.runtime.docker.host`
7. Add validator: Docker containers require host with both capabilities

### Phase 2: Multi-Hypervisor VM Support

1. Create `class.compute.workload.vm` (single VM class, hypervisor-agnostic)
2. Define platform constraints in `class.compute.hypervisor.{proxmox,vbox,hyperv,vmware,xen}`
3. Add VM objects per platform (`obj.<platform>.vm.<os>.<profile>`) with `platform_config` bag
4. Add VM instances to L4 (when hardware/use-case demands)
5. Validate `vm.platform_config` against host hypervisor `platform_config_schema`

### Phase 3: L3 Storage Integration

1. Extend `class.storage.volume` with `format`, `bus_attachment`, `role`, `data_asset_ref`
2. Add L3 volume objects for VM disks (`obj.storage.volume.vm_disk`)
3. Add L3 volume instances for each VM disk
4. Backfill `data_asset_ref` on existing L4 LXC volumes
5. Add validators: format↔pool, format↔hypervisor, boot disk presence, bus↔hypervisor

### Phase 5: Nested Topology (Optional)

1. Implement `topology_scope` mechanism
2. Add `internal_networks` to container scope
3. Generate docker-compose.yaml from Docker container groups + internal networks

### Phase 6: Stack Objects (Optional)

1. Create `class.compute.workload.docker.stack`
2. Stack objects → docker-compose.yaml generators
3. Stack-level healthchecks and lifecycle management

---

## 11. BACKWARD COMPATIBILITY

| Change | Impact | Migration |
|--------|--------|-----------|
| Rename `class.compute.workload.container` → `.lxc` | All LXC instances | Global search-replace `class_ref` |
| New Docker L4 instances | L5 Docker services | Update `target_ref` from L1 → L4 |
| New `host_ref` validation | Existing containers | Already valid (all reference L1 hosts) |
| Docker runtime capability contract | Docker hosts | Ensure `cap.compute.runtime.container_host` + `vendor.runtime.docker.host` |
| `class.storage.volume` new fields | L3 volumes | Optional fields, backward compat |
| `data_asset_ref` on L4 volumes | L4 LXC instances | Optional backfill, not required |
| Multi-hypervisor VM classes | New only | No impact on existing entities |
| `topology_scope` (Phase 5) | None initially | Opt-in, no existing files affected |

**Compatibility-first migration**: changes are implemented with transition aliases
and warning-only validators before hard enforcement. Existing topology remains
valid during transition, then deprecated patterns are removed at cutover gate.
