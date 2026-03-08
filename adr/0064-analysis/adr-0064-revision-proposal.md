# ADR 0064 Revision Proposal: Class-Based OS Model

**Date:** 2026-03-08  
**Status:** Proposal for Review  
**Relates to:** ADR 0064 (Current: Property-Based Model)

---

## Executive Summary

Propose evolving **ADR 0064** from property-based OS model (`software.os`) to **class-based OS model** with explicit `installation_model` distinction.

This change enables:
- Explicit firmware vs. installable OS classification
- Multi-OS device support
- Compile-time service-device compatibility validation
- OS reuse without duplication
- Future OS specialization and composition

**Scope:** Major refactor; 2-3 phase migration with backward compatibility period

---

## Problem Statement (Refined)

Current ADR 0064 treats OS as an embedded property with a reference (`os_ref`). This creates gaps:

1. **Firmware OS is structured identically to installable OS**
   - No distinction between immutable firmware and user-installable OS
   - Firmware devices (routers) treated as flexible as VMs
   - Impossible to enforce "this router must use RouterOS firmware"

2. **OS reuse requires manual duplication**
   - Every Debian 12 VM contains full OS definition
   - 20 VMs = 20x definition duplication
   - No single source of truth for "Debian 12 in this lab"
   - Changes to OS definition require touching all referencing objects

3. **Multi-OS devices not expressible**
   - Dual-boot, multi-partition, live-boot systems have no natural model
   - Array syntax breaks schema
   - No concept of "primary OS" vs. "secondary OS"

4. **Service-device matching requires runtime checking**
   - Service says "needs systemd + apt"
   - Compiler cannot validate: "Will Prometheus work on vm-app-01?"
   - Validation happens at deploy time, when it's too late
   - No reverse query: "What devices can run Prometheus?"

5. **OS specialization not supported**
   - "Debian 12 standard" vs. "Debian 12 hardened" cannot be modeled
   - Variants duplicate data or use ad-hoc conventions
   - Inheritance relationships not expressible

---

## Proposed Solution

### Core Change: OS Becomes a Class

Move from:
```yaml
object
  software:
    os: {family, distribution, release, ...}
    os_ref: "obj.os.debian.12.generic"
```

To:
```yaml
class os.installable | os.firmware
  properties: {family, distribution, release, installation_model, ...}
  capabilities: [cap.os.*, cap.arch.*]

object
  bindings:
    os: obj.os.debian.12.generic  # Strong reference to OS class instance
```

### 1. OS Class Definition

```yaml
# Canonical OS class
name: os
extends: class

properties:
  # Identification (required)
  family:
    type: enum
    values: [linux, bsd, windows, routeros, proprietary]
    required: true
  distribution:
    type: string
    required: true
  release:
    type: string
    required: true
  release_id:
    type: string
    required: true
  architecture:
    type: enum
    values: [x86_64, arm64, armhf, riscv64, mipsel, ppc64le]
    required: true

  # Characteristics (optional, inferred by default)
  codename: {type: string}
  init_system:
    type: enum
    values: [systemd, openrc, sysvinit, busybox, proprietary]
  package_manager:
    type: enum
    values: [apt, apk, dnf, nix, opkg, pacman, none]
  kernel: {type: string}

  # ** NEW: Installation model **
  installation_model:
    type: enum
    values: [firmware, installable]
    required: true
    description: "Immutable firmware or user-installable OS"

  # Firmware-specific (if installation_model == firmware)
  firmware_locked_to_hardware:
    type: bool
    description: "Firmware is locked to specific hardware SKU"
  vendor_locked_release:
    type: bool
    description: "Cannot upgrade to different vendor release without special tools"
  firmware_vendor:
    type: string
    description: "e.g., Mikrotik, Ubiquiti, Cisco"

  # Installable-specific (if installation_model == installable)
  supports_multiboot:
    type: bool
  supports_live_boot:
    type: bool
  base_image_format:
    type: enum
    values: [qcow2, ova, ami, iso, rootfs, tar.gz, docker, oci]
  image_size_gb:
    type: number
    description: "Typical disk footprint"

  # Metadata
  eol_date: {type: date}
  support_tier: {type: enum, values: [lts, standard, beta, eol]}

# ** NEW: Subclass split **
subclasses:
  - os.firmware
  - os.installable

capabilities:
  dynamic:
    - cap.os.{family}
    - cap.os.{distribution}
    - cap.os.{distribution}.{release_id}
    - cap.os.{codename} (alias to above)
    - cap.os.init.{init_system}
    - cap.os.pkg.{package_manager}
    - cap.arch.{architecture}
  conditional:
    - cap.os.firmware (if installation_model == firmware)
    - cap.os.installable (if installation_model == installable)
    - cap.os.eol (if eol_date < today)
```

### 2. OS Instance Examples

**Installable:**
```yaml
# v5/topology/class-modules/classes/os/instances/debian-12-generic.yaml
name: debian-12-generic
class: os.installable

properties:
  family: linux
  distribution: debian
  release: "12"
  release_id: "12"
  codename: bookworm
  architecture: x86_64
  init_system: systemd
  package_manager: apt
  installation_model: installable
  base_image_format: qcow2
  image_size_gb: 10
```

**Firmware:**
```yaml
# v5/topology/class-modules/classes/os/instances/routeros-7-firmware.yaml
name: routeros-7-firmware
class: os.firmware

properties:
  family: routeros
  distribution: routeros
  release: "7.1"
  release_id: "71"
  architecture: x86_64
  init_system: proprietary
  package_manager: none
  installation_model: firmware
  firmware_locked_to_hardware: true
  vendor_locked_release: true
  firmware_vendor: "Mikrotik"
  support_tier: standard
  eol_date: "2030-12-31"
```

### 3. Device Class Bindings

Devices declare OS binding requirements:

```yaml
# compute.vm class
name: compute.vm
extends: compute

bindings:
  os:
    required: true
    class: os.installable  # MUST be installable, NOT firmware
    description: "VM requires guest OS (not hardware firmware)"

os_expectations:
  installation_models: [installable]
  forbidden_models: [firmware]
  # Reject firmware: firmware is hardware-bound, can't be vm guest
```

```yaml
# router.mikrotik-rb3011 class
name: router.mikrotik_rb3011
extends: router

bindings:
  os:
    required: true
    class: os  # Can be either firmware or installable
    hardware_specific: true
    # Default to firmware, but allow override for testing
    preferred: obj.os.routeros-7-firmware

os_expectations:
  installation_models: [firmware]  # RouterOS must be firmware
  firmware_vendors: [Mikrotik]
  # Enforce: Cannot use Debian on RouterOS hardware
```

```yaml
# cloud.aws_instance class
name: cloud.aws_instance
extends: cloud

bindings:
  os:
    required: true
    class: os.installable
    allowed:  # Can use pre-built AMIs
      - obj.os.debian.12
      - obj.os.ubuntu.22.04
      - obj.os.amazon-linux-2

os_expectations:
  installation_models: [installable]
  base_image_formats: [ami, qcow2]  # Cloud-friendly formats
```

### 4. Object Instance Binding

```yaml
# Simple device
name: vm-app-01
class: compute.vm

bindings:
  os: obj.os.debian.12.generic

---

# Device overriding class default
name: router-mikrotik-01
class: router.mikrotik_rb3011
# Inherits: bindings.os = obj.os.routeros-7-firmware
# Can override if needed:
# bindings:
#   os: obj.os.routeros-6-legacy  (downgrade for testing)
```

### 5. Service/Workload Requirements

Service requirements are unchanged, but now compiler can validate:

```yaml
name: service.prometheus
class: service

requires:
  capabilities:
    all:
      - cap.os.linux
      - cap.os.init.systemd
    any:
      - cap.os.debian
      - cap.os.ubuntu

# Compiler validates:
# 1. Load all objects
# 2. For each object, load bound OS instance
# 3. Derive OS capabilities
# 4. Check: device.capabilities ⊇ service.requires.capabilities
# 5. Auto-generate compatibility matrix
# 6. Report: which devices CAN run Prometheus, which CANNOT
```

### 6. Compiler Changes Required

```yaml
# Validation phase
os_binding_validation:
  1. Verify every object with os_policy=required has binding.os
  2. Verify binding.os points to valid OS class instance
  3. Verify OS class matches class.bindings.os.class constraint
  4. Warn if OS is EOL (cap.os.eol detected)

capability_derivation:
  1. Load object's bound OS instance
  2. Extract all properties
  3. Generate capabilities:
     - cap.os.{family}
     - cap.os.{distribution}
     - cap.os.{distribution}.{release_id}
     - cap.os.init.{init_system}
     - cap.os.pkg.{package_manager}
     - cap.arch.{architecture}
     - cap.os.firmware (if installation_model=firmware)
     - cap.os.installable (if installation_model=installable)
  4. Add to device's effective capability set

service_compatibility_validation:
  1. For each service, extract service.requires.capabilities
  2. For each device, load bound OS, derive capabilities
  3. Check: device.capabilities ⊇ service.requires.capabilities
  4. Build compatibility matrix
  5. Report violations:
     - Device D cannot run Service S because missing cap X
     - Device D is EOL and should be replaced before deploying Service S
  6. Generate report: "What devices can run Prometheus?"
```

### 7. Migration Path

#### Phase 1 (Immediate): Add `installation_model` to current model
- Add optional `installation_model` field to `software.os`
- Classify existing OS definitions as `firmware` or `installable`
- Validator warns if not set
- Still property-based, but with classification

#### Phase 2 (Months 1-2): Create OS class system
- Define OS class and subclasses
- Create instances for all OS variants in use
- Compiler can load OS class instances
- Objects still use property model but optional binding support

#### Phase 3 (Months 2-3): Parallel validation
- Compiler validates both property and binding models
- Reports mismatches
- Tools convert property OS to binding OS
- Migration checklist created

#### Phase 4 (Months 3-4): Property model deprecated
- Validator warns if using property-based OS
- Bindings become required for new objects
- Existing objects converted

#### Phase 5 (Month 5+): Property model removed
- Hard error on property-based OS
- All objects use bindings
- Legacy OS references cleaned up

---

## Detailed Change Summary

### New Entities

1. **os class** (base class, not instantiated directly)
2. **os.firmware subclass** (for firmware instances)
3. **os.installable subclass** (for installable instances)
4. **OS instances** (one per distinct OS version/variant combination)

### Modified Entities

1. **Compute classes** (VM, physical server, cloud): binding.os constraint
2. **Router classes**: binding.os constraint with firmware requirement
3. **Service classes**: capabilities validation at compile time

### New Schema Elements

1. `bindings.os` (reference to OS class instance)
2. `installation_model` (firmware | installable)
3. `os_expectations` (class-level policy)
4. `capability derivation` (compiler feature)

### Removed/Deprecated

1. `software.os` (migrate to bindings.os)
2. `software.os_ref` (becomes implicit in bindings.os)
3. `vendor.*` OS markers (formalized in OS class)

---

## Benefits

### Immediate

1. **Explicit firmware/installable distinction**
   - Compiler rejects firmware OS on VM
   - Compiler rejects installable OS on firmware router
   - Schema enforces physical reality

2. **OS reuse**
   - Define Debian 12 once
   - All Debian 12 VMs reference same instance
   - Changes to Debian 12 definition update all VMs

3. **Compile-time validation**
   - Detect "Prometheus cannot run on alpine" at schema validation
   - Generate "Device compatibility matrix"
   - No runtime surprises

### Long-term

4. **OS specialization**
   - Debian 12 generic + Debian 12 hardened + Debian 12 minimal
   - Variants inherit base definition
   - Specialization adds capabilities (e.g., cap.security.selinux)

5. **Multi-OS devices**
   - Raspberry Pi with multiple boot options
   - Dual-boot systems
   - Live-boot media

6. **OS lifecycle management**
   - OS EOL tracking independent of device lifecycle
   - Compliance reporting: "What devices run EOL OS?"
   - Automatic deprecation warnings

7. **Provisioning integration**
   - Provisioning tool: "Assign Debian 12 to VM" → reference OS class
   - Build system: "Generate Terraform for all Debian 12 VMs"
   - IaC naturally works with OS class abstraction

---

## Trade-offs

| Aspect | Property Model | Class Model |
|--------|---|---|
| Schema simplicity | ✓✓ Minimal | ~ More structure |
| OS reuse | ~ Manual | ✓✓ Automatic |
| Firmware classification | ✗ Implicit | ✓✓ Explicit |
| Compile-time validation | ~ Limited | ✓✓ Full |
| Multi-OS support | ✗ Not supported | ✓✓ Native |
| Migration effort | N/A | ~3-4 weeks |
| Compiler complexity | ~ Simple | ✓ Moderate |

---

## Risk Mitigation

### Risk 1: Migration too disruptive
**Mitigation:** 5-phase approach with 6-month compatibility period

### Risk 2: Class proliferation (too many OS instances)
**Mitigation:** Registry with naming convention; prevent ad-hoc instances

### Risk 3: Dangling OS references
**Mitigation:** Compiler validation in phase 2; hard error in phase 5

### Risk 4: Operator confusion with new model
**Mitigation:** Documentation, migration guide, training materials

---

## Implementation Checklist

- [ ] Design OS class and subclasses (complete)
- [ ] Define installation_model enum values
- [ ] Create validator rules for OS bindings
- [ ] Implement capability derivation logic
- [ ] Create service-device compatibility checker
- [ ] Define OS instance directory structure
- [ ] Migrate all current OS definitions to instances
- [ ] Build OS instance registry/catalog
- [ ] Write migration guide
- [ ] Update class definitions for binding requirements
- [ ] Implement Phase 1 (add classification to property model)
- [ ] Implement Phase 2 (add OS class system)
- [ ] Implement Phase 3 (parallel validation)
- [ ] Implement Phase 4 (deprecation warnings)
- [ ] Implement Phase 5 (hard errors, cleanup)

---

## Next Steps

1. **Review this proposal** against ADR requirements
2. **Gather feedback** on:
   - OS instance naming convention
   - Firmware-specific constraints
   - Multi-OS binding syntax
3. **Refine ADR 0064** based on feedback
4. **Create dependent ADRs** for:
   - OS instance catalog format (ADR 0065?)
   - Compiler capability derivation (ADR 0066?)
   - Service-device validation engine (ADR 0067?)
5. **Plan implementation sprints** for phases 1-5
