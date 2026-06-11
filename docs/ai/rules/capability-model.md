# AI Rule Pack: Capability Model (ADR 0106)

Load when:

- Adding new device/platform support
- Modifying generators that process devices
- Modifying validators that check device properties
- Working with bootstrap, platform detection, or role assignment
- Seeing errors E8001-E8021

## Core Principles

1. **NEVER** use object_ref string matching for device type detection
2. **NEVER** use class_ref string matching for platform detection
3. **ALWAYS** use capability checks via `has_capability()` or `get_all_capabilities()`
4. **ALWAYS** emit errors (not fallbacks) when required capability is missing

## Rules

1. Use existing `cap.os.*` capabilities for platform detection (not `cap.platform.*`).
2. Use existing `cap.workload.runtime.*` for workload types (not `cap.workload.vm/lxc`).
3. Derive `cap.bootstrap.*` from `initialization_contract.mechanism`.
4. Derive `cap.vendor.*` from `vendor` field.
5. Derive `cap.role.*` from `enabled_capabilities`.
6. Emit E8020/E8021 errors when required capabilities are missing.
7. Do not implement silent fallbacks for missing capabilities.

## Decision Matrix

| Need to know | USE | NOT |
|--------------|-----|-----|
| Device platform | `cap.os.routeros`, `cap.os.debian`, `cap.os.proxmox` | `"mikrotik" in object_ref` |
| Bootstrap mechanism | `cap.bootstrap.cloud_init`, `cap.bootstrap.netinstall` | `object_ref.startswith("obj.proxmox")` |
| Device role | `cap.role.hypervisor`, `cap.role.router` | hardcoded lists |
| Vendor identity | `cap.vendor.mikrotik`, `cap.vendor.proxmox` | vendor field string checks |
| Workload type | `cap.workload.runtime.lxc`, `cap.workload.runtime.qemu` | class_ref matching |

## Adding New Device Type

1. Create object module with:
   - `initialization_contract.mechanism` (required)
   - `enabled_capabilities` list
   - `vendor` field

2. Compiler auto-derives:
   - `cap.bootstrap.*` from mechanism
   - `cap.os.*` from OS definition
   - `cap.vendor.*` from vendor field

3. No generator/validator changes needed if capabilities are declared

## Error Codes

| Code | Stage | Condition | Fix |
|------|-------|-----------|-----|
| E8001 | Compile | Missing `initialization_contract.mechanism` | Add to object module |
| E8002 | Compile | Unknown mechanism value | Use: cloud_init, netinstall, unattended_install, manual |
| E8020 | Generate | Cannot detect platform | Ensure `cap.os.*` is derived from OS |
| E8021 | Generate | Missing bootstrap capability | Add `initialization_contract` to object |

## Anti-Patterns (PROHIBITED)

```python
# WRONG - hardcoded string matching
if "mikrotik" in object_ref.lower():
    return "mikrotik"

# WRONG - legacy fallback
if not mechanism:
    if object_ref.startswith("obj.proxmox"):
        proxmox_nodes.append(row)

# WRONG - class_ref pattern matching for platform
if class_ref == "class.network.router.mikrotik":
    platform = "mikrotik"
```

## Correct Patterns (REQUIRED)

```python
# CORRECT - capability check for platform
from plugins.generators.capability_helpers import has_capability, get_all_capabilities

if has_capability(obj, "cap.os.routeros"):
    return "mikrotik"

# CORRECT - strict error on missing capability
caps = get_all_capabilities(obj)
bootstrap_caps = [c for c in caps if c.startswith("cap.bootstrap.")]
if not bootstrap_caps:
    ctx.emit_diagnostic(code="E8021", severity="error", ...)
    continue  # Skip, don't fallback

# CORRECT - group by capability
from plugins.generators.capability_helpers import group_by_capability_prefix
groups = group_by_capability_prefix(devices, "cap.bootstrap.")
```

## Heuristics for AI Agents

| Situation | Action |
|-----------|--------|
| Adding new device | Create object module with `initialization_contract` and `enabled_capabilities` |
| Generator not finding device | Check that object has required capability |
| Error E8020/E8021 | Add missing capability to object/class |
| Need platform detection | Use `cap.os.*` capabilities |
| Need bootstrap grouping | Use `group_by_capability_prefix("cap.bootstrap.")` |
| Seeing `object_ref.startswith` | REFACTOR to use `has_capability()` |

## Validation

- `grep -r "object_ref.startswith" topology-tools/plugins/` (should return 0 matches)
- `grep -r "in object_ref.lower()" topology-tools/plugins/` (should return 0 matches)
- `task test:capability-model`

## ADR Sources

- ADR0106 — Capability-driven plugin architecture
