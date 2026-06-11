# Capability Model Guide

**ADR**: 0106
**Status**: Implemented (Stage 1)
**AI Rules**: `docs/ai/rules/capability-model.md`

## Overview

The capability model provides a declarative way to classify devices and determine their behavior without hardcoding vendor names or object references in plugin code.

**Key principle**: Plugins should use capability checks instead of string matching on `object_ref` or `class_ref`.

```python
# BAD - hardcoded string matching
if "mikrotik" in object_ref.lower():
    return "mikrotik"

# GOOD - capability-based detection
from plugins.generators.capability_helpers import has_capability

if has_capability(obj, "cap.os.routeros"):
    return "mikrotik"
```

## Capability Namespaces

| Namespace | Source | Purpose |
|-----------|--------|---------|
| `cap.os.*` | OS family/distribution | Platform detection |
| `cap.arch.*` | CPU architecture | Architecture-specific code |
| `cap.bootstrap.*` | `initialization_contract.mechanism` | Bootstrap grouping |
| `cap.vendor.*` | `vendor` field | Vendor identity |
| `cap.role.*` | `enabled_capabilities` | Device role |

### Platform Capabilities (cap.os.*)

Derived from OS family and distribution in object properties.

| Capability | Meaning |
|------------|---------|
| `cap.os.linux` | Linux-based OS |
| `cap.os.posix` | POSIX-compliant |
| `cap.os.routeros` | MikroTik RouterOS |
| `cap.os.proxmox` | Proxmox VE |
| `cap.os.debian` | Debian distribution |
| `cap.os.ubuntu` | Ubuntu distribution |

### Bootstrap Capabilities (cap.bootstrap.*)

Derived from `initialization_contract.mechanism` field.

| Capability | Mechanism | Devices |
|------------|-----------|---------|
| `cap.bootstrap.cloud_init` | `cloud_init` | Orange Pi, VMs |
| `cap.bootstrap.netinstall` | `netinstall` | MikroTik |
| `cap.bootstrap.unattended` | `unattended_install` | Proxmox |
| `cap.bootstrap.manual` | `manual` | Manual setup |

### Vendor Capabilities (cap.vendor.*)

Derived from `vendor` field in object definition.

| Capability | Vendor |
|------------|--------|
| `cap.vendor.mikrotik` | MikroTik |
| `cap.vendor.proxmox` | Proxmox |
| `cap.vendor.orangepi` | Orange Pi |
| `cap.vendor.oracle` | Oracle Cloud |

### Role Capabilities (cap.role.*)

Derived from `enabled_capabilities` list in object definition.

| Capability | Role |
|------------|------|
| `cap.role.hypervisor` | Hypervisor host |
| `cap.role.router` | Network router |
| `cap.role.edge_node` | Edge compute node |
| `cap.role.vpn_endpoint` | VPN endpoint |
| `cap.role.container_host` | Container runtime host |

## Using Capabilities in Plugins

### Import Helper Functions

```python
from plugins.generators.capability_helpers import (
    has_capability,
    get_all_capabilities,
    filter_by_capability,
    group_by_capability_prefix,
    get_platform_type,
    get_bootstrap_capability,
    get_platform_capability,
    CapabilityError,
)
```

### Check Single Capability

```python
def process_device(obj: dict) -> None:
    if has_capability(obj, "cap.os.routeros"):
        # MikroTik-specific logic
        generate_routeros_config(obj)
    elif has_capability(obj, "cap.os.proxmox"):
        # Proxmox-specific logic
        generate_proxmox_config(obj)
```

### Get All Capabilities

```python
caps = get_all_capabilities(obj)
# Returns: {"cap.os.routeros", "cap.vendor.mikrotik", "cap.bootstrap.netinstall", ...}

if "cap.os.linux" in caps:
    # Linux-specific handling
    pass
```

### Filter Objects by Capability

```python
# Get all devices with cloud-init bootstrap
cloud_init_devices = filter_by_capability(devices, "cap.bootstrap.cloud_init")

for device in cloud_init_devices:
    generate_cloud_init_config(device)
```

### Group by Capability Prefix

```python
# Group devices by bootstrap mechanism
bootstrap_groups = group_by_capability_prefix(devices, "cap.bootstrap.")
# Returns: {
#     "cap.bootstrap.cloud_init": [device1, device2],
#     "cap.bootstrap.netinstall": [device3],
#     "cap.bootstrap.unattended": [device4],
# }

for cap, group_devices in bootstrap_groups.items():
    mechanism = cap.replace("cap.bootstrap.", "")
    generate_bootstrap_package(mechanism, group_devices)
```

### Get Platform Type (Convenience)

```python
platform = get_platform_type(obj)
# Returns: "mikrotik", "proxmox", "linux", "bsd", "windows", or "unknown"

if platform == "mikrotik":
    # MikroTik handling
    pass
```

### Strict Error Handling

```python
try:
    bootstrap_cap = get_bootstrap_capability(obj)
    # Returns e.g., "cap.bootstrap.cloud_init"
except CapabilityError as e:
    # E8021: Missing cap.bootstrap.* capability
    ctx.emit_diagnostic(code=e.code, severity="error", message=e.message)
    return

try:
    platform_cap = get_platform_capability(obj)
    # Returns e.g., "cap.os.routeros"
except CapabilityError as e:
    # E8020: Cannot detect platform
    ctx.emit_diagnostic(code=e.code, severity="error", message=e.message)
    return
```

## Adding New Device Type

### Step 1: Create Object Module

```yaml
# topology/object-modules/newdevice/obj.newdevice.model.yaml
"@object": obj.newdevice.model
class_ref: class.compute.edge_node
vendor: newdevice

properties:
  family: linux
  distribution: debian
  architecture: aarch64

initialization_contract:
  mechanism: cloud_init
  version: "1.0.0"
  bootstrap:
    template: bootstrap/user-data.j2

enabled_capabilities:
  - cap.workload.runtime.docker
  - cap.role.edge_node
```

### Step 2: Verify Derived Capabilities

Run compilation to see derived capabilities:

```bash
.venv/bin/python topology-tools/compile-topology.py --profile dev
```

Check diagnostics for I4201 info messages showing derived capabilities.

### Step 3: No Plugin Changes Needed

If capabilities are properly declared, existing plugins will automatically handle the new device type through capability checks.

## Error Codes

| Code | Stage | Condition | Fix |
|------|-------|-----------|-----|
| E8001 | Compile | `initialization_contract` exists but `mechanism` is missing | Add `mechanism` field |
| E8002 | Compile | Unknown `mechanism` value | Use: cloud_init, netinstall, unattended_install, manual |
| E8020 | Generate | Cannot detect platform from `cap.os.*` | Ensure OS family/distribution is defined |
| E8021 | Generate | Missing `cap.bootstrap.*` capability | Add `initialization_contract` to object |

## Capability Catalog

All valid capabilities are defined in:
```
topology/class-modules/capability-catalog.yaml
```

Adding a new capability:
```yaml
- "@capability": cap.newnamespace.newcap
  title: New Capability
  summary: Description of what this capability represents.
  domain: newnamespace
  layer: L0
  stability: stable
```

## Migration from String Matching

### Before (Legacy Pattern)

```python
def _detect_platform(self, row: dict) -> str:
    object_ref = row.get("object_ref", "")
    if "mikrotik" in object_ref.lower():
        return "mikrotik"
    if "proxmox" in object_ref:
        return "proxmox"
    return "unknown"
```

### After (Capability Pattern)

```python
from plugins.generators.capability_helpers import get_platform_type

def _detect_platform(self, row: dict) -> str:
    obj = row.get("object", {})
    return get_platform_type(obj)
```

## Best Practices

1. **Always use capability checks** for device type detection
2. **Never use string matching** on `object_ref` or `class_ref`
3. **Emit errors, not silent fallbacks** when required capabilities are missing
4. **Use existing namespaces** (`cap.os.*`, `cap.bootstrap.*`) instead of creating duplicates
5. **Declare capabilities in topology** rather than inferring them in plugins
6. **Test with capability mocking** - capabilities are easy to mock in tests

## References

- ADR 0106: Capability-Driven Plugin Architecture
- AI Rules: `docs/ai/rules/capability-model.md`
- Capability Catalog: `topology/class-modules/capability-catalog.yaml`
- Capability Helpers: `topology-tools/plugins/generators/capability_helpers.py`
