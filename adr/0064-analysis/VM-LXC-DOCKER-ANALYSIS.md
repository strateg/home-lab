# ADR 0064 Analysis: Applicability to VM/LXC/Docker

**Date:** 8 March 2026  
**Analysis Type:** Virtualization and Containerization Applicability  
**Status:** Complete

---

## Executive Summary

ADR 0064's **firmware + OS** two-entity model is **directly applicable** to VMs, but requires **clarification** for LXC and **extension** for Docker.

**Key Findings:**
- ✅ **VM (KVM/Xen/VMware/Hyper-V)**: Model applies cleanly with "virtual firmware"
- ⚠️ **LXC containers**: Model applies but firmware concept is implicit (host kernel)
- ❌ **Docker containers**: Current model insufficient, needs container-specific extension

---

## 1. Virtual Machines (VM)

### 1.1 Model Applicability: ✅ FULLY APPLICABLE

VMs have **both firmware and OS**, just like physical machines:

```
Physical Machine:          Virtual Machine:
├─ BIOS/UEFI (firmware)   ├─ Virtual BIOS/UEFI (firmware)
└─ Linux/Windows (OS)     └─ Linux/Windows (OS)
```

### 1.2 Firmware in VMs

**Virtual firmware types:**
- BIOS emulation (legacy)
- UEFI/OVMF (modern)
- VMware virtual firmware
- Hyper-V Gen1/Gen2 firmware
- Xen PV (paravirtualized, minimal firmware)

**Firmware object examples:**

```yaml
# Object: KVM virtual BIOS
object: obj.firmware.kvm-bios
class_ref: class.firmware

properties:
  vendor: qemu
  family: bios
  version: "seabios-1.16.0"
  architecture: x86_64
  boot_stack: bios
  hardware_locked: false  # Can be changed by hypervisor
  vendor_locked: false
  virtual: true  # NEW: indicates virtual firmware
  
capabilities:
  - cap.firmware.qemu
  - cap.firmware.bios
  - cap.firmware.virtual
  - cap.firmware.arch.x86_64
```

```yaml
# Object: KVM OVMF (UEFI)
object: obj.firmware.kvm-ovmf
class_ref: class.firmware

properties:
  vendor: qemu
  family: uefi
  version: "edk2-ovmf-20231129"
  architecture: x86_64
  boot_stack: uefi
  hardware_locked: false
  vendor_locked: false
  virtual: true
  secure_boot_capable: true
  
capabilities:
  - cap.firmware.qemu
  - cap.firmware.uefi
  - cap.firmware.virtual
  - cap.firmware.secureboot
  - cap.firmware.arch.x86_64
```

```yaml
# Object: VMware virtual firmware
object: obj.firmware.vmware-efi
class_ref: class.firmware

properties:
  vendor: vmware
  family: uefi
  version: "efi-2.7"
  architecture: x86_64
  boot_stack: uefi
  hardware_locked: true   # VMware-specific
  vendor_locked: true
  virtual: true
```

### 1.3 OS in VMs

OS modeling is **identical** to physical machines:

```yaml
# Instance: KVM VM with Debian
instance: inst.compute.vm-app-01
object_ref: obj.compute.kvm-vm

firmware_ref: inst.firmware.kvm-ovmf-prod
os_refs:
  - inst.os.debian-12-prod
```

```yaml
# Instance: VMware VM with Windows
instance: inst.compute.vm-win-01
object_ref: obj.compute.vmware-vm

firmware_ref: inst.firmware.vmware-efi-v2.7
os_refs:
  - inst.os.windows-server-2022
```

### 1.4 Hypervisor-Specific Considerations

**Different hypervisors = different firmware profiles:**

| Hypervisor | Firmware Object | Notes |
|------------|----------------|-------|
| KVM/QEMU | kvm-bios, kvm-ovmf | Open-source, flexible |
| VMware ESXi | vmware-bios, vmware-efi | Proprietary |
| Hyper-V | hyperv-gen1, hyperv-gen2 | Gen1=BIOS, Gen2=UEFI |
| Xen | xen-pv, xen-hvm | PV has minimal firmware |
| VirtualBox | vbox-bios, vbox-efi | Oracle firmware |

### 1.5 Recommendation for VMs

✅ **No ADR changes needed.**  
✅ Add virtual firmware objects to firmware registry.  
✅ Document `virtual: true` property for firmware.

---

## 2. LXC Containers

### 2.1 Model Applicability: ⚠️ PARTIALLY APPLICABLE

LXC containers **share host kernel** but have **isolated userspace**.

**Question:** Does LXC container have "firmware" and "OS"?

**Answer:**
- **Firmware:** ❌ No. Container shares host kernel (no firmware layer of its own).
- **OS:** ⚠️ Partial. Container has OS userspace (init, package manager, filesystem) but not kernel.

### 2.2 Firmware in LXC

LXC containers do **not** have their own firmware. They inherit from host:

```
Host (Physical/VM):
├─ Firmware (BIOS/UEFI)
├─ Host OS Kernel (Linux)
└─ LXC Container
    └─ Guest OS Userspace (Debian, Ubuntu, Alpine)
```

**Firmware reference for LXC:**
- Option 1: `firmware_ref: null` (no firmware)
- Option 2: `firmware_ref: inst.firmware.host` (inherit from host)
- Option 3: Don't model firmware at all for containers

**Recommendation:** Option 3 is cleanest.

### 2.3 OS in LXC

LXC containers **do** have OS userspace:

```yaml
# Object: LXC container OS (userspace only)
object: obj.os.debian-12-lxc
class_ref: class.os

properties:
  family: linux
  distribution: debian
  release: "12"
  architecture: x86_64
  init_system: systemd  # Container init
  package_manager: apt
  kernel: shared  # NEW: shares host kernel
  installation_model: installable
  container_type: lxc  # NEW: indicates containerized OS
  
capabilities:
  - cap.os.linux
  - cap.os.debian
  - cap.os.debian.12
  - cap.os.container.lxc
  - cap.os.kernel.shared  # NEW capability
```

### 2.4 LXC Instance Example

```yaml
# Instance: LXC container
instance: inst.compute.lxc-web-01
object_ref: obj.compute.lxc-container

firmware_ref: null  # No firmware (or omit field)
os_refs:
  - inst.os.debian-12-lxc-prod

host_ref: inst.compute.host-proxmox-01  # NEW: reference to host
```

### 2.5 Recommendation for LXC

⚠️ **Minor ADR extension needed:**
1. Allow `firmware_ref: null` for containers.
2. Add `kernel: shared` property to OS class.
3. Add `container_type: lxc|docker|podman` property.
4. Add `host_ref` field for containers to link to host.

---

## 3. Docker Containers

### 3.1 Model Applicability: ❌ INSUFFICIENT

Docker containers are **NOT full OS instances**. They are:
- Application + dependencies
- Minimal filesystem (layers)
- No init system (typically)
- No package manager (typically)

**Question:** Does Docker container have "OS"?

**Answer:** ❌ **No, not in the ADR 0064 sense.**

Docker containers are **runtime environments**, not operating systems.

### 3.2 Docker vs OS: Key Differences

| Aspect | Traditional OS | Docker Container |
|--------|---------------|------------------|
| **Kernel** | Has own kernel | Shares host kernel |
| **Init system** | systemd/openrc/etc | No (single process) |
| **Package manager** | apt/dnf/apk/etc | No (build-time only) |
| **Filesystem** | Full root filesystem | Layered, minimal |
| **Boot process** | Firmware → kernel → init | Container runtime → entrypoint |
| **Multi-user** | Yes | No (single app) |
| **Services** | Multiple daemons | Single process |

### 3.3 What Docker Containers ARE

Docker containers are **runtime environments** with:
- **Base image** (alpine, debian, ubuntu, scratch)
- **Application stack** (Python, Node.js, Java)
- **Dependencies** (libraries, binaries)

```
Host:
├─ Firmware (BIOS/UEFI)
├─ Host OS (Linux kernel)
├─ Docker Engine
└─ Docker Container
    ├─ Base Image (alpine:3.19)
    ├─ Application (Python app)
    └─ Dependencies (pip packages)
```

### 3.4 Modeling Docker Containers

Docker containers should **NOT** use `os_refs`. Instead:

**Option A: New entity type `runtime`**

```yaml
# Class: runtime (NEW)
class: class.runtime
categories: [infrastructure, container]

properties:
  runtime_type: docker | podman | containerd
  base_image: string  # alpine:3.19, debian:12-slim
  language: python | nodejs | java | go | rust
  language_version: string
  
capabilities:
  - cap.runtime.{runtime_type}
  - cap.runtime.base.{base_image_name}
  - cap.runtime.lang.{language}
```

**Example:**

```yaml
# Object: Python runtime on Alpine
object: obj.runtime.python-alpine
class_ref: class.runtime

properties:
  runtime_type: docker
  base_image: alpine:3.19
  language: python
  language_version: "3.11"
  
capabilities:
  - cap.runtime.docker
  - cap.runtime.base.alpine
  - cap.runtime.lang.python
  - cap.runtime.lang.python.3.11
```

**Instance:**

```yaml
# Instance: Docker container
instance: inst.runtime.app-web-01
object_ref: obj.runtime.python-alpine

runtime_ref: inst.runtime.python-alpine-prod  # Not os_refs!
host_ref: inst.compute.docker-host-01
```

**Option B: Extend OS class with `os_type: container-runtime`**

```yaml
# Object: Docker container "OS"
object: obj.os.alpine-docker
class_ref: class.os

properties:
  family: linux
  distribution: alpine
  release: "3.19"
  os_type: container-runtime  # NEW: not full OS
  container_type: docker
  kernel: shared
  init_system: none  # No init
  package_manager: none  # No runtime package manager
  
capabilities:
  - cap.os.alpine
  - cap.os.container.docker
  - cap.os.kernel.shared
```

### 3.5 Recommendation for Docker

❌ **ADR 0064 needs significant extension for Docker:**

**Preferred approach:**
1. Create new entity class `runtime` (not `os`).
2. Docker containers reference `runtime_ref`, not `os_refs`.
3. Runtime includes base image, language, dependencies.
4. Separate ADR for container runtime taxonomy.

**Alternative approach:**
1. Extend OS class with `os_type: container-runtime`.
2. Mark as "not full OS" with constraints.
3. Simpler but conceptually confusing.

---

## 4. Summary Matrix

| Technology | Firmware | OS | ADR 0064 Applicability | Changes Needed |
|------------|----------|----|-----------------------|----------------|
| **Physical PC** | ✅ BIOS/UEFI | ✅ Full OS | ✅ Fully applicable | None |
| **VM (KVM/VMware)** | ✅ Virtual firmware | ✅ Full OS | ✅ Fully applicable | Add virtual firmware objects |
| **LXC Container** | ❌ None (shared) | ⚠️ Userspace only | ⚠️ Partially applicable | Allow `firmware_ref: null`, add `kernel: shared` |
| **Docker Container** | ❌ None (shared) | ❌ Not full OS | ❌ Not applicable | Need new `runtime` entity or extend OS |

---

## 5. Recommended Actions

### 5.1 Immediate (For VMs)

✅ **Add to ADR 0064:**
- Section on virtual firmware
- `virtual: true` property for firmware
- Examples: KVM, VMware, Hyper-V firmware objects

### 5.2 Short-term (For LXC)

⚠️ **Extend ADR 0064:**
1. Allow `firmware_ref: null` for containerized workloads.
2. Add `kernel: shared|own` property to OS class.
3. Add `container_type: lxc|systemd-nspawn` property.
4. Add `host_ref` field to link containers to hosts.
5. Add examples for LXC containers.

### 5.3 Long-term (For Docker)

❌ **Create new ADR:**
- ADR 0065: Container Runtime Taxonomy
- Define `runtime` entity (separate from `os`)
- Model base images, languages, dependencies
- Docker/Podman/containerd support

---

## 6. Example Hierarchies

### 6.1 Physical Machine
```
Physical PC
├─ Firmware: UEFI (obj.firmware.generic-uefi-x86)
└─ OS: Debian 12 (obj.os.debian-12)
```

### 6.2 Virtual Machine
```
KVM VM
├─ Firmware: Virtual OVMF (obj.firmware.kvm-ovmf)
└─ OS: Debian 12 (obj.os.debian-12)
```

### 6.3 LXC Container
```
LXC Container
├─ Firmware: (none, inherited from host)
├─ OS Userspace: Debian 12 (obj.os.debian-12-lxc)
└─ Host: Proxmox host (inst.compute.proxmox-01)
```

### 6.4 Docker Container
```
Docker Container
├─ Firmware: (none)
├─ OS: (none, not applicable)
├─ Runtime: Python on Alpine (obj.runtime.python-alpine)
└─ Host: Docker host (inst.compute.docker-host-01)
```

---

## 7. Gaps in Current ADR 0064

### 7.1 Missing Concepts

1. **Virtual firmware** - Mentioned in table but not formalized
2. **Firmware-less workloads** - LXC/Docker have no firmware
3. **Shared kernel** - Containers don't have own kernel
4. **Container runtimes** - Docker/Podman not modeled
5. **Host relationships** - No `host_ref` field

### 7.2 Unclear Constraints

1. Is `firmware_ref` always required? (Should be optional for containers)
2. Can `os_refs` be empty? (Should be yes for Docker)
3. What about nested virtualization? (VM inside VM)

---

## 8. Proposed Extensions to ADR 0064

### 8.1 Add to Firmware Class

```yaml
# Extend firmware properties
properties:
  virtual: boolean  # true for virtual firmware
  virtualization_platform: qemu | vmware | hyperv | xen | vbox
```

### 8.2 Add to OS Class

```yaml
# Extend OS properties
properties:
  kernel: own | shared  # shared for containers
  os_type: full | container-userspace | container-runtime
  container_type: lxc | docker | podman | systemd-nspawn
```

### 8.3 Add to Device/Compute Instance

```yaml
# Add optional host reference
host_ref: inst.compute.<host-instance>  # For VMs and containers
```

### 8.4 Create New Runtime Class (Future)

```yaml
class: class.runtime
# For Docker/Podman/container runtimes
# Separate from OS class
```

---

## 9. Conclusion

**ADR 0064 firmware + OS model:**

| ✅ Works well for | ⚠️ Needs extension for | ❌ Insufficient for |
|------------------|----------------------|-------------------|
| Physical machines | LXC containers | Docker containers |
| Virtual machines | systemd-nspawn | Container runtimes |
| Appliances | Nested VMs | Application stacks |

**Recommendation:**
1. ✅ Approve ADR 0064 for physical and virtual machines.
2. ⚠️ Extend ADR 0064 for LXC (minor changes).
3. ❌ Create ADR 0065 for Docker/container runtimes (major new concept).

---

**Date:** 8 March 2026  
**Status:** Analysis Complete  
**Next Step:** Update ADR 0064 with VM examples and create ADR 0065 for containers
