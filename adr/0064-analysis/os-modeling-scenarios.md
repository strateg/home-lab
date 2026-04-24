# OS Modeling: Practical Scenarios

**Date:** 2026-03-08
**Purpose:** Real-world examples comparing property and class models

---

## Scenario 1: Simple VM with Debian

### Property Model (Current)

```yaml
# v5/topology/object-modules/compute/vm-prod-web-01.yaml
name: vm-prod-web-01
class: compute.vm

properties:
  hypervisor: proxmox-01
  vcpu: 4
  memory_gb: 16
  disk_gb: 100

software:
  os:
    family: linux
    distribution: debian
    release: "12"
    release_id: "12"
    codename: bookworm
    architecture: x86_64
    init_system: systemd
    package_manager: apt

requires:
  capabilities:
    - cap.os.debian.12
    - cap.os.init.systemd
    - cap.os.pkg.apt
```

**Observations:**
- ✓ Clean, all OS data in one place
- ✓ Easy to read
- ✗ No way to share OS definition with other VMs
- ✗ If we need to create 20 Debian 12 VMs, same data duplicated 20 times

---

### Class Model (Proposed)

```yaml
# v5/topology/class-modules/os/instances/debian-12-generic.yaml
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
  supports_multiboot: false
  base_image_format: qcow2

capabilities:
  - cap.os.linux
  - cap.os.debian
  - cap.os.debian.12
  - cap.os.init.systemd
  - cap.os.pkg.apt
  - cap.arch.x86_64
```

```yaml
# v5/topology/object-modules/compute/vm-prod-web-01.yaml
name: vm-prod-web-01
class: compute.vm

properties:
  hypervisor: proxmox-01
  vcpu: 4
  memory_gb: 16
  disk_gb: 100

bindings:
  os: obj.os.debian.12.generic

requires:
  capabilities:
    - cap.os.debian.12
    - cap.os.init.systemd
    - cap.os.pkg.apt
```

**Observations:**
- ✓ OS definition reused across all Debian 12 VMs
- ✓ No duplication
- ✓ Can define multiple Debian 12 variants (hardened, minimal, etc.)
- ✗ One extra level of indirection
- ✗ 21 lines of OS definition moved elsewhere

---

## Scenario 2: Router with Firmware OS

### Property Model

```yaml
# v5/topology/object-modules/network/router-mikrotik-01.yaml
name: router-mikrotik-01
class: router.mikrotik_rb3011

properties:
  location: datacenter-01
  rack: rack-a
  position: "42u"

software:
  os:
    family: routeros
    distribution: routeros
    release: "7.1"
    release_id: "71"
    architecture: x86_64
    init_system: proprietary
    package_manager: none
    kernel: proprietary
    installation_model: firmware  # Added classification
    vendor_locked: true           # Added annotation
    vendor_locked_release: true   # Cannot change version independently
```

**Observations:**
- ✗ Added `installation_model` but still a property
- ✗ Annotations (`vendor_locked`) are conventions, not enforced
- ✗ Cannot prevent firmware OS from being treated like installable OS

---

### Class Model

```yaml
# v5/topology/class-modules/os/instances/routeros-7-firmware.yaml
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

  # Device binding constraint
  hardware_class: router.mikrotik_rb3011

capabilities:
  - cap.os.routeros
  - cap.os.routeros.7
```

```yaml
# v5/topology/class-modules/L1-foundation/router/instances/mikrotik-rb3011.yaml
name: router.mikrotik_rb3011
inherits: router

properties:
  hardware: "Mikrotik RB3011"
  ports: 10
  memory_mb: 512

bindings:
  os:
    required: true
    class: os.firmware
    hardware_specific: true
    default: obj.os.routeros-7-firmware

os_expectations:
  installation_models: [firmware]
  firmware_locked: true
  vendor_locked_release: true
```

```yaml
# v5/topology/object-modules/network/router-mikrotik-01.yaml
name: router-mikrotik-01
class: router.mikrotik_rb3011

properties:
  location: datacenter-01
  rack: rack-a
  position: "42u"

# OS binding is inherited from class definition
# Can be overridden if needed (e.g., downgrade to RouterOS 6):
#bindings:
#  os: obj.os.routeros-6-legacy
```

**Observations:**
- ✓ Class explicitly marks firmware OS (`os.firmware` vs. `os.installable`)
- ✓ RouterOS 7 is locked to this hardware model
- ✓ Cannot accidentally assign Debian to this router
- ✓ Compiler enforces: router MUST have firmware OS
- ✓ Device can inherit OS binding from class
- ✗ More files, more structure

---

## Scenario 3: VM with Choice of OS

### Property Model

**Not well supported.** Would need:

```yaml
# Option A: List (breaks schema)
software:
  os:
    - family: linux
      distribution: debian
      release: "12"
      # ... all other fields
    - family: linux
      distribution: ubuntu
      release: "22.04"
      # ... all other fields
```

Or Option B: Multiple OS properties (non-standard)

```yaml
software:
  os_debian: {family: linux, distribution: debian, ...}
  os_ubuntu: {family: linux, distribution: ubuntu, ...}
  os_default: debian
```

**Issues:**
- ✗ Schema doesn't naturally support multiple OS
- ✗ "Which OS is actually deployed?" becomes ambiguous
- ✗ Validation logic becomes custom/ad-hoc

---

### Class Model

```yaml
# v5/topology/class-modules/compute/instances/vm-flexible.yaml
name: compute.vm.flexible
inherits: compute.vm

bindings:
  os:
    required: true
    class: os.installable
    # No default - user must choose
    allowed:
      - obj.os.debian.12.generic
      - obj.os.debian.12.hardened
      - obj.os.ubuntu.22.04
      - obj.os.alpine.3.19

# Document supported combinations
validation:
  rules:
    - "architecture must match hosting hypervisor"
    - "memory_gb must be >= 1 if using ubuntu"
```

```yaml
# Instance A: Debian variant
name: vm-app-01
class: compute.vm.flexible

properties:
  hypervisor: proxmox-01
  vcpu: 4
  memory_gb: 8

bindings:
  os: obj.os.debian.12.generic

# Instance B: Ubuntu variant
name: vm-test-01
class: compute.vm.flexible

properties:
  hypervisor: proxmox-02
  vcpu: 2
  memory_gb: 4

bindings:
  os: obj.os.ubuntu.22.04

# Instance C: Alpine minimal
name: vm-edge-01
class: compute.vm.flexible

properties:
  hypervisor: proxmox-03
  vcpu: 1
  memory_gb: 2

bindings:
  os: obj.os.alpine.3.19
```

**Observations:**
- ✓ Multiple OS instances available
- ✓ Explicit choice per device
- ✓ No duplication of OS data
- ✓ Compiler can validate: "Is this OS compatible?"
- ✓ Can express "allowed OS list"

---

## Scenario 4: Service with OS Requirements

### Property Model

```yaml
# v5/topology/class-modules/service/instances/prometheus.yaml
name: service.prometheus
class: service

requires:
  capabilities:
    all:
      - cap.os.linux
      - cap.os.init.systemd
      - cap.os.pkg.apt
    any:
      - cap.os.debian
      - cap.os.ubuntu

deployment_examples:
  - "Can deploy on: Debian 12, Ubuntu 22.04 (both systemd + apt)"
  - "Cannot deploy on: Alpine (no apt), RouterOS (not Linux)"

validation_at_deploy_time:
  "Check that target VM's software.os matches all/any"
```

**Issues:**
- ✓ Requirements are clear
- ✗ Validation must be done at deploy time, not at schema level
- ✗ No compile-time guarantee
- ✗ Reverse lookup "What devices can run Prometheus?" is slow

---

### Class Model

```yaml
# v5/topology/class-modules/service/instances/prometheus.yaml
name: service.prometheus
class: service

requires:
  capabilities:
    all:
      - cap.os.linux
      - cap.os.init.systemd
      - cap.os.pkg.apt
    any:
      - cap.os.debian
      - cap.os.ubuntu

# Compiler automatically validates:
# 1. Load all service instances
# 2. For each device, load bound OS instance
# 3. Derive capabilities from OS
# 4. Check: OS capabilities ⊇ service.requires.capabilities
# 5. Report: which devices CAN run Prometheus

validation_at_compile_time:
  "Compiler builds compatibility matrix:"
  "
  Device              | Bound OS       | Compatible?
  vm-app-01           | debian-12      | ✓ (has cap.os.debian, cap.os.init.systemd, cap.os.pkg.apt)
  vm-edge-01          | alpine-3.19    | ✗ (missing cap.os.pkg.apt, missing cap.os.debian|ubuntu)
  router-mikrotik-01  | routeros-7     | ✗ (missing cap.os.linux)
  "
```

**Observations:**
- ✓ Compiler validates all device-service compatibility at schema level
- ✓ Build-time error detection, not runtime
- ✓ Automatic device discovery: "What can run Prometheus?"
- ✓ Clear, machine-checkable validation

---

## Scenario 5: OS Specialization

### Property Model

**Not supported.** Cannot have "Debian 12 with hardening" and "Debian 12 standard" as two variants.

Would need custom extensions:

```yaml
software:
  os:
    base: debian-12
    variant: hardened
    variant_properties:
      selinux_enabled: true
      apparmor_enabled: true
```

Issues:
- ✗ Non-standard pattern
- ✗ Validation logic is ad-hoc

---

### Class Model

```yaml
# Base OS
# v5/topology/class-modules/os/instances/debian-12-generic.yaml
name: debian-12-generic
class: os.installable
# ... standard Debian 12 definition

# Hardened variant
# v5/topology/class-modules/os/instances/debian-12-hardened.yaml
name: debian-12-hardened
class: os.installable
inherits: debian-12-generic

extra_properties:
  security_hardening: true
  selinux_enabled: true
  apparmor_enabled: true
  firewall_included: true

capabilities:
  - inherits: debian-12-generic
  - cap.os.hardened
  - cap.security.selinux
  - cap.security.apparmor

# Minimal variant
# v5/topology/class-modules/os/instances/debian-12-minimal.yaml
name: debian-12-minimal
class: os.installable
inherits: debian-12-generic

properties:
  base_image_format: qcow2
  image_size_gb: 5  # vs. generic 20

capabilities:
  - inherits: debian-12-generic
  - cap.os.minimal
```

```yaml
# Now instances can choose:
name: vm-secure-app
class: compute.vm
bindings:
  os: obj.os.debian.12.hardened

requires:
  capabilities:
    all:
      - cap.security.selinux

---

name: vm-resource-constrained
class: compute.vm
bindings:
  os: obj.os.debian.12.minimal

properties:
  vcpu: 1
  memory_gb: 1
```

**Observations:**
- ✓ OS variants are explicit classes
- ✓ Inheritance allows specialization
- ✓ Extra capabilities can be required
- ✓ Variants don't duplicate data
- ✓ New variants easily added

---

## Scenario 6: Multi-OS Device (Rare but Real)

### Property Model

Not supported. Would require major schema extension or custom workaround.

---

### Class Model

```yaml
# Devices that support multiple OSes (e.g., Raspberry Pi)
# v5/topology/class-modules/compute/instances/compute.arm.multiboot.yaml
name: compute.arm.multiboot
inherits: compute.base

bindings:
  os_primary: {required: true, class: os.installable}
  os_secondary: {required: false, class: os.installable}
  os_live_boot: {required: false, class: os.installable}

os_expectations:
  all_must_have:
    - cap.arch.arm64  # Or armhf
  primary_is_default: true
```

```yaml
name: rpi-edge-01
class: compute.arm.multiboot

properties:
  hardware: "Raspberry Pi 5"
  memory_gb: 8

bindings:
  os_primary: obj.os.debian.12.arm64
  os_secondary: obj.os.ubuntu.22.04.arm64
  os_live_boot: obj.os.alpine.3.19.arm64
```

**Observations:**
- ✓ Multiple OS bindings are natural
- ✓ Clear which is primary/secondary/live
- ✓ Schema supports device reality

---

## Summary: Which Model Fits Which Case

| Scenario | Property Model | Class Model |
|----------|---|---|
| Single fixed OS | ✓✓ Simple | ✓ Works well |
| Firmware device | ✓ Natural tight coupling | ✓✓ Clear distinction |
| Multiple installable variants | ~ Workaround needed | ✓✓ Natural |
| Service-device matching | ~ Runtime check only | ✓✓ Compile-time |
| OS specialization | ✗ Not supported | ✓✓ Clean inheritance |
| Multi-boot device | ✗ Not supported | ✓✓ Native |
| OS reuse across devices | ~ Manual | ✓✓ Automatic |
| Schema simplicity | ✓✓ Minimal | ~ More structure |
| Compiler complexity | ~ Simple | ✓ Moderate |

---

## Recommendation Summary

**Move to Class Model because:**

1. **Current gaps filled:**
   - Multi-OS scenarios (now supported)
   - OS reuse (automatic, no duplication)
   - Service-device compatibility (compile-time)
   - Firmware vs. installable (explicit)

2. **Future-ready:**
   - OS composition (base + layers)
   - OS lifecycle independent of device
   - Audit trails for OS versions
   - Security policies at OS level

3. **Practical benefits:**
   - Provisioning systems work with OS class
   - Compliance reporting queries OS catalog
   - New OS variants are just new instances
   - Schema is self-documenting

**Migration cost:** ~3-4 weeks for tooling + validator updates
**Long-term benefit:** 5+ years of flexibility
