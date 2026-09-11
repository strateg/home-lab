---
"@pack": capability-model
"@version": 1.2
"@tokens": ~1600
"@adr": [0088, 0106, 0118, 0119]
---

# AI Rule Pack: Capability Model

## Quick Reference

| Rule | Key Point |
|------|-----------|
| Detection | Use `has_capability()`, never string matching |
| Platform | `cap.os.*` capabilities (routeros, debian, proxmox) |
| Bootstrap | Derived from `initialization_contract.mechanism` |
| Errors | E8020/E8021 for platform/bootstrap; network satisfaction uses centrally allocated SEC-CAP diagnostics |
| New device | Add declarations; reuse only already implemented/qualified behavior |
| Network support | Scoped requirements/offers/evidence, never flag-as-proof |

## Load When

- Adding new device/platform support
- Modifying generators that process devices
- Modifying validators that check device properties
- Working with bootstrap, platform detection, or role assignment
- Seeing errors E8001-E8021

## Core Principles

1. **NEVER** use object_ref string matching for device type detection
2. **NEVER** use class_ref string matching for platform detection
3. **ALWAYS** use capability checks via `has_capability()` or `get_all_capabilities()`
4. **ALWAYS** block the affected claim (not silently fall back) when required support is missing; distinguish offline and live evidence

## Rules

1. Use existing `cap.os.*` capabilities for platform detection (not `cap.platform.*`).
2. Use existing `cap.workload.runtime.*` for workload types (not `cap.workload.vm/lxc`).
3. Derive `cap.bootstrap.*` from `initialization_contract.mechanism`.
4. Derive `cap.vendor.*` from `vendor` field.
5. Derive `cap.role.*` from `enabled_capabilities`.
6. Keep E8020/E8021 for missing platform/bootstrap detection; do not reuse them for network semantic satisfaction.
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

3. No generator/validator changes are needed only when the existing implementation
   already supports the same qualified behavior. A declaration cannot implement or
   qualify a new network, state or transition semantic.

## Network satisfaction (Accepted target design, not implemented)

ADR 0118 D6.1 / ADR 0119 D2.1 and
[shared contract](../../../adr/0119-analysis/CAPABILITY-SATISFACTION-CONTRACT.md):

1. Derive requirements from intent/profile with provenance; no duplicate per-service
   authored checklist. Reuse catalog/packs and existing derivation ownership.
2. Offers include exact subjects/versions/contexts, conditions, bounds and authorized
   operations. Effective capability is a derived join, not a parallel registry.
3. Resolve per path/state across device/runtime + adapter + owner operations.
   has_capability is classification, not end-to-end evidence; never union all flags.
   Selected witnesses must be jointly compatible in modes, capacity and ownership.
4. Report satisfied/unsatisfied/unverified for the named claim/gate. Missing live
   evidence blocks activation, not otherwise valid offline candidate generation.
5. Use bounded typed alternative strategies; reject incomplete inventories/cycles
   and unknown semantics. No self-attested qualification or capability-as-permit.
6. Bind offer versions/strategies/conditions and evidence to plan/bundle; invalidate
   on relevant drift/version/mode/owner change or expiry. Keep live timestamps out
   of semantic digests, not out of evidence integrity verification.
7. Preserve cap.net.*, cap.firewall.*, cap.workload.*, cap.operations.* ownership.
   No cap.can_access.*, duplicate cap.platform.* or boolean-per-timeout namespace.
8. safe_mode/state_restore do not prove current-epoch rollback safety or authorize
   a second writer. Catalog and runtime remain unchanged until implementation gates.
9. The catalog is a **closed, identifier-only** vocabulary. The loader publishes
   `catalog_ids`/`packs_map` and reads no other catalog field, and the contract
   validator rejects class/object capabilities outside that set. So extra fields on
   a catalog entry are inert, and any identifier a requirement, offer or test names
   must be registered first. Registration is declaration, never qualification.
10. Split an offer into a semantic core (enters the plan digest) and an evidence
    annex (hashed separately, bound to the manifest only). Without the split,
    recording new qualification evidence rewrites the plan.
11. Missing vocabulary yields **unverified**, not not-applicable. Report the four
    conditions distinctly: absent identifier, unimplemented check, absent data,
    unqualified backend. They have different owners and different remedies.
12. `E8020`/`E8021`/`E3202` are raised in code but are **not** registered in
    `topology-tools/data/error-catalog.yaml`. Do not cite them as an example of
    correct allocation, and register any new capability range before raising it.

## Error Codes

| Code | Stage | Condition | Fix |
|------|-------|-----------|-----|
| E8001 | Compile | Missing `initialization_contract.mechanism` | Add to object module |
| E8002 | Compile | Unknown mechanism value | Use: cloud_init, netinstall, unattended_install, manual |
| E8020 | Generate | Cannot detect platform | Ensure `cap.os.*` is derived from OS |
| E8021 | Generate | Missing bootstrap capability | Add `initialization_contract` to object |

Registry status (verified at `493867d5`): `E8001`/`E8002` are registered in
`topology-tools/data/error-catalog.yaml`; `E8020`, `E8021` and `E3202` are **not**.
The registry, indexed by `docs/diagnostics-catalog.md`, is the source of truth, and
its governance requires ranges to be registered before implementation. Treat the
three as registration debt owned by ADR 0118 W03/G1, not as precedent.

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

```bash
grep -r "object_ref.startswith" topology-tools/plugins/  # Should return 0
grep -r "in object_ref.lower()" topology-tools/plugins/  # Should return 0
task test:capability-model
```
