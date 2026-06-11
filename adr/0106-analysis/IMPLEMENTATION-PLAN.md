# ADR 0106 Implementation Plan

**Status**: Stage 1 Ready for Implementation
**Total Effort**: 20h (Stage 1)
**Analysis Date**: 2026-06-11
**Last Updated**: 2026-06-11 (post deep-analysis)

---

## Overview

### Capability Count

| Category | Count | Source |
|----------|-------|--------|
| Platform | 8 | class_ref derivation |
| Bootstrap | 4 | initialization_contract.mechanism |
| Role | 5 | enabled_capabilities |
| Vendor | 4 | vendor field |
| Workload | 3 | class_ref derivation |
| **Total** | **24** | |

### Files Classification

| Category | Files | Action |
|----------|-------|--------|
| Migrate | 9 | Refactor to use capabilities |
| Keep as-is | 3 | Structural checks (not vendor) |
| Review | 1 | docker_refs_validator.py |

---

## Stage 1: Foundation

### Wave 1: Derived Capability Compiler + Catalog (6h)

#### 1.1 Add Derived Capabilities to Catalog

**File**: `topology/class-modules/capability-catalog.yaml`

```yaml
# L7 Operations - Derived Platform Capabilities
cap.platform:
  proxmox:
    description: Proxmox VE hypervisor platform
    derived_from:
      - class_ref: "class.compute.hypervisor.proxmox"
  routeros:
    description: MikroTik RouterOS platform
    derived_from:
      - class_ref: "class.network.router.mikrotik"
  openwrt:
    description: OpenWRT platform
    derived_from:
      - class_ref: "class.network.router.glinet"
  debian:
    description: Debian-based Linux platform
    derived_from:
      - class_ref: "class.compute.edge_node"
  # Additional platforms (from deep analysis)
  vbox:
    description: VirtualBox hypervisor platform
    derived_from:
      - class_ref: "class.compute.hypervisor.vbox"
  hyperv:
    description: Hyper-V hypervisor platform
    derived_from:
      - class_ref: "class.compute.hypervisor.hyperv"
  vmware:
    description: VMware hypervisor platform
    derived_from:
      - class_ref: "class.compute.hypervisor.vmware"
  xen:
    description: Xen hypervisor platform
    derived_from:
      - class_ref: "class.compute.hypervisor.xen"

# L7 Operations - Derived Bootstrap Capabilities
cap.bootstrap:
  cloud_init:
    description: Cloud-init bootstrap mechanism
    derived_from:
      - initialization_contract.mechanism: "cloud_init"
  netinstall:
    description: MikroTik netinstall bootstrap
    derived_from:
      - initialization_contract.mechanism: "netinstall"
  unattended:
    description: Unattended install bootstrap
    derived_from:
      - initialization_contract.mechanism: "unattended_install"
  manual:
    description: Manual bootstrap (no automation)
    derived_from:
      - initialization_contract.mechanism: "manual"

# L7 Operations - Derived Role Capabilities
cap.role:
  hypervisor:
    description: Hypervisor host role
    derived_from:
      - enabled_capabilities: "cap.compute.host.hypervisor"
  router:
    description: Network router role
    derived_from:
      - enabled_capabilities: "cap.network.routing.core"
  edge_node:
    description: Edge compute node role
    derived_from:
      - enabled_capabilities: "cap.compute.node.edge"
  vpn_endpoint:
    description: VPN endpoint role
    derived_from:
      - enabled_capabilities: "cap.network.vpn.wireguard.endpoint"
  container_host:
    description: Container runtime host role
    derived_from:
      - enabled_capabilities: "cap.compute.runtime.container_host"

# L7 Operations - Derived Vendor Capabilities
cap.vendor:
  proxmox:
    description: Proxmox vendor
    derived_from:
      - vendor: "proxmox"
  mikrotik:
    description: MikroTik vendor
    derived_from:
      - vendor: "mikrotik"
  orangepi:
    description: Orange Pi vendor
    derived_from:
      - vendor: "orangepi"
  oracle:
    description: Oracle Cloud vendor
    derived_from:
      - vendor: "oracle"

# L7 Operations - Derived Workload Capabilities (from deep analysis)
cap.workload:
  vm:
    description: Virtual machine workload
    derived_from:
      - class_ref: "class.compute.workload.vm"
  lxc:
    description: LXC container workload
    derived_from:
      - class_ref: "class.compute.workload.lxc"
  container:
    description: Docker/OCI container workload
    derived_from:
      - class_ref: "class.compute.workload.container"
```

#### 1.2 Create Derived Capability Compiler

**File**: `topology-tools/plugins/compilers/derived_capability_compiler.py`

```python
"""
Derived Capability Compiler (ADR 0106)

Automatically derives capabilities from object metadata:
- class_ref → cap.platform.*
- initialization_contract.mechanism → cap.bootstrap.*
- enabled_capabilities → cap.role.*
- vendor → cap.vendor.*
"""

DERIVATION_RULES = [
    # Platform from class_ref
    {"source": "class_ref", "pattern": "class.compute.hypervisor.proxmox", "derives": "cap.platform.proxmox"},
    {"source": "class_ref", "pattern": "class.compute.hypervisor.vbox", "derives": "cap.platform.vbox"},
    {"source": "class_ref", "pattern": "class.compute.hypervisor.hyperv", "derives": "cap.platform.hyperv"},
    {"source": "class_ref", "pattern": "class.compute.hypervisor.vmware", "derives": "cap.platform.vmware"},
    {"source": "class_ref", "pattern": "class.compute.hypervisor.xen", "derives": "cap.platform.xen"},
    {"source": "class_ref", "pattern": "class.network.router.mikrotik", "derives": "cap.platform.routeros"},
    {"source": "class_ref", "pattern": "class.network.router.glinet", "derives": "cap.platform.openwrt"},
    {"source": "class_ref", "pattern": "class.compute.edge_node", "derives": "cap.platform.debian"},

    # Bootstrap from initialization_contract
    {"source": "initialization_contract.mechanism", "pattern": "cloud_init", "derives": "cap.bootstrap.cloud_init"},
    {"source": "initialization_contract.mechanism", "pattern": "netinstall", "derives": "cap.bootstrap.netinstall"},
    {"source": "initialization_contract.mechanism", "pattern": "unattended_install", "derives": "cap.bootstrap.unattended"},
    {"source": "initialization_contract.mechanism", "pattern": "manual", "derives": "cap.bootstrap.manual"},

    # Workload from class_ref
    {"source": "class_ref", "pattern": "class.compute.workload.vm", "derives": "cap.workload.vm"},
    {"source": "class_ref", "pattern": "class.compute.workload.lxc", "derives": "cap.workload.lxc"},
    {"source": "class_ref", "pattern": "class.compute.workload.container", "derives": "cap.workload.container"},
]

def derive_capabilities(obj: dict) -> set[str]:
    """Apply derivation rules and return set of derived capabilities."""
    derived = set()

    for rule in DERIVATION_RULES:
        source_path = rule["source"].split(".")
        value = obj
        for key in source_path:
            value = value.get(key, {}) if isinstance(value, dict) else None
            if value is None:
                break

        if value == rule["pattern"]:
            derived.add(rule["derives"])

    # Vendor-based derivation (dynamic)
    vendor = obj.get("vendor")
    if vendor:
        derived.add(f"cap.vendor.{vendor}")

    return derived

def run(ctx):
    """Compiler plugin entry point."""
    for obj in ctx.objects.values():
        derived = derive_capabilities(obj)
        if derived:
            existing = set(obj.get("derived_capabilities", []))
            obj["derived_capabilities"] = list(existing | derived)
```

---

### Wave 2: Capability Accessor Helpers (2h)

**File**: `topology-tools/plugins/generators/capability_helpers.py`

Add functions:

```python
def get_all_capabilities(obj: dict) -> set[str]:
    """
    Return all capabilities for object including:
    - enabled_capabilities
    - operations_capabilities
    - vendor_capabilities
    - derived_capabilities (from ADR 0106)
    """
    caps = set()
    caps.update(obj.get("enabled_capabilities", []))
    caps.update(obj.get("operations_capabilities", []))
    caps.update(obj.get("vendor_capabilities", []))
    caps.update(obj.get("derived_capabilities", []))
    return caps


def has_capability(obj: dict, cap: str) -> bool:
    """Check if object has specified capability."""
    return cap in get_all_capabilities(obj)


def filter_by_capability(objects: list[dict], cap: str) -> list[dict]:
    """Return objects that have specified capability."""
    return [obj for obj in objects if has_capability(obj, cap)]


def group_by_capability_prefix(objects: list[dict], prefix: str) -> dict[str, list[dict]]:
    """
    Group objects by capability prefix.

    Example:
        group_by_capability_prefix(devices, "cap.bootstrap.")
        # Returns: {
        #   "cap.bootstrap.cloud_init": [...],
        #   "cap.bootstrap.netinstall": [...],
        # }
    """
    groups: dict[str, list[dict]] = {}
    for obj in objects:
        for cap in get_all_capabilities(obj):
            if cap.startswith(prefix):
                if cap not in groups:
                    groups[cap] = []
                groups[cap].append(obj)
    return groups


def get_platform_type(obj: dict) -> str | None:
    """
    Return platform type from derived capabilities.

    Returns: "proxmox", "routeros", "openwrt", "debian", or None
    """
    caps = get_all_capabilities(obj)
    if "cap.platform.proxmox" in caps:
        return "proxmox"
    elif "cap.platform.routeros" in caps:
        return "mikrotik"
    elif "cap.platform.openwrt" in caps:
        return "openwrt"
    elif "cap.platform.debian" in caps:
        return "debian"
    return None
```

---

### Wave 3: Generator Refactoring (6h)

#### 3.1 bootstrap_projections.py

**Before**:
```python
proxmox_nodes = [d for d in devices if d.get("object_ref", "").startswith("obj.proxmox")]
mikrotik_nodes = [d for d in devices if d.get("object_ref", "").startswith("obj.mikrotik")]
orangepi_nodes = [d for d in devices if d.get("object_ref", "").startswith("obj.orangepi")]
```

**After**:
```python
from .capability_helpers import group_by_capability_prefix, filter_by_capability

# Primary: capability-driven grouping
bootstrap_groups = group_by_capability_prefix(devices, "cap.bootstrap.")

# Legacy aliases for backward compatibility
proxmox_nodes = bootstrap_groups.get("cap.bootstrap.unattended", [])
mikrotik_nodes = bootstrap_groups.get("cap.bootstrap.netinstall", [])
orangepi_nodes = bootstrap_groups.get("cap.bootstrap.cloud_init", [])
```

#### 3.2 wireguard_generator.py

**Before** (lines 410-433):
```python
def _get_platform_type(self, object_ref: str) -> str:
    if "mikrotik" in object_ref.lower():
        return "mikrotik"
    elif "proxmox" in object_ref:
        return "proxmox"
    elif "orangepi" in object_ref:
        return "orangepi"
    elif "oracle" in object_ref:
        return "oracle"
    return "linux"
```

**After**:
```python
from .capability_helpers import get_platform_type

def _get_platform_type(self, obj: dict) -> str:
    platform = get_platform_type(obj)
    return platform if platform else "linux"
```

#### 3.3 projections.py

**Before** (lines 155-160):
```python
CAPABILITY_ROLE_MAP = {
    "cap.network.routing.core": "router",
}
```

**After**:
```python
CAPABILITY_ROLE_MAP = {
    # Platform-based roles
    "cap.platform.proxmox": "hypervisor",
    "cap.platform.routeros": "router",
    "cap.platform.debian": "server",

    # Capability-based roles (existing)
    "cap.network.routing.core": "router",
    "cap.compute.host.hypervisor": "hypervisor",
    "cap.compute.node.edge": "edge_node",
    "cap.compute.runtime.container_host": "container_host",
    "cap.network.vpn.wireguard.endpoint": "vpn_endpoint",
}
```

---

### Wave 4: Validator Refactoring (4h)

#### 4.1 hypervisor_execution_model_validator.py

**Before**:
```python
if obj.get("class_ref") == "class.compute.hypervisor.proxmox":
    # validate
```

**After**:
```python
from topology_tools.plugins.generators.capability_helpers import has_capability

if has_capability(obj, "cap.platform.proxmox"):
    # validate
```

#### 4.2 router_port_validator.py

**Before**:
```python
if object_ref.startswith("obj.mikrotik.") or object_ref.startswith("obj.glinet."):
    # validate router ports
```

**After**:
```python
from topology_tools.plugins.generators.capability_helpers import has_capability

if has_capability(obj, "cap.platform.routeros") or has_capability(obj, "cap.platform.openwrt"):
    # validate router ports
```

#### 4.3-4.6 Other Validators

Apply same pattern:
- `volume_format_compat_validator.py`: Replace `_HYPERVISOR_FORMAT_COMPAT` dict keys with capability checks
- `vm_hypervisor_compat_validator.py`: Replace `_DEFAULT_ALLOWED_*` with capability-based lookup
- `vm_refs_validator.py`: Replace `platform != "proxmox"` with `not has_capability()`
- `lxc_refs_validator.py`: Same pattern

---

### Wave 5: Backward Compatibility Aliases (2h)

**File**: `topology-tools/plugins/generators/projections.py`

Add legacy alias mappings:

```python
# Legacy compatibility aliases (ADR 0106 Stage 1)
# These map old projection names to capability-based groups
LEGACY_PROJECTION_ALIASES = {
    "proxmox_nodes": "cap.bootstrap.unattended",
    "mikrotik_nodes": "cap.bootstrap.netinstall",
    "orangepi_nodes": "cap.bootstrap.cloud_init",
    "oracle_nodes": "cap.bootstrap.cloud_init",
}

def get_legacy_projection(objects: list[dict], alias: str) -> list[dict]:
    """Get objects using legacy projection name."""
    cap = LEGACY_PROJECTION_ALIASES.get(alias)
    if cap:
        return filter_by_capability(objects, cap)
    return []
```

---

## Stage 2: Generator Redesign (Future ADR)

### Scope (to be detailed in separate ADR)

1. **Unified dispatch architecture**
   - Single generator entry point
   - Capability matrix for template selection
   - No per-vendor generator classes

2. **Template capability matrix**
   - Templates declare required capabilities
   - Runtime matches objects to templates

3. **Full legacy pattern removal**
   - Remove all `LEGACY_PROJECTION_ALIASES`
   - Remove backward compat code
   - Clean capability-only API

---

## Acceptance Criteria

### Stage 1 Gates

| Gate | Criterion | Verification |
|------|-----------|--------------|
| G1 | Derived capabilities appear in compiled output | `grep "derived_capabilities" .state/compiled-topology.json` |
| G2 | `has_capability()` returns correct results | Unit tests |
| G3 | All 12 files migrated | Code review |
| G4 | No regression in generated outputs | Diff test |
| G5 | Legacy aliases work | Integration test |

### Testing Strategy

1. **Unit tests**: `tests/unit/test_capability_helpers.py`
2. **Integration tests**: `tests/plugin_integration/test_derived_capabilities.py`
3. **Diff test**: Compare generated outputs before/after migration

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Capability not derived correctly | Add debug logging in compiler |
| Missing capability in filter | Fallback to object_ref check |
| Performance regression | Cache capabilities at compile time |

---

## Tracking

| Wave | Status | Notes |
|------|--------|-------|
| Wave 1 | Pending | - |
| Wave 2 | Pending | - |
| Wave 3 | Pending | - |
| Wave 4 | Pending | - |
| Wave 5 | Pending | - |

---

## Patterns NOT Requiring Migration

Based on deep code analysis, the following patterns should **remain as-is**:

| File | Pattern | Reason |
|------|---------|--------|
| `hypervisor_execution_model_validator.py` | `_HYPERVISOR_CLASSES` set | Uses class_ref hierarchy (structural check) |
| `volume_format_compat_validator.py` | `_HYPERVISOR_FORMAT_COMPAT` dict | Format compatibility matrix (hypervisor type data) |
| `vm_hypervisor_compat_validator.py` | `_DEFAULT_ALLOWED_*` constants | Hypervisor type defaults |

**Rationale**: These patterns check class-level structural properties, not vendor-specific object_ref strings. They define constraints that are inherent to the class hierarchy and should remain as class_ref-based checks.

---

## Dependency Graph

```
Wave 1: Foundation (catalog + compiler)
    │
    ▼
Wave 2: Capability Helpers (5 functions)
    │
    ├──────────────────┐
    │                  │
    ▼                  ▼
Wave 3: Generators    Wave 4: Validators
(3 files)             (4 files)
    │                  │
    └────────┬─────────┘
             │
             ▼
Wave 5: Backward Compat + Integration Tests
```

---

## Deep Analysis Reference

See `DETAILED-CODE-ANALYSIS.md` for:
- Line-by-line code analysis of each file
- Additional hardcoded patterns discovered
- Stage 2 recommendations
- Full risk assessment
