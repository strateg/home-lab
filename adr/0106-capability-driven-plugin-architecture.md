# ADR 0106: Capability-Driven Plugin Architecture

- Status: Proposed
- Date: 2026-06-11
- Analysis: `adr/0106-analysis/`

## Context

### Problem Statement

Current plugins contain hardcoded vendor name checks that create tight coupling between plugin logic and specific device types:

```python
# Current pattern - fragile, requires code changes for new devices
if "mikrotik" in object_ref.lower():
    return "mikrotik"
elif "proxmox" in object_ref:
    return "proxmox"
```

This violates the Infrastructure-as-Data principle: adding a new device type (e.g., Ubiquiti EdgeRouter) requires modifying plugin source code rather than simply declaring capabilities in topology.

### Affected Files

**Files to Migrate (9 files):**

| File | Pattern | Action |
|------|---------|--------|
| `bootstrap_projections.py` | `obj.mikrotik.*`, `obj.proxmox.ve` + vendor-named lists | Use `group_by_capability_prefix()` |
| `wireguard_generator.py` | `if "mikrotik" in object_ref.lower()` | Use `get_platform_type()` |
| `projections.py` | `CAPABILITY_ROLE_MAP` (only 1 entry) | Expand with platform capabilities |
| `capability_helpers.py` | Underutilized | Add 5 accessor functions |
| `vm_refs_validator.py` | `platform != "proxmox"` | Use `has_capability()` |
| `lxc_refs_validator.py` | `platform != "proxmox"` | Use `has_capability()` |
| `router_port_validator.py` | `obj.mikrotik.`, `obj.glinet.` prefixes | Use `has_capability()` |

**Files to Keep As-Is (3 files, structural checks):**

| File | Pattern | Reason |
|------|---------|--------|
| `hypervisor_execution_model_validator.py` | `_HYPERVISOR_CLASSES` set | Class hierarchy check (structural) |
| `volume_format_compat_validator.py` | `_HYPERVISOR_FORMAT_COMPAT` dict | Format compatibility matrix |
| `vm_hypervisor_compat_validator.py` | `_DEFAULT_ALLOWED_*` constants | Hypervisor type defaults |

### Root Cause

The capability system exists (`topology/class-modules/capability-catalog.yaml` with 188+ capabilities) but is underutilized. Plugins bypass capability checks and directly inspect object/class references using string matching.

## Decision

Implement **Derived Capabilities** model with **two-stage migration**.

### D1: Derived Capabilities Compiler

Add new compiler pass `derived_capability_compiler.py` that automatically derives capabilities from object metadata:

```yaml
# Derivation rules
derivation_rules:
  # Platform capabilities from class_ref
  - source: class_ref
    pattern: "class.compute.hypervisor.proxmox"
    derives: "cap.platform.proxmox"

  - source: class_ref
    pattern: "class.network.router.mikrotik"
    derives: "cap.platform.routeros"

  # Bootstrap capabilities from initialization_contract.mechanism
  - source: initialization_contract.mechanism
    pattern: "cloud_init"
    derives: "cap.bootstrap.cloud_init"

  - source: initialization_contract.mechanism
    pattern: "netinstall"
    derives: "cap.bootstrap.netinstall"

  # Vendor capabilities from vendor field
  - source: vendor
    pattern: "*"
    derives: "cap.vendor.{value}"
```

### D2: New Derived Capabilities (24 total)

```yaml
# Platform capabilities (8)
cap.platform.proxmox:    # Proxmox VE hypervisor
cap.platform.vbox:       # VirtualBox hypervisor
cap.platform.hyperv:     # Hyper-V hypervisor
cap.platform.vmware:     # VMware hypervisor
cap.platform.xen:        # Xen hypervisor
cap.platform.routeros:   # RouterOS-based routers
cap.platform.openwrt:    # OpenWRT-based routers
cap.platform.debian:     # Debian-based Linux hosts

# Bootstrap capabilities (4)
cap.bootstrap.cloud_init:     # Cloud-init mechanism
cap.bootstrap.netinstall:     # MikroTik netinstall
cap.bootstrap.unattended:     # Unattended install (Proxmox)
cap.bootstrap.manual:         # Manual bootstrap

# Role capabilities (5)
cap.role.hypervisor:     # Hypervisor host
cap.role.router:         # Network router
cap.role.edge_node:      # Edge compute node
cap.role.vpn_endpoint:   # VPN endpoint
cap.role.container_host: # Container runtime host

# Vendor capabilities (4)
cap.vendor.proxmox:      # Proxmox vendor
cap.vendor.mikrotik:     # MikroTik vendor
cap.vendor.orangepi:     # Orange Pi vendor
cap.vendor.oracle:       # Oracle Cloud vendor

# Workload capabilities (3)
cap.workload.vm:         # Virtual machine workload
cap.workload.lxc:        # LXC container workload
cap.workload.container:  # Docker/OCI container workload
```

### D3: Capability Helper Functions

Extend `capability_helpers.py` with accessor functions:

```python
def get_all_capabilities(obj: dict) -> set[str]:
    """Return all capabilities including derived ones."""

def has_capability(obj: dict, cap: str) -> bool:
    """Check if object has capability (enabled or derived)."""

def filter_by_capability(objects: list, cap: str) -> list:
    """Filter objects having specified capability."""

def group_by_capability_prefix(objects: list, prefix: str) -> dict[str, list]:
    """Group objects by capability prefix (e.g., 'cap.bootstrap.')."""
```

### D4: Two-Stage Implementation

**Stage 1: Foundation (this ADR)**
- Derived capabilities compiler
- Capability helpers
- Refactor generators to use `has_capability()`
- Refactor validators to use `filter_by_capability()`
- Backward compatibility aliases

**Stage 2: Generator Redesign (future ADR)**
- Unified generator dispatch based on capability matrix
- Template selection by capability
- Dynamic role assignment from capability→role mapping
- Full elimination of legacy patterns

### D5: Migration Pattern

Before (hardcoded):
```python
# bootstrap_projections.py
proxmox_nodes = [d for d in devices if d.get("object_ref", "").startswith("obj.proxmox")]
mikrotik_nodes = [d for d in devices if d.get("object_ref", "").startswith("obj.mikrotik")]
orangepi_nodes = [d for d in devices if d.get("object_ref", "").startswith("obj.orangepi")]
```

After (capability-driven):
```python
# bootstrap_projections.py
from .capability_helpers import group_by_capability_prefix

bootstrap_groups = group_by_capability_prefix(devices, "cap.bootstrap.")
# Returns: {
#   "cap.bootstrap.cloud_init": [...orangepi, ...oracle nodes],
#   "cap.bootstrap.netinstall": [...mikrotik nodes],
#   "cap.bootstrap.unattended": [...proxmox nodes],
# }

# Legacy aliases for backward compatibility (Stage 1)
proxmox_nodes = bootstrap_groups.get("cap.bootstrap.unattended", [])
mikrotik_nodes = bootstrap_groups.get("cap.bootstrap.netinstall", [])
orangepi_nodes = bootstrap_groups.get("cap.bootstrap.cloud_init", [])
```

### D6: Validator Migration Pattern

Before:
```python
# hypervisor_execution_model_validator.py
if obj.get("class_ref") == "class.compute.hypervisor.proxmox":
    # validate Proxmox-specific rules
```

After:
```python
from topology_tools.plugins.generators.capability_helpers import has_capability

if has_capability(obj, "cap.platform.proxmox"):
    # validate Proxmox-specific rules
```

### D7: Constraint Preservation

| Constraint | How Preserved |
|------------|---------------|
| C01: Topology = source of truth | Capabilities declared in topology, derived by compiler |
| C19: No custom systems | Uses native capability checking, no new infrastructure |
| C22: All operations via Ansible | Not affected |
| C24: Capability-driven generation | Enhanced by this ADR |

## Consequences

### Positive

1. **Extensibility**: Adding new device type requires only capability declarations in topology
2. **Maintainability**: Plugin logic becomes device-agnostic
3. **Testability**: Capability presence is easily mockable
4. **Consistency**: Single source of device classification
5. **Discovery**: Capabilities self-document device features

### Trade-offs

1. **Learning curve**: Developers must understand capability model
2. **Initial effort**: 20h migration across 9 files (3 files remain as structural checks)
3. **Two-stage process**: Full benefits require Stage 2 completion

### Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| Capability explosion | Medium | Strict namespace governance |
| Performance overhead | Low | Capabilities cached at compile time |
| Migration breakage | Medium | Backward compatibility aliases |

## Implementation Plan

### Stage 1: Foundation (20h total)

| Wave | Focus | Files | Effort |
|------|-------|-------|--------|
| Wave 1 | Derived capability compiler + catalog | 2 | 6h |
| Wave 2 | Capability accessor helpers | 1 | 2h |
| Wave 3 | Generator refactoring | 3 | 6h |
| Wave 4 | Validator refactoring | 4 | 4h |
| Wave 5 | Backward compat aliases + tests | 2 | 2h |

**Dependency graph:**
```
Wave 1 → Wave 2 → Wave 3 (parallel) → Wave 5
                → Wave 4 (parallel) ↗
```

### Stage 2: Generator Redesign (future ADR)

- Unified dispatch architecture
- Template capability matrix
- Output path normalization
- Full legacy pattern removal

## References

- SWOT Analysis: `adr/capabilities-analysis/SWOT-CAPABILITIES.md`
- Detailed Code Analysis: `adr/0106-analysis/DETAILED-CODE-ANALYSIS.md`
- Implementation Plan: `adr/0106-analysis/IMPLEMENTATION-PLAN.md`
- Gap Analysis: `adr/0106-analysis/GAP-ANALYSIS.md`
- Capability catalog: `topology/class-modules/capability-catalog.yaml`
- ADR 0063: Plugin microkernel architecture
- ADR 0074: V5 generator architecture
- ADR 0080: Unified build pipeline
