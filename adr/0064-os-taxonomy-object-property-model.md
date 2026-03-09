# ADR 0064: Software Stack Taxonomy - Firmware and OS as Separate Entities

**Date:** 2026-03-08
**Status:** Implemented - Two-Entity Model (Firmware + OS)
**Extends:** ADR 0062 (Topology v5 - Modular Class-Object-Instance Architecture)
**Replaces:** Previous property-based OS model
**Analysis:** See `adr/0064-analysis/` for detailed decision rationale

---

## Context

The v5 model uses `Class -> Object -> Instance` and a capability contract (ADR 0062).
Device software stack must be modeled as two distinct layers:

1. **Firmware** (low-level): vendor/hardware-bound software foundation
2. **OS** (high-level): operating system layer that provides runtime environment

### Core Insight: Firmware and OS Are Different Entities

**Firmware** is the foundational software layer:
- Always hardware-specific (vendor firmware)
- Required for device to function
- Examples: BIOS/UEFI (PC), Apple Silicon firmware, MikroTik router firmware, PDU management firmware

**OS** is the higher-level management layer:
- May be embedded in firmware (MikroTik RouterOS)
- May be installable/replaceable (PC: Linux/Windows)
- May be absent (PDU with firmware-only management)
- **Cannot exist without firmware**

### Problem With Previous Single-Entity Model

Previous approach conflated firmware and OS:
- RouterOS firmware treated as "OS" (missing firmware layer)
- PC BIOS not modeled (OS-only binding)
- PDU firmware not distinguished from "OS-less"
- Embedded vs installable OS not structurally different

### Decision: Two First-Class Entities

Software stack is now modeled as:
- `class.firmware` -> `obj.firmware.mikrotik-routeros7` -> `inst.firmware.routeros-7-1`
- `class.os` -> `obj.os.routeros-7` -> `inst.os.routeros-7-prod`
- Devices reference firmware/OS **instances** via `firmware_ref` and `os_refs`
- OS types: `embedded` (part of firmware stack) or `installable` (independent)

---

## Decision

### 0. Canonical Layer Semantics: Class -> Object -> Instance

**All entities** (firmware, OS, devices) follow the same model:

1. **Class** defines contract and constraints (schema, properties, capabilities).
2. **Object** defines a concrete profile/variant on top of class contract.
3. **Instance** defines a deployed/active version of an object profile.
4. One object MAY have many instances in the same system.

**Canonical naming format:**

```yaml
# Class definition (versioned)
class: class.<domain>.<name>
version: <semver>

# Object definition
object: obj.<domain>.<name>
class_ref: class.<domain>.<name>

# Instance definition
instance: inst.<domain>.<name>
object_ref: obj.<domain>.<name>
```

**Version compatibility:**
- Classes declare `version: <semver>` as separate field
- References (`class_ref`, `object_ref`) do NOT include version
- Compiler validates version compatibility during resolution
- Breaking changes require major version bump

**Example hierarchy:**

```
class.firmware (v1.0.0)
  +-- obj.firmware.routeros-7
  |     +-- inst.firmware.routeros-7-prod
  |     +-- inst.firmware.routeros-7-staging
  +-- obj.firmware.generic-uefi-x86
        +-- inst.firmware.uefi-2.8

class.os (v1.0.0)
  +-- obj.os.debian-12
  |     +-- inst.os.debian-12-prod
  |     +-- inst.os.debian-12-staging
  +-- obj.os.windows-11
        +-- inst.os.windows-11-enterprise

class.compute (v1.0.0)
  +-- obj.compute.pc
  |     +-- inst.compute.pc-workstation-01
  |     +-- inst.compute.pc-workstation-02
  +-- obj.compute.orange-pi-5
        +-- inst.compute.sbc-orangepi-01
```

### Entity Categories

Classes include a `categories` field for taxonomic classification:

**Purpose:**
- **Taxonomic clarity** - Categorize entities by role and nature
- **Query support** - Enable filtering (e.g., "all infrastructure entities")
- **Documentation** - Auto-generate entity taxonomies
- **Validation** - Enforce category constraints

**Standard categories:**

| Category | Meaning | Examples |
|----------|---------|----------|
| `infrastructure` | Core infrastructure component | firmware, os, compute |
| `prerequisite` | Required before other entities | firmware (before OS), os (before services) |
| `runtime` | Provides execution environment | os, container runtime |
| `hardware-bound` | Tied to physical/virtual hardware | firmware |
| `virtual` | Virtual/software entity | VM firmware, virtual networks |
| `host` | Hosts other entities | compute devices, hypervisors |

**Relationship to capabilities:**
- **Categories** answer "WHAT IS THIS?" (taxonomic)
- **Capabilities** answer "WHAT CAN IT DO?" (functional)

Example:
```yaml
# Categories: infrastructure, prerequisite, hardware-bound
# Capabilities: cap.firmware.mikrotik, cap.firmware.routeros, cap.firmware.arch.x86_64
```

### 1. Firmware Is a First-Class Entity (Always Required for Active Devices)

```yaml
# Class definition
class: class.firmware
version: 1.0.0
categories: [infrastructure, prerequisite, hardware-bound]

properties:
  # Identification (required)
  vendor: mikrotik | apple | generic | apc | cisco | ubiquiti
  family: routeros | apple_silicon | bios | uefi | uboot | proprietary
  version: string
  architecture: x86_64 | arm64 | mips | armhf

  # Boot and runtime
  boot_stack: bios | uefi | uboot | proprietary | none
  management_interface: cli | web | snmp | proprietary | none

  # Hardware binding
  hardware_locked: boolean
  vendor_locked: boolean
  
  # Virtualization (optional)
  virtual: boolean  # true for virtual firmware (VMs)

  # Lifecycle
  release_date: ISO8601
  eol_date: ISO8601

capabilities:
  dynamic:
    - cap.firmware.{vendor}
    - cap.firmware.{family}
    - cap.firmware.{vendor}.{family}.{version_normalized}
    - cap.firmware.arch.{architecture}
    - cap.firmware.boot.{boot_stack}
  conditional:
    - cap.firmware.virtual (if virtual == true)
```

**Categories explained:**
- `infrastructure` - Core infrastructure component required for system operation
- `prerequisite` - Must exist before OS/workloads can run
- `hardware-bound` - Tied to physical or virtual hardware platform

**Firmware object examples:**

```yaml
# MikroTik RouterOS firmware
object: obj.firmware.mikrotik-routeros7
class_ref: class.firmware

properties:
  vendor: mikrotik
  family: routeros
  version: "7.13"
  architecture: arm64
  boot_stack: proprietary
  management_interface: web
  hardware_locked: true
  vendor_locked: true

# Derived capabilities:
# - cap.firmware.mikrotik
# - cap.firmware.routeros
# - cap.firmware.mikrotik.routeros.7
# - cap.firmware.arch.arm64
```

```yaml
# Generic UEFI firmware
object: obj.firmware.generic-uefi-x86
class_ref: class.firmware

properties:
  vendor: generic
  family: uefi
  version: "2.8"
  architecture: x86_64
  boot_stack: uefi
  hardware_locked: false
  vendor_locked: false

# Derived capabilities:
# - cap.firmware.generic
# - cap.firmware.uefi
# - cap.firmware.arch.x86_64
# - cap.firmware.boot.uefi
```

```yaml
# U-Boot for ARM64 SBC
object: obj.firmware.generic-arm64-uboot
class_ref: class.firmware

properties:
  vendor: generic
  family: uboot
  version: "2023.07"
  architecture: arm64
  boot_stack: uboot
  management_interface: none
  hardware_locked: false
  vendor_locked: false

# Derived capabilities:
# - cap.firmware.generic
# - cap.firmware.uboot
# - cap.firmware.arch.arm64
# - cap.firmware.boot.uboot
```

```yaml
# PDU management firmware
object: obj.firmware.apc-pdu-mgmt
class_ref: class.firmware

properties:
  vendor: apc
  family: proprietary
  version: "3.9.2"
  architecture: armhf
  boot_stack: none
  management_interface: snmp
  hardware_locked: true
  vendor_locked: true

# Derived capabilities:
# - cap.firmware.apc
# - cap.firmware.proprietary
# - cap.firmware.arch.armhf
```

**Virtual firmware (for VMs):**

```yaml
# KVM virtual BIOS
object: obj.firmware.kvm-bios
class_ref: class.firmware

properties:
  vendor: qemu
  family: bios
  version: "seabios-1.16.0"
  architecture: x86_64
  boot_stack: bios
  hardware_locked: false
  vendor_locked: false
  virtual: true  # Indicates virtual firmware

# Derived capabilities:
# - cap.firmware.qemu
# - cap.firmware.bios
# - cap.firmware.virtual
# - cap.firmware.arch.x86_64
```

```yaml
# KVM OVMF (UEFI for VMs)
object: obj.firmware.kvm-ovmf
class_ref: class.firmware

properties:
  vendor: qemu
  family: uefi
  version: "edk2-20231129"
  architecture: x86_64
  boot_stack: uefi
  hardware_locked: false
  vendor_locked: false
  virtual: true
  secure_boot_capable: true

# Derived capabilities:
# - cap.firmware.qemu
# - cap.firmware.uefi
# - cap.firmware.virtual
# - cap.firmware.secureboot
# - cap.firmware.arch.x86_64
```

```yaml
# VMware virtual firmware
object: obj.firmware.vmware-efi
class_ref: class.firmware

properties:
  vendor: vmware
  family: uefi
  version: "efi-2.7"
  architecture: x86_64
  boot_stack: uefi
  hardware_locked: true
  vendor_locked: true
  virtual: true

# Derived capabilities:
# - cap.firmware.vmware
# - cap.firmware.uefi
# - cap.firmware.virtual
# - cap.firmware.arch.x86_64
```

**Firmware instance examples:**

```yaml
instance: inst.firmware.routeros-7-13-arm64
object_ref: obj.firmware.mikrotik-routeros7

deployment:
  installed_date: "2024-01-15"
  patch_level: "7.13.5"
```

```yaml
instance: inst.firmware.generic-uefi-2.8
object_ref: obj.firmware.generic-uefi-x86

deployment:
  installed_date: "2023-10-01"
```

### 2. OS Is a First-Class Entity (Conditionally Required)

```yaml
# Class definition
class: class.os
version: 1.0.0
categories: [infrastructure, prerequisite, runtime]

properties:
  # Identification (required)
  family: linux | bsd | windows | macos | routeros | proprietary
  distribution: debian | ubuntu | alpine | fedora | routeros | macos | windows
  release: string
  release_id: string  # normalized for capability IDs
  architecture: x86_64 | arm64 | armhf | riscv64 | mips

  # Runtime characteristics
  codename: string
  init_system: systemd | openrc | sysvinit | busybox | launchd | proprietary
  package_manager: apt | apk | dnf | nix | brew | none
  kernel: linux | darwin | nt | bsd | proprietary

  # Installation model (CRITICAL)
  installation_model: embedded | installable

  # Embedded-specific
  embedded_in_firmware: boolean
  independently_updatable: boolean

  # Installable-specific
  supports_multiboot: boolean
  base_image_format: qcow2 | ova | ami | iso | rootfs

  # Lifecycle
  eol_date: ISO8601

capabilities:
  dynamic:
    - cap.os.{family}
    - cap.os.{distribution}
    - cap.os.{distribution}.{release_id}
    - cap.os.{codename}
    - cap.os.init.{init_system}
    - cap.os.pkg.{package_manager}
    # NOTE: cap.arch.* is NOT derived from OS - firmware is source of truth
  conditional:
    - cap.os.embedded (if installation_model == embedded)
    - cap.os.installable (if installation_model == installable)

# OS.architecture is used for compatibility validation, not capability derivation
```

**Categories explained:**
- `infrastructure` - Core infrastructure component required for system operation
- `prerequisite` - Must exist before services/workloads can run
- `runtime` - Provides execution environment for applications and services

**OS object examples:**

```yaml
# RouterOS (embedded in firmware)
object: obj.os.routeros-7
class_ref: class.os

properties:
  family: routeros
  distribution: routeros
  release: "7"
  release_id: "7"
  architecture: arm64
  init_system: proprietary
  package_manager: none
  kernel: proprietary
  installation_model: embedded
  embedded_in_firmware: true
  independently_updatable: false

# Derived capabilities:
# - cap.os.routeros
# - cap.os.routeros.7
# - cap.os.embedded
# (cap.arch.* from firmware, not OS)
```

```yaml
# Debian 12 (installable)
object: obj.os.debian-12
class_ref: class.os

properties:
  family: linux
  distribution: debian
  release: "12"
  release_id: "12"
  codename: bookworm
  architecture: x86_64
  init_system: systemd
  package_manager: apt
  kernel: linux
  installation_model: installable
  supports_multiboot: true
  base_image_format: qcow2
  eol_date: "2028-06-30"

# Derived capabilities:
# - cap.os.linux
# - cap.os.debian
# - cap.os.debian.12
# - cap.os.bookworm
# - cap.os.init.systemd
# - cap.os.pkg.apt
# - cap.os.installable
```

```yaml
# Debian 12 ARM64 variant
object: obj.os.debian-12-arm64
class_ref: class.os

properties:
  family: linux
  distribution: debian
  release: "12"
  release_id: "12"
  codename: bookworm
  architecture: arm64
  init_system: systemd
  package_manager: apt
  kernel: linux
  installation_model: installable
  supports_multiboot: true
  base_image_format: rootfs
  eol_date: "2028-06-30"

# Derived capabilities:
# - cap.os.linux
# - cap.os.debian
# - cap.os.debian.12
# - cap.os.init.systemd
# - cap.os.pkg.apt
# - cap.os.installable
```

```yaml
# macOS (embedded, vendor-locked)
object: obj.os.macos-14
class_ref: class.os

properties:
  family: macos
  distribution: macos
  release: "14"
  release_id: "14"
  codename: sonoma
  architecture: arm64
  init_system: launchd
  package_manager: brew
  kernel: darwin
  installation_model: embedded
  embedded_in_firmware: true
  independently_updatable: true

# Derived capabilities:
# - cap.os.macos
# - cap.os.macos.14
# - cap.os.sonoma
# - cap.os.init.launchd
# - cap.os.pkg.brew
# - cap.os.embedded
```

```yaml
# Windows 11 (installable)
object: obj.os.windows-11
class_ref: class.os

properties:
  family: windows
  distribution: windows
  release: "11"
  release_id: "11"
  architecture: x86_64
  init_system: proprietary
  package_manager: none
  kernel: nt
  installation_model: installable
  supports_multiboot: true
  base_image_format: iso

# Derived capabilities:
# - cap.os.windows
# - cap.os.windows.11
# - cap.os.installable
```

**OS instance examples:**

```yaml
# Embedded OS - linked to firmware instance
instance: inst.os.routeros-7-prod
object_ref: obj.os.routeros-7
embedded_in: inst.firmware.routeros-7-13-arm64  # firmware-OS link

deployment:
  installed_date: "2024-02-01"
  patch_level: "7.13.5"
```

```yaml
# Installable OS - no firmware link (independent)
instance: inst.os.debian-12-prod
object_ref: obj.os.debian-12
# embedded_in: absent (installable OS)

deployment:
  installed_date: "2024-01-10"
  kernel_version: "6.1.0-17"
```

```yaml
instance: inst.os.debian-12-arm64-prod
object_ref: obj.os.debian-12-arm64

deployment:
  installed_date: "2024-03-01"
  kernel_version: "6.1.0-18"
```

### 3. Device Binding: Direct Instance References

Device instances reference **firmware instance** and **OS instances** directly using `firmware_ref` and `os_refs`.

**Class level** defines binding constraints (types and cardinalities):

```yaml
# Class definition
class: class.compute
version: 1.0.0

bindings:
  firmware:
    kind: single
    class_ref: class.firmware
    required: true
  os:
    kind: array
    class_ref: class.os
    min_items: 0
    max_items: 3

firmware_policy: required
os_policy: conditional  # depends on device type
```

**Object level** defines device profile and refines constraints:

```yaml
# PC object (supports multi-boot)
object: obj.compute.pc
class_ref: class.compute

os_constraints:
  installation_model: [installable]
  multi_boot: true
  min_items: 1
  max_items: 3
```

```yaml
# MacBook object (vendor-locked, no multi-boot)
object: obj.compute.macbook
class_ref: class.compute

os_constraints:
  installation_model: [embedded]
  allowed_distributions: [macos]
  multi_boot: false
  min_items: 1
  max_items: 1
```

```yaml
# Orange Pi 5 object (SBC, supports multi-boot)
object: obj.compute.orange-pi-5
class_ref: class.compute

os_constraints:
  installation_model: [installable]
  architecture: [arm64]
  multi_boot: true
  min_items: 1
  max_items: 2
```

```yaml
# MikroTik Chateau object (embedded OS)
object: obj.compute.mikrotik-chateau-lte7ax
class_ref: class.compute

os_constraints:
  installation_model: [embedded]
  multi_boot: false
  min_items: 1
  max_items: 1
```

```yaml
# PDU object (no OS)
object: obj.power.apc-pdu
class_ref: class.power

os_constraints:
  min_items: 0
  max_items: 0  # OS forbidden
```

**Instance level** specifies concrete firmware/OS instances:

```yaml
# PC single-boot
instance: inst.compute.pc-workstation-01
object_ref: obj.compute.pc

firmware_ref: inst.firmware.generic-uefi-2.8
os_refs: [inst.os.debian-12-prod]
```

```yaml
# PC dual-boot
instance: inst.compute.pc-workstation-02
object_ref: obj.compute.pc

firmware_ref: inst.firmware.generic-uefi-2.8
os_refs: [inst.os.windows-11-prod, inst.os.debian-12-prod]
```

```yaml
# KVM Virtual Machine
object: obj.compute.kvm-vm
class_ref: class.compute

os_constraints:
  installation_model: [installable]
  multi_boot: false  # VMs typically single-boot
  min_items: 1
  max_items: 1

# Instance
instance: inst.compute.vm-app-01
object_ref: obj.compute.kvm-vm

firmware_ref: inst.firmware.kvm-ovmf-prod
os_refs: [inst.os.debian-12-prod]
hypervisor_ref: inst.compute.kvm-host-01  # Reference to hypervisor host
```

```yaml
# VMware Virtual Machine
object: obj.compute.vmware-vm
class_ref: class.compute

os_constraints:
  installation_model: [installable]
  multi_boot: false
  min_items: 1
  max_items: 1

# Instance
instance: inst.compute.vm-win-01
object_ref: obj.compute.vmware-vm

firmware_ref: inst.firmware.vmware-efi-v2.7
os_refs: [inst.os.windows-server-2022]
hypervisor_ref: inst.compute.esxi-host-01
```

```yaml
# MacBook
instance: inst.compute.macbook-pro-01
object_ref: obj.compute.macbook

firmware_ref: inst.firmware.apple-m2-14.2
os_refs: [inst.os.macos-14-prod]
```

```yaml
# MikroTik Chateau LTE7ax
instance: inst.compute.edge-mikrotik-chateau-01
object_ref: obj.compute.mikrotik-chateau-lte7ax

firmware_ref: inst.firmware.routeros-7-13-arm64
os_refs: [inst.os.routeros-7-prod]
```

```yaml
# Orange Pi 5 dual-boot
instance: inst.compute.sbc-orangepi-02
object_ref: obj.compute.orange-pi-5

firmware_ref: inst.firmware.uboot-2023.07-arm64
os_refs: [inst.os.debian-12-arm64-prod, inst.os.ubuntu-2204-arm64-staging]
```

```yaml
# PDU (no OS)
instance: inst.power.pdu-rack-a-01
object_ref: obj.power.apc-pdu

firmware_ref: inst.firmware.apc-pdu-3.9.2
# os_refs: absent (forbidden by object constraints)
```

### 4. Effective Capability Derivation

Compiler derives device capabilities from firmware instance and all OS instances:

```yaml
# Device instance: pc-workstation-02 (dual-boot Windows + Linux)
instance: inst.compute.pc-workstation-02
object_ref: obj.compute.pc

firmware_ref: inst.firmware.generic-uefi-2.8
os_refs: [inst.os.windows-11-prod, inst.os.debian-12-prod]

# Compiler derives:
effective_capabilities:
  from_firmware:
    - cap.firmware.generic
    - cap.firmware.uefi
    - cap.firmware.boot.uefi
    - cap.arch.x86_64           # architecture from firmware only
  from_os[0]:  # Windows
    - cap.os.windows
    - cap.os.windows.11
    - cap.os.installable
  from_os[1]:  # Debian
    - cap.os.linux
    - cap.os.debian
    - cap.os.debian.12
    - cap.os.init.systemd
    - cap.os.pkg.apt
    - cap.os.installable
  combined:
    - all firmware capabilities (including cap.arch.*)
    - all OS capabilities from all os_refs (without cap.arch.*)

# This device can run services requiring Windows OR Linux
```

### 5. Service/Workload Requirements

Services declare requirements against firmware and OS capabilities:

```yaml
# Service: prometheus (requires Linux + systemd)
service: prometheus
requires:
  capabilities:
    all: [cap.os.linux, cap.os.init.systemd]
    any: [cap.os.debian, cap.os.ubuntu, cap.os.alpine]

# Validation against pc-workstation-02:
#   os_refs includes debian-12-production
#   has cap.os.linux (from Debian)
#   has cap.os.init.systemd (from Debian)
#   has cap.os.debian (from Debian)
# Result: COMPATIBLE (via Debian OS context)
```

```yaml
# Service: routeros-management-tool
service: routeros-mgmt
requires:
  capabilities:
    all: [cap.firmware.mikrotik, cap.os.routeros]

# Validation against edge-mikrotik-chateau-01:
#   has cap.firmware.mikrotik
#   has cap.os.routeros
# Result: COMPATIBLE

# Validation against pc-workstation-02:
#   missing cap.firmware.mikrotik
# Result: INCOMPATIBLE
```

### 6. Validation Rules

Compiler MUST enforce:

1. **Firmware reference validation:**
   - Every active device with `firmware_policy: required` MUST have `firmware_ref`
   - Referenced firmware instance MUST exist
   - Firmware instance's object MUST be `class: firmware`
   - Firmware architecture MUST match device object constraints

2. **OS reference validation:**
   - `os_refs` array length MUST satisfy `min_items` and `max_items`
   - If `min_items > 0`, device instance MUST have `os_refs`
   - If `max_items == 0`, device instance MUST NOT have `os_refs`
   - Each referenced OS instance MUST exist
   - Each OS instance's object MUST be `class: os`
   - OS `installation_model` MUST match device `os_constraints`

3. **Firmware-OS link (embedded_in):**
   - If OS object has `installation_model: embedded`, OS instance MUST have `embedded_in`
   - `embedded_in` MUST reference existing firmware instance
   - Referenced firmware instance MUST be same as device's `firmware_ref`
   - If OS object has `installation_model: installable`, `embedded_in` MUST be absent

4. **Architecture compatibility:**
   - Firmware `architecture` is the hardware architecture (source of truth)
   - OS `architecture` is the build target architecture
   - OS `architecture` MUST equal firmware `architecture`
   - All OS instances in `os_refs` MUST have same architecture as firmware
   - Capability `cap.arch.*` is derived from firmware architecture only (single source)

5. **Multi-boot validation:**
   - If `multi_boot: false`, `os_refs` MUST have exactly 1 item (when required)
   - If `multi_boot: true`, `os_refs` MAY have multiple items (up to `max_items`)
   - All OS instances MUST satisfy architecture compatibility (rule 4)

6. **Capability derivation:**
   - Derive capabilities from firmware instance's object properties
   - Derive capabilities from ALL OS instances' object properties
   - `cap.arch.*` derived from firmware only (not duplicated from OS)
   - Combine into device effective capability set

7. **Service-device matching:**
   - Service `requires.capabilities.all` -> device MUST have ALL listed
   - Service `requires.capabilities.any` -> device MUST have AT LEAST ONE
   - For multi-boot: service can be deployed to ANY compatible OS context

8. **Version compatibility:**
   - Object's `class_ref` resolved to class with matching version
   - Instance's `object_ref` resolved to object with compatible class version
   - Breaking class changes require major version bump
   - Compiler validates version compatibility during resolution phase

### 7. Inference Rules

When `init_system` or `package_manager` are omitted from OS object, compiler SHOULD infer by `distribution`:

| Distribution | init_system | package_manager |
|--------------|-------------|-----------------|
| debian | systemd | apt |
| ubuntu | systemd | apt |
| alpine | openrc | apk |
| fedora | systemd | dnf |
| nixos | systemd | nix |
| routeros | proprietary | none |
| macos | launchd | brew |
| windows | proprietary | none |

Explicit value in object overrides inference.

### 8. Real-World Examples Matrix

| Device Type | Firmware Instance | OS Instances | OS Model | Notes |
|-------------|-------------------|--------------|----------|-------|
| **PC Single-boot** | generic-uefi-2.8 | debian-12-prod | installable | User can change OS |
| **PC Dual-boot** | generic-uefi-2.8 | windows-11 + debian-12 | installable | Both Windows and Linux |
| **MacBook Pro** | apple-m2-14.2 | macos-14-prod | embedded | Vendor-locked, no dual-boot |
| **Orange Pi 5** | uboot-2023.07-arm64 | debian-12-arm64 | installable | ARM SBC, SD card |
| **Orange Pi 5 dual** | uboot-2023.07-arm64 | debian-12 + ubuntu-2204 | installable | Two ARM64 distros |
| **MikroTik Chateau** | routeros-7-13-arm64 | routeros-7-prod | embedded | Edge compute + routing |
| **PDU APC** | apc-pdu-3.9.2 | (none) | N/A | Firmware-only |
| **VM (KVM)** | kvm-ovmf-prod | debian-12-prod | installable | Virtual UEFI firmware |
| **VM (VMware)** | vmware-efi-v2.7 | windows-server-2022 | installable | VMware virtual firmware |
| **VM (Hyper-V)** | hyperv-gen2-uefi | ubuntu-22.04 | installable | Gen2 UEFI firmware |

**Virtualization notes:**
- VMs have virtual firmware (KVM OVMF, VMware EFI, Hyper-V Gen2)
- Virtual firmware provides same boot interface as physical
- OS in VM is identical to physical machine OS
- Each hypervisor has specific firmware objects
- LXC containers: not covered (no firmware, shared kernel) - see future ADR
- Docker containers: not covered (no OS layer) - see future ADR

### 9. Migration Contract: 5-Phase Transition

**Phase 1: Define firmware and OS classes**
- Define `class.firmware` with properties and capabilities
- Define `class.os` with properties and capabilities
- Create firmware objects for all active device types
- Create OS objects for all distributions in use
- No breaking changes (old model still works)

**Phase 2: Create firmware and OS instances**
- Create firmware instances for deployed versions
- Create OS instances for deployed versions
- Implement compiler capability derivation
- Devices can optionally use new model

**Phase 3: Device instance migration**
- Migrate device instances to use `firmware_ref` and `os_refs`
- Enable dual validation (both old and new models)
- Migration tooling: auto-convert old -> new format
- Migrate 50% of device instances

**Phase 4: Deprecation**
- Warn on old model usage
- Require new model for new device instances
- Migrate remaining 50%

**Phase 5: Cleanup**
- Hard error on old model
- Remove legacy code paths
- Final validation

**Risk:** LOW (reversible until Phase 4)

---

## Consequences

### Positive

1. **Firmware and OS are properly separated**
   - Firmware as foundational layer (always required for active devices)
   - OS as runtime layer (conditional, can be embedded or installable)
   - PDU firmware without OS is natural
   - PC BIOS/UEFI firmware is explicit

2. **Clear semantic distinction**
   - `class.firmware` -> `obj.firmware.mikrotik-routeros7` -> `inst.firmware.routeros-7-prod`
   - `class.os` -> `obj.os.debian-12` -> `inst.os.debian-12-prod`
   - MikroTik has both firmware AND embedded OS (two entities, linked)

3. **Instance references model**
   - Device instances reference firmware/OS instances directly
   - `firmware_ref: inst.firmware.generic-uefi-2.8`
   - `os_refs: [inst.os.debian-12-prod, inst.os.windows-11-prod]`
   - Clean references, no nested bindings

4. **Capabilities from both layers**
   - Firmware: `cap.firmware.mikrotik`, `cap.firmware.routeros`
   - OS: `cap.os.routeros.7`, `cap.os.embedded`
   - Services can require firmware-specific or OS-specific capabilities

5. **Multi-boot support**
   - `os_refs` array can contain multiple OS instances
   - PC: Windows + Linux dual-boot
   - Orange Pi: Debian + Ubuntu dual-boot
   - MacBook: single OS only (vendor-locked)

6. **Compile-time validation**
   - Service requirements validated against firmware + OS capabilities
   - Early error detection (schema time, not deploy time)

### Trade-offs

1. **Three-level hierarchy for all entities**
   - Class -> Object -> Instance for firmware, OS, devices
   - More directory structure, but consistent model

2. **Implementation effort: 6-8 weeks** for full migration
   - 5-phase migration plan
   - Reversible until Phase 4

3. **Temporary dual-mode** during migration
   - Both old and new models supported (Phases 1-3)
   - Resolved in Phase 5 cleanup

---

## Implementation Checklist

### Phase 1: Define Classes (COMPLETE)
- [x] Define `class.firmware` with properties and capabilities
- [x] Define `class.os` with properties and capabilities
- [x] Document capability namespaces (`cap.firmware.*`, `cap.os.*`)
- [x] Create examples: PC, MacBook, MikroTik, PDU

### Phase 2: Create Objects and Instances (COMPLETE)
- [x] Create firmware objects (obj.firmware.routeros.7.arm64, obj.firmware.uefi.generic.x86_64, etc.)
- [x] Create OS objects (obj.os.debian.12.arm64.edge, obj.os.proxmox.ve.9, obj.os.routeros.7.arm64, etc.)
- [x] Create firmware instances (inst.firmware.* in instance-bindings.yaml)
- [x] Create OS instances (inst.os.* in instance-bindings.yaml)
- [x] Implement compiler capability derivation

### Phase 3: Device Migration (COMPLETE - 100% migrated)
- [x] Add `firmware_ref` and `os_refs` to device instance schema
- [x] Migrate all L1 devices with firmware_ref/os_refs
- [x] Migrate all L4 LXC containers with os_refs
- [x] Implement validation rules (firmware_ref, os_refs, architecture, embedded_in)
- [x] Add `embedded_in` field for embedded OS instances

### Phase 4: Deprecation (COMPLETE)
- [x] Warn on old model usage (W3201 for legacy software.os fields)
- [x] Require new model for new devices (--require-new-model flag)
- [x] Final v4 compatibility verification (all validators pass)

### Phase 5: Cleanup (COMPLETE)
- [x] Hard error on old model (E3202 with --require-new-model)
- [x] Remove legacy code paths (all objects migrated, no legacy fields)
- [x] Final validation and capability derivation tests (test_adr0064_capability_derivation.py)

---

## References

**Analysis Documents** (see `adr/0064-analysis/`):
- `os-modeling-approach-comparison.md`: Property vs class model comparison
- `os-modeling-scenarios.md`: Real-world scenarios with examples
- `adr-0064-revision-proposal.md`: Technical implementation details
- `decision-matrix-and-scenarios.md`: Scenario validation matrices

**Code Locations**:
- Firmware objects: `v5/topology/object-modules/software/obj.firmware.*.yaml`
- OS objects: `v5/topology/object-modules/software/obj.os.*.yaml`
- Device objects: `v5/topology/object-modules/{vendor}/obj.*.yaml`
- Instance bindings: `v5/topology/instances/home-lab/instance-bindings.yaml`
- Layer contract: `v5/topology/layer-contract.yaml`
- Manifest: `v5/topology/topology.yaml`

**Key Concepts**:
- **Firmware**: Low-level vendor/hardware-bound software foundation
- **OS**: Higher-level operating system layer (embedded or installable)
- **Embedded OS**: Part of firmware stack, not independently replaceable
- **Installable OS**: Independent from firmware, user can change

**Status**: Approved 2026-03-08
