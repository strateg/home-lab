# ADR 0064: OS Taxonomy - Object Property Model

**Date:** 2026-03-08
**Status:** Proposed
**Extends:** ADR 0062 (Topology v5 - Modular Class-Object-Instance Architecture)

---

## Context

The v5 topology model uses `Class -> Object -> Instance` semantics with capability-based feature declaration. Operating systems (OS) are fundamental to infrastructure modeling but currently lack a consistent taxonomy.

### Current State Analysis

OS modeling is inconsistent across object modules:

1. **Explicit OS section** (MikroTik):
   ```yaml
   software:
     os:
       vendor: mikrotik
       name: RouterOS
       version: v7
       architecture: arm64
   ```

2. **Vendor capability encoding** (Proxmox LXC, OrangePi):
   ```yaml
   vendor_capabilities:
     - vendor.debian.bookworm.base
   ```

3. **Implicit through class** (services):
   - Service classes assume Linux base without explicit OS declaration

### Problem Statement

- No canonical OS schema for objects
- OS constraints for services (e.g., "requires Debian 12") are not enforceable
- Container runtime compatibility (systemd vs init) is implicit
- Package manager assumptions are undocumented

### Options Evaluated

| Option | Description | Verdict |
|--------|-------------|---------|
| A | OS as Class | Rejected - OS is not deployable, violates Class semantics |
| B | OS as Capability Domain | Partial - loses structured properties |
| C | OS as Object Property + Derived Capabilities | **Recommended** |

---

## Decision

### 1. OS Is an Object Property, Not a Class

Operating systems are **properties of objects**, not deployable entities. The OS does not get its own class; instead, objects declare their OS through a structured `os` property.

### 2. Canonical OS Property Schema

All objects with operating systems MUST declare `os` under `software`:

```yaml
software:
  os:
    family: linux | bsd | windows | routeros | proprietary
    distribution: debian | ubuntu | alpine | fedora | nixos | routeros | openwrt | null
    release: "12" | "22.04" | "3.18" | "7.x" | null
    codename: bookworm | jammy | null
    architecture: x86_64 | arm64 | armhf | riscv64
    init_system: systemd | openrc | sysvinit | busybox | proprietary | null
    package_manager: apt | apk | dnf | nix | opkg | null | none
    kernel: linux | bsd | nt | proprietary
    eol_date: "2028-06-30" | null  # ISO 8601 date
```

#### Required Fields

| Field | Required | Default | Description |
|-------|----------|---------|-------------|
| `family` | Yes | - | OS family (linux, bsd, windows, routeros, proprietary) |
| `architecture` | Yes | - | CPU architecture |
| `distribution` | No | null | Distribution name |
| `release` | No | null | Version/release identifier |
| `codename` | No | null | Release codename |
| `init_system` | No | null | Init system (derived if null) |
| `package_manager` | No | null | Package manager (derived if null) |
| `kernel` | No | derived | Kernel type (derived from family) |
| `eol_date` | No | null | End of life date |

### 3. Derived Capability Rules

The compiler MUST derive OS capabilities from `software.os` properties:

```text
os.family = linux           -> cap.os.linux
os.distribution = debian    -> cap.os.debian
os.release = 12             -> cap.os.debian.12
os.init_system = systemd    -> cap.os.init.systemd
os.package_manager = apt    -> cap.os.pkg.apt
os.architecture = arm64     -> cap.arch.arm64
```

#### Derivation Matrix

| Property | Derived Capability | Example |
|----------|-------------------|---------|
| `family: linux` | `cap.os.linux` | Linux base |
| `family: bsd` | `cap.os.bsd` | BSD base |
| `distribution: debian` | `cap.os.debian` | Debian family |
| `distribution: alpine` | `cap.os.alpine` | Alpine Linux |
| `distribution: routeros` | `cap.os.routeros` | MikroTik RouterOS |
| `release: "12"` (debian) | `cap.os.debian.12` | Debian 12 |
| `codename: bookworm` | `cap.os.debian.bookworm` | Alias for 12 |
| `init_system: systemd` | `cap.os.init.systemd` | Systemd init |
| `init_system: openrc` | `cap.os.init.openrc` | OpenRC init |
| `package_manager: apt` | `cap.os.pkg.apt` | APT package manager |
| `package_manager: apk` | `cap.os.pkg.apk` | Alpine APK |
| `architecture: arm64` | `cap.arch.arm64` | ARM64 arch |
| `architecture: x86_64` | `cap.arch.x86_64` | x86-64 arch |

### 4. OS Capability Namespace

New capability namespace for OS-derived capabilities:

```text
cap.os.<family>                      # OS family
cap.os.<distribution>                # Distribution
cap.os.<distribution>.<release>      # Distribution + release
cap.os.init.<init_system>            # Init system
cap.os.pkg.<package_manager>         # Package manager
cap.arch.<architecture>              # CPU architecture
```

### 5. Service-to-Workload OS Compatibility

Services MAY declare OS requirements in `requires`:

```yaml
# class.service.database
requires:
  os:
    - cap.os.linux
    - cap.os.init.systemd

# Service can declare distribution preference
# class.service.postgresql
requires:
  os:
    - cap.os.debian | cap.os.ubuntu | cap.os.alpine
```

The compiler validates that the target workload's derived OS capabilities satisfy service requirements.

### 6. Inference Rules for Init System and Package Manager

When `init_system` or `package_manager` are null, the compiler SHOULD infer:

| Distribution | Default init_system | Default package_manager |
|--------------|---------------------|-------------------------|
| debian | systemd | apt |
| ubuntu | systemd | apt |
| alpine | openrc | apk |
| fedora | systemd | dnf |
| nixos | systemd | nix |
| routeros | proprietary | none |
| openwrt | busybox | opkg |

### 7. Object Module Migration

Existing objects SHOULD add explicit `software.os` section:

**Before (implicit via vendor capability):**
```yaml
id: obj.proxmox.lxc.debian12.base
vendor_capabilities:
  - vendor.debian.bookworm.base
```

**After (explicit OS property):**
```yaml
id: obj.proxmox.lxc.debian12.base
software:
  os:
    family: linux
    distribution: debian
    release: "12"
    codename: bookworm
    architecture: x86_64
    init_system: systemd
    package_manager: apt
    eol_date: "2028-06-30"
```

The `vendor.debian.bookworm.base` capability is deprecated in favor of derived `cap.os.debian.12`.

---

## Consequences

### Positive

1. Consistent OS modeling across all object types
2. Enforceable service-to-workload OS compatibility checks
3. Clear derivation rules for capability generation
4. Structured data enables automated compliance checks (EOL dates)
5. Init system and package manager are explicitly modeled

### Trade-offs

1. Requires migration of existing objects to add `software.os`
2. Compiler must implement derivation rules
3. Slight increase in object module verbosity

### Migration Path

1. Add `software.os` schema to object module validator
2. Update existing objects with explicit OS properties
3. Implement capability derivation in compiler
4. Deprecate `vendor.<distro>.*` OS capabilities
5. Add service OS requirement validation

---

## References

- ADR 0062: Topology v5 - Modular Class-Object-Instance Architecture
- Object modules: `v5/topology/object-modules/`
- Capability catalog: `v5/topology/class-modules/capability-catalog.yaml`
