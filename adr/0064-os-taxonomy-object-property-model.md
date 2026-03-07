# ADR 0064: OS Taxonomy - Infrastructure Prerequisite and Runtime Projection

**Date:** 2026-03-08
**Status:** Proposed
**Extends:** ADR 0062 (Topology v5 - Modular Class-Object-Instance Architecture)

---

## Context

The v5 model uses `Class -> Object -> Instance` and a capability contract (ADR 0062).
Operating system is a deployment prerequisite, similar to hardware/firmware baseline, and must be modeled as infrastructure data.

Current gaps:

1. OS is modeled inconsistently (explicit in some objects, implicit `vendor.*` markers in others).
2. Service/workload OS compatibility is not formally checkable.
3. VM/LXC and cloud workloads need an explicit OS prerequisite contract (template/image/base).
4. Init/package assumptions are implicit and drift-prone.

---

## Decision

### 1. OS Is an Infrastructure Prerequisite With Runtime Projection

OS modeling is split into two linked representations:

1. **OS prerequisite object** (source artifact/profile): reusable infrastructure baseline.
2. **Runtime OS projection** (`software.os`): effective OS facts on a concrete object.

This keeps OS in the infrastructure domain while preserving explicit runtime facts for validation and generation.

### 2. `software.os` Is Canonical Effective Contract

Objects that run an OS MUST expose canonical effective OS data:

```yaml
software:
  os:
    family: linux | bsd | windows | routeros | proprietary
    distribution: debian | ubuntu | alpine | fedora | nixos | routeros | openwrt
    release: "12" | "22.04" | "7"
    release_id: "12" | "2204" | "7"   # normalized token used in capability IDs
    codename: bookworm | jammy
    architecture: x86_64 | arm64 | armhf | riscv64 | mipsel
    init_system: systemd | openrc | sysvinit | busybox | proprietary
    package_manager: apt | apk | dnf | nix | opkg | none
    kernel: linux | bsd | nt | proprietary
    eol_date: "2028-06-30"             # ISO 8601
```

Normative rules:

1. `family` and `architecture` are required for OS-bearing objects.
2. `release_id` is required when `release` is set and MUST be normalized for IDs.
3. `kernel` defaults from `family` if omitted.
4. No OS section for objects that do not run OS (for example passive power units).

### 3. OS Prerequisite Reference (`prerequisites.os_ref`)

Objects MAY reference a reusable OS prerequisite object:

```yaml
prerequisites:
  os_ref: obj.os.debian.12.generic
```

Policy by object type:

1. **VM/LXC/cloud workload objects**: `prerequisites.os_ref` SHOULD be set (recommended as default policy).
2. **Device objects with vendor firmware (router/appliance)**: direct `software.os` is allowed without `os_ref`.
3. **OS-less objects**: `os_ref` and `software.os` are both absent.

### 4. Precedence and Conflict Rules

Effective OS is resolved as:

1. `os_ref` base OS data
2. object-local `software.os` overrides

Conflict policy:

1. Overrides are allowed only for fields expected to vary per build (for example patch release).
2. Conflicts in invariant fields (`family`, `distribution`, `architecture`) are compile errors.
3. If both `release` and `release_id` are set, they MUST represent the same normalized release token.

### 5. Derived Capabilities From Effective OS

Compiler MUST derive capabilities from effective `software.os`:

```text
family=linux             -> cap.os.linux
distribution=debian      -> cap.os.debian
release_id=12            -> cap.os.debian.12
codename=bookworm        -> cap.os.debian.bookworm (alias)
init_system=systemd      -> cap.os.init.systemd
package_manager=apt      -> cap.os.pkg.apt
architecture=arm64       -> cap.arch.arm64
```

Namespace:

```text
cap.os.<family>
cap.os.<distribution>
cap.os.<distribution>.<release_id>
cap.os.init.<init_system>
cap.os.pkg.<package_manager>
cap.arch.<architecture>
```

`cap.os.pkg.none` is valid for systems without package manager surface.

### 6. Service/Workload OS Requirements

OS requirements use structured logic under `requires.os`:

```yaml
requires:
  os:
    all:
      - cap.os.linux
      - cap.os.init.systemd
    any:
      - cap.os.debian
      - cap.os.ubuntu
      - cap.os.alpine
```

Semantics:

1. `all`: every capability MUST be present.
2. `any`: at least one capability MUST be present.
3. If `any` is absent, only `all` is evaluated.

### 7. Inference Rules

When `init_system` or `package_manager` are omitted, compiler SHOULD infer by `distribution`:

| Distribution | init_system | package_manager |
|--------------|-------------|-----------------|
| debian | systemd | apt |
| ubuntu | systemd | apt |
| alpine | openrc | apk |
| fedora | systemd | dnf |
| nixos | systemd | nix |
| routeros | proprietary | none |
| openwrt | busybox | opkg |

Explicit value wins over inferred value if not conflicting with immutable distro constraints.

### 8. Migration Contract

Phase sequence:

1. Add validator support for `software.os`, `prerequisites.os_ref`, `requires.os`.
2. Add compiler resolution and capability derivation for effective OS.
3. Migrate objects from `vendor.<distro>.*` OS markers to canonical OS model.
4. Keep compatibility warnings for legacy vendor OS markers during transition.
5. Switch legacy vendor OS markers to hard errors after migration gate completion.

---

## Consequences

### Positive

1. OS becomes explicit infrastructure prerequisite, not implicit metadata.
2. VM/LXC/cloud objects get auditable OS dependency links.
3. Service-to-runtime compatibility becomes machine-checkable.
4. Capability registry and OS taxonomy stay aligned through normalized `release_id`.

### Trade-offs

1. More schema and compiler logic.
2. Temporary dual-mode support during migration.
3. Slightly higher verbosity in object modules.

---

## References

- ADR 0062: Topology v5 - Modular Class-Object-Instance Architecture
- Object modules: `v5/topology/object-modules/`
- Manifest: `v5/topology/topology.yaml`
- Capability catalog (active via manifest): `v5/topology/class-modules/classes/router/capability-catalog.yaml`
