# Proposed Amendments: ADR 0106 + ADR 0104

**Date:** 2026-06-18
**Updated:** 2026-06-18 (publish/subscribe design)
**Based on:** SPC SWOT Analysis
**Status:** Proposed

---

## Design Decision: publish/subscribe Pattern

After analyzing the codebase, the recommended approach uses **publish/subscribe** pattern consistent with 60+ existing usages in the project.

### Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         COMPILE STAGE                                    │
│                                                                          │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │ capability_compiler.py (SINGLE SOURCE OF TRUTH)                  │   │
│  │                                                                   │   │
│  │ Uses: capability_derivation.py (shared module)                   │   │
│  │ + own logic for cap.bootstrap.*, cap.vendor.*, cap.role.*        │   │
│  │                                                                   │   │
│  │ ctx.publish("derived_capabilities", {...})                       │   │
│  └───────────────────────────┬──────────────────────────────────────┘   │
│                              │ publish                                   │
│                              ▼                                           │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │ effective_model_compiler.py                                       │   │
│  │                                                                   │   │
│  │ ctx.subscribe("base.compiler.capability", "derived_capabilities")│   │
│  │                                                                   │   │
│  │ Includes derived_caps in compiled_json output                    │   │
│  │ (NO own derivation - removed duplication)                        │   │
│  └──────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Amendment A1: capability_compiler — Use Shared Derivation Module

### Current State

`capability_compiler.py` has its own OS/arch derivation logic that partially duplicates `capability_derivation.py`.

### Proposed Change

```python
# capability_compiler.py - ADD imports
from capability_derivation import (
    derive_os_capabilities as shared_derive_os,
    derive_firmware_capabilities as shared_derive_firmware,
)

class CapabilityCompiler(CompilerPlugin):
    def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        derived_caps: dict[str, list[str]] = {}

        for object_id, object_data in ctx.objects.items():
            caps: set[str] = set()

            # 1. Use shared module for OS/firmware derivation
            os_caps, _ = shared_derive_os(
                object_id=object_id,
                object_payload=object_data,
                catalog_ids=set(),
                path=f"object:{object_id}",
                add_diag=lambda **_: None,
                emit_diagnostics=False,
            )
            caps.update(os_caps)

            fw_caps, _ = shared_derive_firmware(
                object_id=object_id,
                object_payload=object_data,
                catalog_ids=set(),
                path=f"object:{object_id}",
                add_diag=lambda **_: None,
                emit_diagnostics=False,
            )
            caps.update(fw_caps)

            # 2. Own logic for bootstrap/vendor/role (unique to this compiler)
            self._derive_bootstrap_capabilities(object_data, caps, ...)
            self._derive_vendor_capability(object_data, caps)
            self._derive_role_capabilities(object_data, caps)

            if caps:
                derived_caps[object_id] = sorted(caps)

        ctx.publish("derived_capabilities", derived_caps)
        return self.make_result(...)
```

**Effort:** 2h

---

## Amendment A2: effective_model_compiler — Subscribe to Derived Capabilities

### Current State

`effective_model_compiler.py` has its own `_derive_object_effective()` and `_derive_instance_effective()` methods that duplicate derivation logic.

### Proposed Change

```python
# effective_model_compiler.py

class EffectiveModelCompiler(CompilerPlugin):
    _CAPABILITY_PLUGIN_ID = "base.compiler.capability"

    def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        # Subscribe to derived capabilities (NEW)
        try:
            derived_caps = ctx.subscribe(
                self._CAPABILITY_PLUGIN_ID,
                "derived_capabilities"
            )
        except PluginDataExchangeError:
            derived_caps = {}

        # ... existing code ...

        # When building objects_index, use subscribed data:
        for object_ref_key, object_payload in ctx.objects.items():
            objects_index[object_ref_key] = {
                # ... existing fields ...
                "derived_capabilities": derived_caps.get(object_ref_key, []),
                # ... existing fields ...
            }

        # REMOVE: _derive_object_effective() call
        # REMOVE: _derive_instance_effective() call
```

**Effort:** 1h

---

## Amendment A3: Plugin Manifest — Add Dependency

### Current State

`effective_model_compiler` does not declare dependency on `capability_compiler`.

### Proposed Change

```yaml
# plugins.yaml

- id: base.compiler.effective_model
  family: compilers
  stage: compile
  order: 150  # Must be after capability_compiler (order: 50)
  depends_on:
    - base.compiler.capability  # ADD
  consumes:
    - from_plugin: base.compiler.capability
      keys: [derived_capabilities]  # ADD
```

**Effort:** 0.5h

---

## Amendment A4: Remove Duplicate Derivation Methods

### Current State

`effective_model_compiler.py` contains:
- `_derive_object_effective()` (lines 108-119)
- `_derive_instance_effective()` (lines 121-194)

### Proposed Change

**DELETE** these methods after A2 is implemented. They become dead code.

**Effort:** 1h (including test updates)

---

## Amendment A5: ADR 0104 — Update §3 (Capability-Based Role Triggering)

### Current State

ADR 0104 §3 shows `enabled_capabilities` usage only.

### Proposed Change

```python
# projections.py - build_ansible_role_projection()

from .capability_helpers import get_all_capabilities

def build_ansible_role_projection(compiled_json: dict[str, Any]) -> dict[str, Any]:
    # ...
    for inst in group_instances:
        # CHANGE: Use get_all_capabilities() instead of direct access
        capabilities = list(get_all_capabilities(inst))  # Includes derived!

        for cap in capabilities:
            if cap in CAPABILITY_ROLE_MAP:
                role_assignments.append({...})
```

**Effort:** 1h

---

## Amendment A6: Capability Catalog — Add Operations Role Capabilities

### Proposed Addition

```yaml
# capability-catalog.yaml

- @capability: cap.role.linux_host
  title: Linux Host Role
  summary: Device functions as managed Linux host requiring common configuration.
  domain: role
  layer: L7
  stability: stable
  derived: true

- @capability: cap.role.monitoring_target
  title: Monitoring Target Role
  summary: Device should expose monitoring metrics via node_exporter.
  domain: role
  layer: L7
  stability: stable

- @capability: cap.role.backup_target
  title: Backup Target Role
  summary: Device should have backup agent installed.
  domain: role
  layer: L7
  stability: stable
```

**Effort:** 1h

---

## Amendment A7: capability_compiler — Add Linux Host Derivation

### Proposed Addition

```python
# capability_compiler.py

def _derive_linux_host_capability(self, caps: set[str]) -> None:
    """Derive cap.role.linux_host from OS capabilities."""
    linux_caps = {"cap.os.debian", "cap.os.ubuntu", "cap.os.linux"}
    if caps & linux_caps:
        caps.add("cap.role.linux_host")
```

**Effort:** 0.5h

---

## Amendment A8: ADR 0104 — Add §7.3 (CI Validation)

### Proposed Addition

```yaml
# .github/workflows/ci.yml

- name: Validate generated Ansible
  run: |
    ansible-playbook --syntax-check \
      generated/home-lab/ansible/playbooks/*.yml
```

**Effort:** 2h

---

## Summary of Amendments

| ID | Target | Type | Description | Effort |
|----|--------|------|-------------|--------|
| A1 | capability_compiler | Extend | Use shared derivation module | 2h |
| A2 | effective_model_compiler | Modify | Subscribe to derived_capabilities | 1h |
| A3 | plugins.yaml | Modify | Add dependency declaration | 0.5h |
| A4 | effective_model_compiler | Remove | Delete duplicate derivation methods | 1h |
| A5 | projections.py | Modify | Use get_all_capabilities() | 1h |
| A6 | capability-catalog.yaml | Add | Operations role capabilities | 1h |
| A7 | capability_compiler | Add | Linux host derivation rule | 0.5h |
| A8 | CI workflow | Add | Ansible validation step | 2h |
| **Total** | | | | **9h** |

---

## Implementation Order

```
Phase 1: Core Integration (4.5h)
├── A1: capability_compiler uses shared module
├── A2: effective_model_compiler subscribes
├── A3: Manifest dependency
└── A4: Remove duplicate methods

Phase 2: Ansible Integration (2.5h)
├── A5: projections.py uses get_all_capabilities()
├── A6: Catalog additions
└── A7: Linux host derivation

Phase 3: CI/Workflow (2h)
└── A8: CI validation
```

---

## Approval Checklist

- [ ] A1: capability_compiler uses shared module
- [ ] A2: effective_model_compiler subscribes
- [ ] A3: Manifest dependency
- [ ] A4: Remove duplicate methods
- [ ] A5: projections.py update
- [ ] A6: Catalog additions
- [ ] A7: Linux host derivation
- [ ] A8: CI validation
