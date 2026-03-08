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

### Core Insight: Firmware ≠ OS

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
- ❌ RouterOS firmware treated as "OS" (missing firmware layer)
- ❌ PC BIOS not modeled (OS-only binding)
- ❌ PDU firmware not distinguished from "OS-less"
- ❌ Embedded vs installable OS not structurally different

### Decision: Two First-Class Entities

Software stack is now modeled as:
- ✅ `class: firmware` → `object: mikrotik-routeros7-firmware`
- ✅ `class: os` → `object: routeros-7`, `object: debian-12`, `object: macos-14`
- ✅ Devices **bind** to both (firmware required, OS conditional)
- ✅ OS types: `embedded` (part of firmware stack) or `installable` (independent)

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
  ├─ Object: routeros-7
  │   ├─ Instance: routeros-7-1
  │   └─ Instance: routeros-7-2
  └─ Object: generic-uefi-x86
      └─ Instance: generic-uefi-2.8
```

```
Class: os
  ├─ Object: debian-12
  │   ├─ Instance: debian-12-production
  │   └─ Instance: debian-12-staging
  └─ Object: windows-11
      └─ Instance: windows-11-enterprise
```

```
Class: compute
  ├─ Object: pc
  │   ├─ Instance: pc-workstation-01
  │   └─ Instance: pc-workstation-02
  └─ Object: orange-pi-5
      └─ Instance: sbc-orangepi-01
```

### 1. Firmware Is a First-Class Entity (Always Required for Active Devices)

```yaml
# Class definition
class: firmware
categories: [infrastructure, prerequisite, hardware-bound]

properties:
  # Identification (required)
  vendor: mikrotik | apple | generic | apc | cisco | ubiquiti
  family: routeros | apple_silicon | bios | uefi | proprietary
  version: string
  architecture: x86_64 | arm64 | mips | armhf
  
  # Boot and runtime
  boot_stack: bios | uefi | proprietary | none
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
# Object definition
object: mikrotik-routeros7
class_ref: class.firmware

properties:
  vendor: mikrotik
  family: routeros
  version: "7.1"
  architecture: x86_64
  boot_stack: proprietary
  hardware_locked: true
  vendor_locked: true

# Derived capabilities:
# - cap.firmware.mikrotik
# - cap.firmware.routeros
# - cap.firmware.mikrotik.routeros.7
# - cap.firmware.arch.x86_64
```

```yaml
# Object definition
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
```

**Firmware instance examples:**

```yaml
# Instance definition
instance: routeros-7-1
object_ref: obj.mikrotik-routeros7

# Specific deployment version
deployment:
  installed_date: "2024-01-15"
  patch_level: "7.1.5"
```

```yaml
# Instance definition
instance: generic-uefi-2.8
object_ref: obj.generic-uefi-x86

deployment:
  installed_date: "2023-10-01"
```

```yaml
# Object definition
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
```

```yaml
# Object definition
object: mikrotik-chateau-lte7ax
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
# Object definition
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
  release_id: string  # normalized for IDs
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
  image_size_gb: number
  
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
# Object definition
object: routeros-7
class_ref: class.os

properties:
  family: routeros
  distribution: routeros
  release: "7.1"
  release_id: "7"
  architecture: x86_64
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
# - cap.arch.x86_64
```

```yaml
# Object definition
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

# Derived capabilities:
# - cap.os.linux
# - cap.os.debian
# - cap.os.debian.12
# - cap.os.init.systemd
# - cap.os.pkg.apt
# - cap.os.installable
# - cap.arch.x86_64
```

**OS instance examples:**

```yaml
# Instance definition
instance: routeros-7-production
object_ref: obj.routeros-7

deployment:
  installed_date: "2024-02-01"
  patch_level: "7.1.5"
```

```yaml
# Instance definition
instance: debian-12-production
object_ref: obj.debian-12

deployment:
  installed_date: "2024-01-10"
  kernel_version: "6.1.0-17"
```

```yaml
# Instance definition
instance: debian-12-staging
object_ref: obj.debian-12

deployment:
  installed_date: "2024-03-01"
  kernel_version: "6.1.0-18"
```

```yaml
# Object definition
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
```

```yaml
# Object definition
object: ubuntu-22.04-arm64
class_ref: class.os

properties:
  family: linux
  distribution: ubuntu
  release: "22.04"
  release_id: "2204"
  codename: jammy
  architecture: arm64
  init_system: systemd
  package_manager: apt
  kernel: linux
  installation_model: installable
  supports_multiboot: true
  base_image_format: rootfs
```

```yaml
# Object definition
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
```

```yaml
# Object definition
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
```
# - cap.os.pkg.apt
# - cap.os.installable
# - cap.arch.arm64
```

```yaml
# object: macos-14
class: os
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
# - cap.os.embedded
# - cap.arch.arm64
```

```yaml
# object: windows-11
class: os
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
    min_items: 1
    max_items: 3

firmware_policy: required
os_policy: installable_allowed
```

**Object level** defines device profile and refines constraints:

```yaml
# object: pc
object: pc
class_ref: class.compute

os_constraints:
  installation_model: [installable]
  multi_boot: true
  min_items: 1
  max_items: 3
```

```yaml
# object: macbook
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
# object: orange-pi-5
object: orange-pi-5
class_ref: class.compute

os_constraints:
  installation_model: [installable]
  multi_boot: true
  architecture: [arm64]
  min_items: 1
  max_items: 2
```

```yaml
# object: mikrotik-chateau-lte7ax
object: mikrotik-chateau-lte7ax
class_ref: class.compute

os_constraints:
  installation_model: [embedded]
  multi_boot: false
  min_items: 1
  max_items: 1
```

**Instance level** specifies concrete firmware/OS instances:

```yaml
# instance: PC dual-boot
instance: pc-workstation-02
object_ref: obj.pc

firmware_ref: firmware.generic-uefi-2.8
os_refs:
  - os.windows-11-enterprise
  - os.debian-12-production
```

```yaml
# instance: MacBook
instance: macbook-pro-01
object_ref: obj.macbook

firmware_ref: firmware.apple-m2-14.2
os_refs:
  - os.macos-14-production
```

```yaml
# instance: MikroTik Chateau LTE7ax
instance: edge-mikrotik-chateau-01
object_ref: obj.mikrotik-chateau-lte7ax

firmware_ref: firmware.routeros-7-13-arm64
os_refs:
  - os.routeros-7-production
```

```yaml
# instance: Orange Pi 5 dual-boot
instance: sbc-orangepi-02
object_ref: obj.orange-pi-5

firmware_ref: firmware.uboot-2023.07-arm64
os_refs:
  - os.debian-12-arm64-production
  - os.ubuntu-2204-arm64-staging
```

```yaml
# instance: PDU (no OS)
instance: pdu-rack-a-01
object_ref: obj.apc-pdu

firmware_ref: firmware.apc-pdu-3.9.2
# os_refs: absent (forbidden by class policy)
```

### 4. Effective Capability Derivation

Compiler derives device capabilities from firmware instance and OS instances:

```yaml
# Device instance: pc-workstation-02 (dual-boot)
instance: pc-workstation-02
object_ref: obj.pc

firmware_ref: firmware.generic-uefi-2.8
os_refs:
  - os.windows-11-enterprise
  - os.debian-12-production

# Compiler derives:
effective_capabilities:
  from_firmware:
    - cap.firmware.generic
    - cap.firmware.uefi
    - cap.firmware.arch.x86_64
    - cap.firmware.boot.uefi
  from_os[0] (Windows):
    - cap.os.windows
    - cap.os.windows.11
    - cap.os.installable
  from_os[1] (Debian):
    - cap.os.linux
    - cap.os.debian
    - cap.os.debian.12
    - cap.os.init.systemd
    - cap.os.pkg.apt
    - cap.os.installable
  combined:
    - all of the above
    
# This device can run services requiring Windows OR Linux
```
  os_primary: obj.os.debian-12-generic

# Compiler derives:
effective_capabilities:
  from_firmware:
    - cap.firmware.generic
    - cap.firmware.uefi
    - cap.firmware.arch.x86_64
    - cap.firmware.boot.uefi
  from_os_primary:
    - cap.os.linux
    - cap.os.debian
    - cap.os.debian.12
    - cap.os.init.systemd
    - cap.os.pkg.apt
    - cap.os.installable
    - cap.arch.x86_64
  combined:
    - all of the above
```

**Multi-boot capability derivation:**

```yaml
# Device: pc-workstation-02 (dual-boot Windows + Linux)
bindings:
  firmware: obj.firmware.generic-uefi-x86
  os_primary: obj.os.windows-11
  os_secondary: obj.os.debian-12-generic

# Compiler derives:
effective_capabilities:
  from_firmware:
    - cap.firmware.generic
    - cap.firmware.uefi
    - cap.firmware.arch.x86_64
  from_os_primary:
    - cap.os.windows
    - cap.os.windows.11
    - cap.os.installable
  from_os_secondary:
    - cap.os.linux
    - cap.os.debian
    - cap.os.debian.12
    - cap.os.init.systemd
    - cap.os.pkg.apt
  combined:
    - all from firmware
    - all from os_primary
    - all from os_secondary
    
# This device can run services requiring EITHER Windows OR Linux
# Deployment system must specify which OS context to use
```

### 5. Service/Workload Requirements

Services declare requirements against firmware and OS capabilities:

```yaml
# service: prometheus
requires:
  capabilities:
    all:
      - cap.os.linux
      - cap.os.init.systemd
    any:
      - cap.os.debian
      - cap.os.ubuntu
      - cap.os.alpine

# Compiler validates at schema time:
# Device pc-workstation-02:
#   os_refs includes debian-12-production
#   has cap.os.linux ✓
#   has cap.os.init.systemd ✓
#   has cap.os.debian ✓
# Result: COMPATIBLE
```

```yaml
# service: routeros-specific-tool
requires:
  capabilities:
    all:
      - cap.firmware.mikrotik
      - cap.os.routeros

# Compiler validates:
# Device edge-mikrotik-chateau-01:
#   firmware_ref: routeros-7-13-arm64
#   has cap.firmware.mikrotik ✓
#   has cap.os.routeros ✓
# Result: COMPATIBLE
#
# Device pc-workstation-02:
#   firmware_ref: generic-uefi-2.8
#   missing cap.firmware.mikrotik ✗
# Result: INCOMPATIBLE
```

### 6. Validation Rules

Compiler MUST enforce:

1. **Firmware reference validation:**
   - Every active device with `firmware_policy: required` MUST have `firmware_ref`
   - Referenced firmware instance MUST exist
   - Firmware instance's object MUST be class `firmware`
   - Firmware architecture MUST match device object constraints

2. **OS reference validation:**
   - If `os_policy: required`, device instance MUST have `os_refs` with at least `min_items`
   - If `os_policy: forbidden`, device instance MUST NOT have `os_refs`
   - Each referenced OS instance MUST exist
   - Each OS instance's object MUST be class `os`
   - OS `installation_model` MUST match device object `os_constraints`
   - Array length MUST satisfy `min_items` and `max_items`

3. **Multi-boot validation:**
   - If `multi_boot: false`, `os_refs` MUST have exactly 1 item
   - If `multi_boot: true`, `os_refs` MAY have multiple items (up to `max_items`)
   - All OS instances in `os_refs` MUST have `installation_model: installable`
   - All OS instances MUST have compatible architecture

4. **Capability derivation:**
   - Derive capabilities from firmware instance's object properties
   - Derive capabilities from ALL OS instances' object properties
   - Combine into device effective capability set
   - Multi-boot device has capabilities from ALL OS instances

5. **Service-device matching:**
   - Service `requires.capabilities.all` → device MUST have ALL listed capabilities
   - Service `requires.capabilities.any` → device MUST have AT LEAST ONE
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
| **PC Dual-boot** | generic-uefi-2.8 | windows-11-enterprise + debian-12-production | installable | Both Windows and Linux |
| **MacBook Pro** | apple-m2-14.2 | macos-14-production | embedded | Vendor-locked, no dual-boot |
| **Orange Pi 5 (SBC)** | uboot-2023.07-arm64 | debian-12-arm64-production | installable | ARM SBC, RK3588S, SD card |
| **Orange Pi 5 dual-boot** | uboot-2023.07-arm64 | debian-12-arm64-production + ubuntu-2204-arm64-staging | installable | Two ARM64 distros |
| **MikroTik Chateau LTE7ax** | routeros-7-13-arm64 | routeros-7-production | embedded | Edge compute + routing |
| **MikroTik RB3011** | routeros-7-1 | routeros-7-production | embedded | OS part of firmware |
| **PDU APC** | apc-pdu-3.9.2 | (none) | N/A | Firmware-only |
| **Raspberry Pi** | arm64-boot-2023 | debian-12-arm64-production | installable | SD card, can multi-boot |
| **VM (KVM)** | virtual-bios-1.0 | debian-12-production | installable | Virtual firmware |

**Multi-boot notes:**
- PC supports multiple OS instances in `os_refs` array
- MacBook does NOT support multi-boot (vendor policy: `os_constraints.multi_boot: false`)
- Orange Pi 5 CAN multi-boot (partition boot or swap SD card)
- MikroTik Chateau: edge compute device with embedded RouterOS
- Each OS instance contributes its capabilities to device effective capability set

### 9. Migration Contract: 5-Phase Transition

**Phase 1: Add firmware and OS classes** (weeks 1-2)
- Define `class: firmware` with properties and capabilities
- Define `class: os` with properties and capabilities
- Create firmware objects for all active device types
- Create OS objects for all distributions in use
- No breaking changes (old model still works)

**Phase 2: Device binding support** (weeks 3-5)
- Add `bindings.firmware` and `bindings.os` to device schema
- Implement compiler validation for bindings
- Implement capability derivation from firmware + OS
- Devices can optionally use new bindings (old model still works)

**Phase 3: Parallel validation** (weeks 6-7)
- Compiler validates both old and new models
- Migration tooling: auto-convert old → new bindings
- Migrate 50% of devices to new model
- Test service-device matching with new capabilities

**Phase 4: Deprecation** (week 8)
- Warn on old model usage (deprecated)
- Require new bindings for new devices
- Migrate remaining 50% of devices

**Phase 5: Cleanup** (week 9+)
- Hard error on old model
- Remove legacy code paths
- All devices use firmware + OS bindings

**Risk:** LOW (reversible until Phase 4)
  package_manager: none
  installation_model: firmware
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
- Implement compiler capability derivation from firmware + OS instances
- Devices can optionally use new model (old model still works)

**Phase 3: Device instance migration** (weeks 6-7)
- Migrate device instances to use `firmware_ref` and `os_refs`
- Enable dual validation (both old and new models)
- Migration tooling: auto-convert old → new format
- Migrate 50% of device instances

**Phase 4: Deprecation** (week 8)
- Warn on old model usage (deprecated)
- Require new model for new device instances
- Migrate remaining 50% of device instances

**Phase 5: Cleanup** (week 9+)
- Hard error on old model
- Remove legacy code paths
- Final validation and testing

**Risk:** LOW (reversible until Phase 4)

---

## Consequences

### Positive

1. **Firmware and OS are properly separated**
   - Firmware as foundational layer (always required for active devices)
   - OS as runtime layer (conditional, can be embedded or installable)
   - PDU firmware without OS is natural (not "OS-less device")
   - PC BIOS/UEFI firmware is explicit (not hidden)

2. **Clear semantic distinction**
   - `class: firmware` → `object: mikrotik-routeros7` → `instance: routeros-7-1`
   - `class: os` → `object: debian-12` → `instance: debian-12-production`
   - `class: os` → `object: routeros-7`, `object: debian-12`
   - MikroTik has both firmware AND embedded OS (two entities, linked)
   - Device: `class: compute` → `object: pc` → `instance: pc-workstation-01`

3. **Instance references model**
   - Device instances reference firmware/OS instances directly
   - `firmware_ref: firmware.generic-uefi-2.8`
   - `os_refs: [os.debian-12-production, os.windows-11-enterprise]`
   - No nested bindings, clean references

4. **Capabilities from both layers**
   - Firmware capabilities: `cap.firmware.mikrotik`, `cap.firmware.routeros`, `cap.firmware.arch.x86_64`
   - OS capabilities: `cap.os.routeros.7`, `cap.os.embedded`
   - Services can require firmware-specific or OS-specific capabilities
   - Example: RouterOS management tool requires `cap.firmware.mikrotik` + `cap.os.routeros`

5. **Embedded vs installable is OS property**
   - MikroTik: firmware contains embedded OS (not replaceable independently)
   - PC: firmware (UEFI) + installable OS (Debian/Windows, user choice)
   - MacBook: firmware + embedded OS (macOS, vendor-locked)
   - Clear modeling of reality

6. **Compile-time service-device validation**
   - Service requirements validated against firmware + OS capabilities
   - Early error detection (schema time, not deploy time)
   - Auto-generate compatibility matrix

7. **OS lifecycle tracking**
   - OS instances can have deployment metadata
   - Track installed_date, patch_level, kernel_version
   - Audit trail for deployed versions

8. **Multi-boot support**
   - `os_refs` array can contain multiple OS instances
   - PC: Windows + Linux dual-boot
   - Orange Pi: Debian + Ubuntu dual-boot
   - MacBook: single OS only (vendor-locked)

### Trade-offs

1. **Three-level hierarchy for all entities**
   - Class → Object → Instance for firmware, OS, devices
   - More directory structure
   - But: consistent model everywhere

2. **Implementation effort: 6-8 weeks** for full migration
   - Define firmware/OS classes, objects, instances
   - Migrate device instances to new references
   - 5-phase migration plan

3. **Temporary dual-mode** during migration
   - Both old and new models supported (Phase 1-3)
   - Increases compiler complexity temporarily
   - Resolved in Phase 5 cleanup
   - Well-organized, but more files

### Risk Mitigation

| Risk | Likelihood | Mitigation |
|------|---|---|
| Implementation delays | Low | 5-phase approach, reversible until Phase 4 |
| Firmware/OS confusion | Medium | Clear documentation, examples, training |
| Capability proliferation | Low | Structured namespaces (`cap.firmware.*`, `cap.os.*`) |
| Team adoption | Medium | Real-world examples (PC, MacBook, MikroTik, PDU) |

---

## Implementation Checklist

## Implementation Checklist

### Phase 1: Define Firmware and OS Classes (weeks 1-2)

- [ ] Define `class: firmware` with properties and capabilities
- [ ] Define `class: os` with properties and capabilities
- [ ] Document firmware capability namespace (`cap.firmware.*`)
- [ ] Document OS capability namespace (`cap.os.*`)
- [ ] Create examples: PC, MacBook, MikroTik, PDU
- [ ] No breaking changes

**Success criteria:** Classes defined, documentation clear

### Phase 2: Create Firmware and OS Objects (weeks 3-5)

- [ ] Create firmware objects:
  - [ ] generic-uefi-x86-firmware
  - [ ] generic-bios-x86-firmware
  - [ ] apple-silicon-m2-firmware
  - [ ] mikrotik-routeros7-firmware
  - [ ] apc-pdu-mgmt-firmware
  - [ ] (others as needed)
- [ ] Create OS objects:
  - [ ] debian-12-generic, debian-12-hardened
  - [ ] ubuntu-22.04, ubuntu-24.04
  - [ ] alpine-3-19
  - [ ] routeros-7, routeros-6
  - [ ] macos-14
  - [ ] windows-11
  - [ ] (others as needed)
- [ ] Implement compiler capability derivation from firmware + OS
- [ ] Objects can optionally use new bindings (not yet required)

**Success criteria:** All firmware and OS objects created, compiler derives capabilities

### Phase 3: Device Binding Support (weeks 6-7)

- [ ] Add `bindings.firmware` and `bindings.os` to device schema
- [ ] Implement compiler validation for bindings
- [ ] Implement `firmware_policy` and `os_policy` class constraints
- [ ] Create migration tooling (old model → new bindings)
- [ ] Migrate 50% of devices
- [ ] Enable dual validation (both models work)

**Success criteria:** 50% migrated, dual validation works, no regressions

### Phase 4: Deprecation (week 8)

- [ ] Warn on old model usage (deprecated)
- [ ] Require new bindings for new devices
- [ ] Migrate remaining 50% of devices
- [ ] Update all documentation

**Success criteria:** All devices using new bindings, old model deprecated

### Phase 5: Cleanup (week 9+)

- [ ] Hard error on old model
- [ ] Remove legacy code paths
- [ ] Final validation and testing
- [ ] Post-migration review

**Success criteria:** Old model removed, clean implementation

---

## Dependencies and Related ADRs

### Extends
- ADR 0062: Topology v5 - Modular Class-Object-Instance Architecture

### Related
- ADR 0035: L4 Host OS Foundation and Runtime Substrates
- ADR 0039: L4 Host OS Installation Storage Contract Clarification

### Dependent (Future)
- ADR 0065: Firmware Instance Catalog Format and Registry
- ADR 0066: OS Instance Catalog Format and Registry
- ADR 0067: Compiler Capability Derivation From Firmware + OS Bindings
- ADR 0068: Service-Device Validation Engine

---

## References

**Analysis Documents** (see `adr/0064-analysis/`):
- `os-modeling-approach-comparison.md`: Detailed comparison of modeling approaches
- `os-modeling-scenarios.md`: Real-world scenarios with code examples
- `adr-0064-revision-proposal.md`: Technical implementation details
- `decision-matrix-and-scenarios.md`: Scenario validation matrices

**Code Locations**:
- Firmware class: `v5/topology/class-modules/classes/firmware/`
- Firmware objects: `v5/topology/class-modules/classes/firmware/instances/`
- OS class: `v5/topology/class-modules/classes/os/`
- OS objects: `v5/topology/class-modules/classes/os/instances/`
- Device classes: `v5/topology/class-modules/classes/compute/`, `v5/topology/class-modules/classes/router/`, `v5/topology/class-modules/classes/power/`
- Device objects: `v5/topology/object-modules/`
- Manifest: `v5/topology/topology.yaml`

**Key Concepts**:
- **Firmware**: Low-level vendor/hardware-bound software foundation (always required for active devices)
- **OS**: Higher-level operating system layer (conditional: embedded or installable)
- **Embedded OS**: Part of firmware stack, not independently replaceable (e.g., RouterOS, macOS)
- **Installable OS**: Independent from firmware, user can change (e.g., Linux, Windows)
- **Firmware-only device**: Has firmware but no OS layer (e.g., PDU with management firmware)

**Real-World Examples**:
- PC: `firmware=generic-uefi-x86` + `os=debian-12` (installable)
- MacBook: `firmware=apple-silicon-m2` + `os=macos-14` (embedded)
- MikroTik: `firmware=mikrotik-routeros7` + `os=routeros-7` (embedded)
- PDU: `firmware=apc-pdu-mgmt` + no OS (firmware-only)

**Timeline**: Approved 2026-03-08, target completion 2026-05-17 (Phase 5 cleanup)
- ADR 0039: L4 Host OS Installation Storage Contract Clarification

### Dependent (Future)
- ADR 0065: OS Instance Catalog Format and Registry
- ADR 0066: Compiler Capability Derivation From OS Bindings
- ADR 0067: Service-Device Validation Engine

---

## References

**Analysis Documents** (see `adr/0064-analysis/`):
- `os-modeling-approach-comparison.md`: Detailed pros/cons of property vs. class models
- `os-modeling-scenarios.md`: 6 real-world scenarios with code examples
- `adr-0064-revision-proposal.md`: Technical implementation details
- `decision-matrix-and-scenarios.md`: Scenario validation matrices

**Code Locations**:
- OS class definition: `v5/topology/class-modules/classes/os/`
- OS instances: `v5/topology/class-modules/classes/os/instances/`
- Device classes: `v5/topology/class-modules/classes/compute/`, `v5/topology/class-modules/classes/router/`
- Object examples: `v5/topology/object-modules/`
- Manifest: `v5/topology/topology.yaml`

**Timeline**: Approved 2026-03-08, target completion 2026-05-17 (Phase 5 cleanup)
