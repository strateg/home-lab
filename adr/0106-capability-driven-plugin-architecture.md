# ADR 0106: Capability-Driven Plugin Architecture

- Status: Proposed
- Date: 2026-06-11
- Updated: 2026-06-11 (all-in approach, ontology optimization)
- Analysis: `adr/0106-analysis/`
- AI Rules: `docs/ai/rules/capability-model.md`

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

Implement **Derived Capabilities** model with **all-in approach** (no legacy fallbacks).

### Key Principles

1. **ALL-IN**: No legacy fallbacks — strict errors when capabilities are missing
2. **ONTOLOGY REUSE**: Use existing `cap.os.*` and `cap.workload.runtime.*` instead of creating duplicates
3. **STRICT ERRORS**: Emit diagnostics E8001-E8021 for missing capabilities

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

### D2: Capability Namespaces (Optimized Ontology)

**Reuse existing capabilities** (no duplicates):

| Need | Use Existing | NOT (removed) |
|------|--------------|---------------|
| Platform detection | `cap.os.routeros`, `cap.os.debian`, `cap.os.proxmox` | ~~cap.platform.*~~ |
| Workload type | `cap.workload.runtime.lxc`, `cap.workload.runtime.qemu` | ~~cap.workload.vm/lxc~~ |

**New derived capabilities (13 total):**

```yaml
# Bootstrap capabilities (4) - derived from initialization_contract.mechanism
cap.bootstrap.cloud_init:     # Cloud-init mechanism
cap.bootstrap.netinstall:     # MikroTik netinstall
cap.bootstrap.unattended:     # Unattended install (Proxmox)
cap.bootstrap.manual:         # Manual bootstrap

# Role capabilities (5) - derived from enabled_capabilities
cap.role.hypervisor:     # Hypervisor host
cap.role.router:         # Network router
cap.role.edge_node:      # Edge compute node
cap.role.vpn_endpoint:   # VPN endpoint
cap.role.container_host: # Container runtime host

# Vendor capabilities (4) - derived from vendor field
cap.vendor.proxmox:      # Proxmox vendor
cap.vendor.mikrotik:     # MikroTik vendor
cap.vendor.orangepi:     # Orange Pi vendor
cap.vendor.oracle:       # Oracle Cloud vendor
```

**Required catalog addition:**

```yaml
# Add to capability-catalog.yaml (missing)
- @capability: cap.os.proxmox
  title: Proxmox VE OS
  summary: Proxmox VE hypervisor operating system.
  domain: os
  layer: L0
  stability: stable
  derived: true
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

### D4: Strict Error Model (ALL-IN)

**No fallbacks — only errors:**

| Code | Stage | Condition | Action |
|------|-------|-----------|--------|
| E8001 | Compile | Missing `initialization_contract.mechanism` | Error: add to object |
| E8002 | Compile | Unknown mechanism value | Error: use known values |
| E8020 | Generate | Cannot detect platform from `cap.os.*` | Error: ensure OS capability |
| E8021 | Generate | Missing `cap.bootstrap.*` capability | Error: add initialization_contract |

```python
# ALL-IN: No fallback, strict error
def get_bootstrap_capability(obj: dict) -> str:
    caps = get_all_capabilities(obj)
    for cap in caps:
        if cap.startswith("cap.bootstrap."):
            return cap
    # NO FALLBACK
    raise CapabilityError(code="E8021", ...)
```

### D5: Two-Stage Implementation

**Stage 1: Foundation (this ADR)**
- Derived capabilities compiler
- Capability helpers with strict errors
- Refactor generators to use `has_capability()`
- Refactor validators to use `filter_by_capability()`
- **NO backward compatibility aliases** (all-in)

**Stage 2: Generator Redesign (future ADR)**
- Unified generator dispatch based on capability matrix
- Template selection by capability
- Dynamic role assignment from capability→role mapping

### D6: Migration Pattern (ALL-IN)

**Before (hardcoded + fallback):**
```python
# bootstrap_projections.py - REMOVE THIS
mechanism = _resolve_initialization_mechanism(row)
if mechanism == "unattended_install":
    proxmox_nodes.append(export_row)
# ... legacy fallback:
if object_ref.startswith("obj.mikrotik."):  # REMOVE
    mikrotik_nodes.append(export_row)
```

**After (capability-driven, strict):**
```python
# bootstrap_projections.py - ALL-IN
from .capability_helpers import group_by_capability_prefix

bootstrap_groups = group_by_capability_prefix(devices, "cap.bootstrap.")

# Strict: if device has no cap.bootstrap.*, it's excluded with error
for device in devices:
    caps = get_all_capabilities(device)
    if not any(c.startswith("cap.bootstrap.") for c in caps):
        ctx.emit_diagnostic(code="E8021", severity="error", ...)
```

### D7: Validator Migration Pattern

**Before:**
```python
if obj.get("class_ref") == "class.compute.hypervisor.proxmox":
    # validate
```

**After (use cap.os.*):**
```python
from .capability_helpers import has_capability

if has_capability(obj, "cap.os.proxmox"):
    # validate Proxmox-specific rules
```

### D8: Constraint Preservation

| Constraint | How Preserved |
|------------|---------------|
| C01: Topology = source of truth | Capabilities declared in topology, derived by compiler |
| C19: No custom systems | Uses native capability checking, no new infrastructure |
| C22: All operations via Ansible | Not affected |
| C24: Capability-driven generation | Enhanced by this ADR |
| **NEW C32: No legacy fallbacks** | Strict errors for missing capabilities |

## Consequences

### Positive

1. **Extensibility**: Adding new device type requires only capability declarations in topology
2. **Maintainability**: Plugin logic becomes device-agnostic
3. **Testability**: Capability presence is easily mockable
4. **Consistency**: Single source of device classification
5. **Discovery**: Capabilities self-document device features

### Trade-offs

1. **Learning curve**: Developers must understand capability model
2. **Initial effort**: 18h migration across 9 files
3. **Breaking change**: All objects MUST have `initialization_contract` (all-in)

### Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| Capability explosion | Medium | Strict namespace governance |
| Performance overhead | Low | Capabilities cached at compile time |
| Missing capabilities in objects | High | Pre-migration audit + strict errors guide fixes |

## Implementation Plan

### Stage 1: Foundation (18h total)

| Wave | Focus | Files | Effort |
|------|-------|-------|--------|
| Wave 1 | Add `cap.os.proxmox` + derived capability compiler | 2 | 5h |
| Wave 2 | Capability accessor helpers with strict errors | 1 | 2h |
| Wave 3 | Generator refactoring (remove fallbacks) | 3 | 6h |
| Wave 4 | Validator refactoring + AI rules doc | 5 | 5h |

**Dependency graph:**
```
Wave 1 → Wave 2 → Wave 3 (parallel) → Done
                → Wave 4 (parallel) ↗
```

### Stage 2: Generator Redesign (future ADR)

- Unified dispatch architecture
- Template selection by capability matrix
- Output path normalization

## References

- **AI Agent Rules**: `docs/ai/rules/capability-model.md`
- SWOT Analysis: `adr/capabilities-analysis/SWOT-CAPABILITIES.md`
- Detailed Code Analysis: `adr/0106-analysis/DETAILED-CODE-ANALYSIS.md`
- Implementation Plan: `adr/0106-analysis/IMPLEMENTATION-PLAN.md`
- Gap Analysis: `adr/0106-analysis/GAP-ANALYSIS.md`
- Capability catalog: `topology/class-modules/capability-catalog.yaml`
- ADR 0063: Plugin microkernel architecture
- ADR 0074: V5 generator architecture
- ADR 0080: Unified build pipeline
