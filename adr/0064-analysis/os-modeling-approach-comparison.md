# OS Modeling Approaches: Class vs Property Model

**Date:** 2026-03-08  
**Purpose:** Analysis of two OS modeling paradigms for flexible device-OS binding

---

## Overview

Current ADR 0064 models OS as a **property** (`software.os` + `prerequisites.os_ref`).  
Alternative proposal: Model OS as a **first-class object** with explicit relationships.

This document compares both approaches across several dimensions.

---

## Device Classification

All devices fall into two categories:

### 1. **OS-Bearing Devices** (compute, router, appliance)
- Run an operating system
- OS can be installable or firmware-based
- OS selection affects service/workload compatibility
- Examples: VM, physical server, router, NAS, IoT device with Linux

### 2. **OS-Less Devices** (passive, infrastructure)
- No OS concept (e.g., power distribution unit, patch panel, optical switch)
- Not subject to OS constraints
- Examples: PDU, UPS, passive switch, storage shelf

---

## OS Installation Models

Operating systems can exist in two forms:

### A. **Firmware-Based OS** (immutable, hardware-locked)
- Prewired into the device at manufacturing
- Examples:
  - Router firmware (OpenWrt, RouterOS)
  - Appliance firmware (Proxmox, TrueNAS proprietary variants)
  - IoT/embedded devices
  - Smart switches with embedded management OS
- **Characteristics:**
  - Fixed to hardware SKU
  - Version tied to hardware lifecycle
  - Not independently installable (or very restricted)
  - Often cannot be changed without specialized tools
  - Vendor controls release schedule

### B. **Installable OS** (flexible, host-provided)
- Installed independently of hardware
- Examples:
  - VM guest OS (Debian, Ubuntu, Alpine)
  - LXC container filesystem
  - Cloud instance image (AMI, Compute Engine image)
  - Bare-metal Linux via PXE/netinstall
  - WSL2 container
- **Characteristics:**
  - Decoupled from hardware specifics
  - User/admin controls installation
  - Bootloader can select different OS versions
  - Can be replaced/upgraded independently
  - Standardized distribution channels

---

## Approach 1: Property Model (Current ADR 0064)

### Model Structure

```
object (e.g., vm, router, appliance)
  ├─ software.os
  │  ├─ family: linux | windows | routeros
  │  ├─ distribution: debian | alpine | routeros
  │  ├─ release: "12" | "3.19"
  │  ├─ init_system: systemd | openrc
  │  └─ package_manager: apt | apk
  └─ prerequisites
     └─ os_ref: obj.os.debian.12.generic
```

### Advantages (✓)

1. **Minimal schema complexity**
   - OS is just a structured property section
   - No additional entity types needed
   - Straightforward YAML serialization

2. **Clear ownership**
   - OS facts are explicitly owned by the device object
   - Single source of truth per device
   - No cross-references to resolve

3. **Tight device-OS binding**
   - Device and its OS are inseparable in the model
   - Matches physical reality for firmware devices
   - Makes inheritance/specialization intuitive

4. **Inference-friendly**
   - Can infer missing OS fields from distribution
   - Validation happens at object level
   - Capability derivation is straightforward

5. **Query simplicity**
   - "What OS does device X have?" → Direct property access
   - No join operations needed
   - Easy to filter devices by OS

6. **Backward compatibility**
   - Fits naturally into existing `software.*` sections
   - Can coexist with other software properties
   - Migration from vendor markers is additive

### Disadvantages (✗)

1. **OS Heterogeneity Hidden**
   - Installable and firmware OS use same schema
   - No structural difference between mutable and immutable
   - Mixing concerns: what is invariant vs. what varies

2. **Multi-OS Devices Not Elegant**
   - Device with dual-boot or multiple partitions doesn't fit
   - Would need array syntax (breaking change)
   - "Primary OS" concept becomes implicit

3. **OS Decoupling From Build Logic Difficult**
   - If OS is a property, build process is object-focused
   - Hard to ask: "What devices can run Debian 12?"
   - Requires reverse query logic

4. **Firmware vs. Installable Ambiguity**
   - Schema doesn't distinguish immutable firmware from installable OS
   - "Is this OS locked to hardware?" not obvious
   - Operators must use convention/documentation

5. **OS Lifecycle Decoupled From Class**
   - OS policy (`os_policy`) must be enforced at class level
   - Mismatch: some objects inherit multiple policies
   - Inheritance chains make policy enforcement complex

6. **Prerequisite References Can Drift**
   - `os_ref` is a string reference, not a structured dependency
   - No compile-time guarantee that referenced OS object exists
   - Dangling references possible

7. **Service Requirements Indirect**
   - Service says: "I need Debian 12 with systemd"
   - Compiler must resolve: service → capabilities → device.software.os
   - Three-level indirection for validation

---

## Approach 2: Class Model (Alternative Proposal)

### Model Structure

```
classes/
  ├─ os/
  │  ├─ os-class.yaml
  │  └─ instances/
  │     ├─ debian-12-generic.yaml
  │     ├─ debian-12-hardened.yaml
  │     ├─ alpine-3-19.yaml
  │     └─ routeros-7-firmware.yaml
  │
  ├─ compute/
  │  ├─ vm.yaml
  │  └─ physical-server.yaml
  │
  └─ router/
     ├─ mikrotik-rb3011.yaml
     └─ instances/
        ├─ mikrotik-rb3011-routeros-7.yaml
        └─ mikrotik-rb3011-routeros-6-legacy.yaml

object (e.g., my-kvm-vm1)
  ├─ class: compute.vm
  └─ bindings:
     └─ os: obj.os.debian.12.generic
```

### Class Definition Example

```yaml
# os-class.yaml
name: os
categories: [infrastructure, prerequisite]

properties:
  family: {required: true, enum: [linux, bsd, windows, routeros, proprietary]}
  distribution: {required: true}
  release: {required: true}
  release_id: {required: true}
  codename: {optional: true}
  architecture: {required: true}
  init_system: {optional: true}
  package_manager: {optional: true}
  
  # Key addition: explicit installation model
  installation_model: 
    required: true
    enum: [firmware, installable]
    description: "Immutable firmware or user-installable OS"
  
  # Firmware-specific
  firmware_locked_to_hardware: {optional: true, type: bool}
  vendor_locked_release: {optional: true, type: bool}
  
  # Installable-specific
  supports_multiboot: {optional: true, type: bool}
  supports_live_boot: {optional: true, type: bool}
  base_image_format: {optional: true, enum: [qcow2, ova, ami, rootfs, iso]}

capabilities:
  - cap.infrastructure.prerequisite
  - cap.os.{family}
  - cap.os.{distribution}
  - cap.os.{release_id}
  - cap.os.init.{init_system}
  - cap.os.pkg.{package_manager}
  - cap.arch.{architecture}
```

### Device Binding

```yaml
# compute/vm.yaml
name: compute.vm

properties:
  hypervisor: {required: true}
  vcpu_count: {required: true}
  memory_gb: {required: true}

bindings:
  os: {required: true, class: os}

os_expectations:
  categories: [installable]  # VM must use installable OS
  installation_models: [installable]  # Reject firmware
  supports_multiboot: false  # Expect single boot
```

```yaml
# router/mikrotik-rb3011.yaml
name: router.mikrotik_rb3011

properties:
  ports: {value: 10}
  memory_mb: {value: 512}

bindings:
  os: {required: true, class: os}

os_expectations:
  categories: [firmware]  # RouterOS firmware bound to hardware
  installation_models: [firmware]
  vendor_locked_release: true  # Cannot change RouterOS release independently
```

### Advantages (✓)

1. **Explicit Installation Model**
   - `installation_model: firmware|installable` is part of schema
   - Clear distinction: what's mutable vs. immutable
   - Firmware vs. installable are structurally different

2. **OS as First-Class Entity**
   - OS has its own lifecycle, versioning, and deprecation path
   - Can define OS-level policies independently
   - OS capabilities are derived from OS class, not device

3. **Multi-OS Devices Natural**
   - Device can have multiple OS bindings: `bindings: [os_primary, os_secondary, os_live_boot]`
   - Dual-boot, multipass systems fit naturally
   - No schema extension needed

4. **Strong Typing and References**
   - `bindings.os` is a structured reference to an OS class instance
   - Compiler can validate: "Does this OS instance exist?"
   - No dangling reference risk

5. **Device-OS Decoupling**
   - Devices declare requirements, not assumptions
   - OS objects exist independently
   - "What devices can use Debian 12?" is a forward query

6. **Service-to-Device Validation Simplified**
   - Service requires: `[cap.os.debian, cap.os.init.systemd]`
   - Device binds: `obj.os.debian.12.generic`
   - Compiler derives device capabilities from bound OS
   - Direct 2-level resolution

7. **Inheritance and Specialization**
   - Base VM OS: `obj.os.debian.12.generic`
   - Specialized variant: `obj.os.debian.12.hardened` (inherits base, adds security layer)
   - Router with firmware: single instance per hardware revision
   - Natural polymorphism

8. **Build and Provisioning Logic Cleaner**
   - Provisioning system: "Assign Debian 12 to VM" → bind to OS class
   - Build system: "Generate Terraform for Debian 12 VMs" → query OS class
   - Infrastructure-as-Code benefits from explicit OS objects

9. **Future Extensibility**
   - Add OS-level metadata: vendor support window, security patches, EOL
   - OS-level constraints: "This Debian variant requires x86_64"
   - OS composition: "Debian 12 + hardening profile + custom kernel"
   - All handled at OS class, not propagated to every device

10. **Audit and Compliance**
    - Enumerate all OS versions in use (query OS class instances)
    - Track which devices use which OS variant
    - EOL warnings at OS level, auto-cascade to bound devices

### Disadvantages (✗)

1. **Schema and Model Complexity**
   - Additional entity type: OS class
   - New relationship type: device ↔ OS binding
   - Compiler must resolve bindings at validation time
   - More indirection in generated code

2. **Reference Brittleness (if not careful)**
   - String references still possible if not enforced
   - Must use compiled binding resolution to prevent dangling refs
   - Tooling complexity increases

3. **Class Proliferation Risk**
   - Each OS variant becomes a class instance
   - Debian 12 generic, Debian 12 hardened, Debian 12 minimal = 3 instances
   - Inventory can grow large without discipline

4. **YAML Verbosity**
   - Device definition now must include OS binding section
   - Vs. property model: just nest under `software:`
   - Not dramatically worse, but noticeable

5. **Backward Incompatibility**
   - Existing `software.os` sections cannot auto-migrate
   - Requires migration tooling
   - Transition period with dual-mode support needed

6. **Class Naming and Discovery**
   - How to name OS class instances? `obj.os.debian.12.generic` vs. `obj.os.debian-12-generic`
   - Discovery must be clear: "What OS instances are available?"
   - Need catalog/manifest explicit listing

7. **Tight Coupling in Some Cases**
   - Firmware OS is inherently bound to hardware
   - Class model implies looser coupling (good in general)
   - For firmware, the tight coupling was actually correct
   - May need special markers for firmware OSes

8. **Tool Ecosystem Must Adapt**
   - YAML generation tools must know about OS bindings
   - Provisioning tools must query OS class
   - Validation checkers more complex
   - IDE auto-completion, linting, all need updates

9. **Simpler Queries Become Slightly Harder**
   - "What OS does device X have?" → resolve binding → read OS object
   - vs. property model: direct access
   - Still fast, but requires compilation phase

---

## Hybrid Model: Class + Policy

### Concept

Keep OS as a class, but allow:
1. **Firmware OS instances** → locked to device class (tight coupling)
2. **Installable OS instances** → standalone, referenced by devices (loose coupling)

```yaml
# firmware-routeros.yaml (tightly bound)
class: os.firmware
hardware_sku: "vendor.mikrotik.rb3011"
installation_model: firmware
firmware_locked: true
# This OS instance is published only in the router.mikrotik-rb3011 class
```

```yaml
# debian-12.yaml (standalone)
class: os.installable
installation_model: installable
# Available for any compute-type device that accepts it
```

### Advantages
- Combines clarity of both models
- Firmware OSes stay tightly coupled (reality-appropriate)
- Installable OSes stay flexible (separation-of-concerns)
- Service/workload logic simplified

### Disadvantages
- Need to classify OS instances (firmware vs. installable)
- Compiler logic more complex (two binding paths)
- Slightly more cognitive load

---

## Decision Framework

### Choose **Property Model (Current)** if:
- ✓ Simplicity and minimalism are top priority
- ✓ Most devices have single, fixed OS
- ✓ Firmware devices dominate (tight coupling is OK)
- ✓ Service-to-OS requirements are simple
- ✓ Build velocity matters more than flexibility

### Choose **Class Model** if:
- ✓ Multi-OS devices are common or anticipated
- ✓ OS lifecycle independent from device lifecycle
- ✓ Need to audit/track which devices use which OS variant
- ✓ Future composition/specialization of OS expected
- ✓ Build system must decouple OS provisioning from device definition

### Choose **Hybrid Model** if:
- ✓ Both firmware and installable OS devices are common
- ✓ Want different models for different categories
- ✓ Willing to accept moderate additional complexity

---

## Recommendation

**Suggested direction:** Move toward **Class Model with explicit `installation_model`** because:

1. Future-proofs for multi-OS and cloud-native scenarios
2. Makes firmware vs. installable distinction explicit
3. Enables strong validation and audit trails
4. Scales better for larger infrastructure

**Transition path:**
1. Phase 1: Keep property model, add `installation_model` field for classification
2. Phase 2: Define OS class structure alongside existing model
3. Phase 3: Migrate installable OS instances to class
4. Phase 4: Firmware OS instances remain property-based or get special firmware class
5. Phase 5: Deprecate property-only OS, mandate bindings

**Cost:** 2-3 ADRs, compiler refactor, migration tooling
**Benefit:** Flexible, extensible, auditable OS model for years to come
