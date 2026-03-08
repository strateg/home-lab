# ADR 0064: Software Stack Taxonomy - Firmware and OS as Separate Entities

**Date:** 2026-03-08
**Status:** Approved - Two-Entity Model (Firmware + OS)
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
- `class: firmware` -> `object: mikrotik-routeros7-firmware`
- `class: os` -> `object: routeros-7`, `object: debian-12`, `object: macos-14`
- Devices **bind** to both (firmware required, OS conditional)
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
# Object definition
object: <name>
class_ref: class.<class_name>

# Instance definition
instance: <name>
object_ref: obj.<object_name>
```

**Example hierarchy:**

```
Class: firmware
  +-- Object: routeros-7
  |     +-- Instance: routeros-7-1
  |     +-- Instance: routeros-7-2
  +-- Object: generic-uefi-x86
        +-- Instance: generic-uefi-2.8

Class: os
  +-- Object: debian-12
  |     +-- Instance: debian-12-production
  |     +-- Instance: debian-12-staging
  +-- Object: windows-11
        +-- Instance: windows-11-enterprise

Class: compute
  +-- Object: pc
  |     +-- Instance: pc-workstation-01
  |     +-- Instance: pc-workstation-02
  +-- Object: orange-pi-5
        +-- Instance: sbc-orangepi-01
```

### 1. Firmware Is a First-Class Entity (Always Required for Active Devices)

```yaml
# Class definition
class: firmware
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
```

**Firmware object examples:**

```yaml
# MikroTik RouterOS firmware
object: mikrotik-routeros7
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
object: generic-uefi-x86
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
object: generic-arm64-uboot
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
object: apc-pdu-mgmt
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

**Firmware instance examples:**

```yaml
instance: routeros-7-13-arm64
object_ref: obj.mikrotik-routeros7

deployment:
  installed_date: "2024-01-15"
  patch_level: "7.13.5"
```

```yaml
instance: generic-uefi-2.8
object_ref: obj.generic-uefi-x86

deployment:
  installed_date: "2023-10-01"
```

### 2. OS Is a First-Class Entity (Conditionally Required)

```yaml
# Class definition
class: os
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
    - cap.arch.{architecture}
  conditional:
    - cap.os.embedded (if installation_model == embedded)
    - cap.os.installable (if installation_model == installable)
```

**OS object examples:**

```yaml
# RouterOS (embedded in firmware)
object: routeros-7
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
# - cap.arch.arm64
```

```yaml
# Debian 12 (installable)
object: debian-12
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
# - cap.arch.x86_64
```

```yaml
# Debian 12 ARM64 variant
object: debian-12-arm64
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
# - cap.arch.arm64
```

```yaml
# macOS (embedded, vendor-locked)
object: macos-14
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
# - cap.arch.arm64
```

```yaml
# Windows 11 (installable)
object: windows-11
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
# - cap.arch.x86_64
```

**OS instance examples:**

```yaml
instance: routeros-7-production
object_ref: obj.routeros-7

deployment:
  installed_date: "2024-02-01"
  patch_level: "7.13.5"
```

```yaml
instance: debian-12-production
object_ref: obj.debian-12

deployment:
  installed_date: "2024-01-10"
  kernel_version: "6.1.0-17"
```

```yaml
instance: debian-12-arm64-production
object_ref: obj.debian-12-arm64

deployment:
  installed_date: "2024-03-01"
  kernel_version: "6.1.0-18"
```

### 3. Device Binding: Direct Instance References

Device instances reference **firmware instance** and **OS instances** directly using `firmware_ref` and `os_refs`.

**Class level** defines binding constraints (types and cardinalities):

```yaml
# class: compute
bindings:
  firmware:
    kind: single
    class: firmware
    required: true
  os:
    kind: array
    class: os
    min_items: 0
    max_items: 3

firmware_policy: required
os_policy: conditional  # depends on device type
```

**Object level** defines device profile and refines constraints:

```yaml
# PC object (supports multi-boot)
object: pc
class_ref: class.compute

os_constraints:
  installation_model: [installable]
  multi_boot: true
  min_items: 1
  max_items: 3
```

```yaml
# MacBook object (vendor-locked, no multi-boot)
object: macbook
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
object: orange-pi-5
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
object: mikrotik-chateau-lte7ax
class_ref: class.compute

os_constraints:
  installation_model: [embedded]
  multi_boot: false
  min_items: 1
  max_items: 1
```

```yaml
# PDU object (no OS)
object: apc-pdu
class_ref: class.power

os_constraints:
  min_items: 0
  max_items: 0  # OS forbidden
```

**Instance level** specifies concrete firmware/OS instances:

```yaml
# PC single-boot
instance: pc-workstation-01
object_ref: obj.pc

firmware_ref: firmware.generic-uefi-2.8
os_refs: [os.debian-12-production]
```

```yaml
# PC dual-boot
instance: pc-workstation-02
object_ref: obj.pc

firmware_ref: firmware.generic-uefi-2.8
os_refs: [os.windows-11-enterprise, os.debian-12-production]
```

```yaml
# MacBook
instance: macbook-pro-01
object_ref: obj.macbook

firmware_ref: firmware.apple-m2-14.2
os_refs: [os.macos-14-production]
```

```yaml
# MikroTik Chateau LTE7ax
instance: edge-mikrotik-chateau-01
object_ref: obj.mikrotik-chateau-lte7ax

firmware_ref: firmware.routeros-7-13-arm64
os_refs: [os.routeros-7-production]
```

```yaml
# Orange Pi 5 dual-boot
instance: sbc-orangepi-02
object_ref: obj.orange-pi-5

firmware_ref: firmware.uboot-2023.07-arm64
os_refs: [os.debian-12-arm64-production, os.ubuntu-2204-arm64-staging]
```

```yaml
# PDU (no OS)
instance: pdu-rack-a-01
object_ref: obj.apc-pdu

firmware_ref: firmware.apc-pdu-3.9.2
# os_refs: absent (forbidden by object constraints)
```

### 4. Effective Capability Derivation

Compiler derives device capabilities from firmware instance and all OS instances:

```yaml
# Device instance: pc-workstation-02 (dual-boot Windows + Linux)
instance: pc-workstation-02
object_ref: obj.pc

firmware_ref: firmware.generic-uefi-2.8
os_refs: [os.windows-11-enterprise, os.debian-12-production]

# Compiler derives:
effective_capabilities:
  from_firmware:
    - cap.firmware.generic
    - cap.firmware.uefi
    - cap.firmware.arch.x86_64
    - cap.firmware.boot.uefi
  from_os[0]:  # Windows
    - cap.os.windows
    - cap.os.windows.11
    - cap.os.installable
    - cap.arch.x86_64
  from_os[1]:  # Debian
    - cap.os.linux
    - cap.os.debian
    - cap.os.debian.12
    - cap.os.init.systemd
    - cap.os.pkg.apt
    - cap.os.installable
    - cap.arch.x86_64
  combined:
    - all firmware capabilities
    - all OS capabilities from all os_refs

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

3. **Multi-boot validation:**
   - If `multi_boot: false`, `os_refs` MUST have exactly 1 item (when required)
   - If `multi_boot: true`, `os_refs` MAY have multiple items (up to `max_items`)
   - All OS instances in `os_refs` MUST have compatible architecture

4. **Capability derivation:**
   - Derive capabilities from firmware instance's object properties
   - Derive capabilities from ALL OS instances' object properties
   - Combine into device effective capability set

5. **Service-device matching:**
   - Service `requires.capabilities.all` -> device MUST have ALL listed
   - Service `requires.capabilities.any` -> device MUST have AT LEAST ONE
   - For multi-boot: service can be deployed to ANY compatible OS context

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
| **PC Single-boot** | generic-uefi-2.8 | debian-12-production | installable | User can change OS |
| **PC Dual-boot** | generic-uefi-2.8 | windows-11 + debian-12 | installable | Both Windows and Linux |
| **MacBook Pro** | apple-m2-14.2 | macos-14-production | embedded | Vendor-locked, no dual-boot |
| **Orange Pi 5** | uboot-2023.07-arm64 | debian-12-arm64 | installable | ARM SBC, SD card |
| **Orange Pi 5 dual** | uboot-2023.07-arm64 | debian-12 + ubuntu-2204 | installable | Two ARM64 distros |
| **MikroTik Chateau** | routeros-7-13-arm64 | routeros-7-production | embedded | Edge compute + routing |
| **PDU APC** | apc-pdu-3.9.2 | (none) | N/A | Firmware-only |
| **VM (KVM)** | virtual-bios-1.0 | debian-12-production | installable | Virtual firmware |

### 9. Migration Contract: 5-Phase Transition

**Phase 1: Define firmware and OS classes** (weeks 1-2)
- Define `class: firmware` with properties and capabilities
- Define `class: os` with properties and capabilities
- Create firmware objects for all active device types
- Create OS objects for all distributions in use
- No breaking changes (old model still works)

**Phase 2: Create firmware and OS instances** (weeks 3-5)
- Create firmware instances for deployed versions
- Create OS instances for deployed versions
- Implement compiler capability derivation
- Devices can optionally use new model

**Phase 3: Device instance migration** (weeks 6-7)
- Migrate device instances to use `firmware_ref` and `os_refs`
- Enable dual validation (both old and new models)
- Migration tooling: auto-convert old -> new format
- Migrate 50% of device instances

**Phase 4: Deprecation** (week 8)
- Warn on old model usage
- Require new model for new device instances
- Migrate remaining 50%

**Phase 5: Cleanup** (week 9+)
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
   - `class: firmware` -> `object: mikrotik-routeros7` -> `instance: routeros-7-1`
   - `class: os` -> `object: debian-12` -> `instance: debian-12-production`
   - MikroTik has both firmware AND embedded OS (two entities, linked)

3. **Instance references model**
   - Device instances reference firmware/OS instances directly
   - `firmware_ref: firmware.generic-uefi-2.8`
   - `os_refs: [os.debian-12-production, os.windows-11-enterprise]`
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

### Phase 1: Define Classes (weeks 1-2)
- [ ] Define `class: firmware` with properties and capabilities
- [ ] Define `class: os` with properties and capabilities
- [ ] Document capability namespaces (`cap.firmware.*`, `cap.os.*`)
- [ ] Create examples: PC, MacBook, MikroTik, PDU

### Phase 2: Create Objects and Instances (weeks 3-5)
- [ ] Create firmware objects (generic-uefi, mikrotik-routeros7, apc-pdu, etc.)
- [ ] Create OS objects (debian-12, ubuntu-2204, routeros-7, macos-14, etc.)
- [ ] Create firmware instances
- [ ] Create OS instances
- [ ] Implement compiler capability derivation

### Phase 3: Device Migration (weeks 6-7)
- [ ] Add `firmware_ref` and `os_refs` to device instance schema
- [ ] Implement validation rules
- [ ] Create migration tooling
- [ ] Migrate 50% of devices
- [ ] Enable dual validation

### Phase 4: Deprecation (week 8)
- [ ] Warn on old model usage
- [ ] Require new model for new devices
- [ ] Migrate remaining 50%

### Phase 5: Cleanup (week 9+)
- [ ] Hard error on old model
- [ ] Remove legacy code
- [ ] Final validation

---

## References

**Analysis Documents** (see `adr/0064-analysis/`):
- `os-modeling-approach-comparison.md`: Property vs class model comparison
- `os-modeling-scenarios.md`: Real-world scenarios with examples
- `adr-0064-revision-proposal.md`: Technical implementation details
- `decision-matrix-and-scenarios.md`: Scenario validation matrices

**Code Locations**:
- Firmware class: `v5/topology/class-modules/classes/firmware/`
- Firmware objects: `v5/topology/object-modules/firmware/`
- OS class: `v5/topology/class-modules/classes/os/`
- OS objects: `v5/topology/object-modules/os/`
- Device classes: `v5/topology/class-modules/classes/compute/`, `.../router/`, `.../power/`
- Device objects: `v5/topology/object-modules/`
- Manifest: `v5/topology/topology.yaml`

**Key Concepts**:
- **Firmware**: Low-level vendor/hardware-bound software foundation
- **OS**: Higher-level operating system layer (embedded or installable)
- **Embedded OS**: Part of firmware stack, not independently replaceable
- **Installable OS**: Independent from firmware, user can change

**Timeline**: Approved 2026-03-08, target completion 2026-05-17
