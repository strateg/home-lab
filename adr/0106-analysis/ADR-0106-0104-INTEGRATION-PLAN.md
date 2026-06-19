# ADR 0106 + ADR 0104 Integration Plan

**Created:** 2026-06-18
**Updated:** 2026-06-18 (publish/subscribe design)
**Status:** Approved (SPC Steps 0-7 complete)
**Total Effort:** 30 hours (revised from 35h)
**Design Pattern:** publish/subscribe (consistent with 60+ usages in project)
**SWOT Analysis:** `SWOT-ADR0106-ADR0104.md`
**Amendments:** `AMENDMENTS-ADR0106-ADR0104.md`

---

## Executive Summary

ADR 0106 (Capability-Driven Plugin Architecture) and ADR 0104 (Ansible Role Generation) require integration via the project's standard **publish/subscribe** pattern.

**Key findings:**
1. `capability_compiler` publishes but nobody subscribes
2. `effective_model_compiler` duplicates derivation logic instead of subscribing
3. Solution: consolidate derivation, use publish/subscribe

---

## Architecture (Revised)

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         COMPILE STAGE                                    │
│                                                                          │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │ capability_compiler.py (order: 50)                               │   │
│  │ SINGLE SOURCE OF TRUTH for capability derivation                 │   │
│  │                                                                   │   │
│  │ Uses: capability_derivation.py (shared module)                   │   │
│  │ Derives: cap.os.*, cap.arch.*, cap.firmware.*                    │   │
│  │ + own: cap.bootstrap.*, cap.vendor.*, cap.role.*                 │   │
│  │                                                                   │   │
│  │ ctx.publish("derived_capabilities", {...})                       │   │
│  └───────────────────────────┬──────────────────────────────────────┘   │
│                              │                                           │
│                              │ publish/subscribe                         │
│                              ▼                                           │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │ effective_model_compiler.py (order: 150)                         │   │
│  │                                                                   │   │
│  │ depends_on: [base.compiler.capability]                           │   │
│  │ consumes: [derived_capabilities]                                 │   │
│  │                                                                   │   │
│  │ derived_caps = ctx.subscribe(                                    │   │
│  │     "base.compiler.capability", "derived_capabilities"           │   │
│  │ )                                                                 │   │
│  │                                                                   │   │
│  │ Builds compiled_json with derived_capabilities included          │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│                              │                                           │
│                              ▼                                           │
│                        compiled_json                                     │
│                    (instances have derived_capabilities)                │
└─────────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         GENERATE STAGE                                   │
│                                                                          │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │ ansible_role_generator.py                                        │   │
│  │                                                                   │   │
│  │ build_ansible_role_projection() uses:                            │   │
│  │   capabilities = get_all_capabilities(inst)  # sees derived!    │   │
│  │                                                                   │   │
│  │ CAPABILITY_ROLE_MAP matches derived capabilities                 │   │
│  └──────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Phase 1: Core Integration (6.5h) — CRITICAL

### T1.1: Extend capability_compiler with Shared Module

**File:** `topology-tools/plugins/compilers/capability_compiler.py`

**Change:** Use `capability_derivation.py` for OS/firmware derivation to eliminate duplication.

```python
from capability_derivation import (
    derive_os_capabilities as shared_derive_os,
    derive_firmware_capabilities as shared_derive_firmware,
)
```

**Effort:** 2h
**Dependencies:** None

### T1.2: Add Subscribe to effective_model_compiler

**File:** `topology-tools/plugins/compilers/effective_model_compiler.py`

**Change:** Subscribe to `derived_capabilities` instead of deriving independently.

```python
derived_caps = ctx.subscribe(
    "base.compiler.capability",
    "derived_capabilities"
)
```

**Effort:** 1h
**Dependencies:** T1.1

### T1.3: Update Plugin Manifest

**File:** `topology-tools/plugins/plugins.yaml`

**Change:** Add dependency declaration.

```yaml
- id: base.compiler.effective_model
  depends_on:
    - base.compiler.capability
  consumes:
    - from_plugin: base.compiler.capability
      keys: [derived_capabilities]
```

**Effort:** 0.5h
**Dependencies:** T1.1

### T1.4: Remove Duplicate Derivation Methods

**File:** `topology-tools/plugins/compilers/effective_model_compiler.py`

**Change:** Delete `_derive_object_effective()` and `_derive_instance_effective()` methods.

**Effort:** 1h
**Dependencies:** T1.2

### T1.5: Add Unit Tests

**File:** `tests/plugin_unit/test_capability_integration.py` (new)

**Tests:**
- `test_capability_compiler_publishes_derived()`
- `test_effective_model_subscribes_correctly()`
- `test_compiled_json_has_derived_capabilities()`

**Effort:** 2h
**Dependencies:** T1.4

---

## Phase 2: Ansible Integration (4h)

### T2.1: Update projections.py

**File:** `topology-tools/plugins/generators/projections.py`

**Change:** Use `get_all_capabilities()` in `build_ansible_role_projection()`.

```python
from .capability_helpers import get_all_capabilities

capabilities = list(get_all_capabilities(inst))  # Includes derived
```

**Effort:** 1h
**Dependencies:** Phase 1

### T2.2: Add Capabilities to Catalog

**File:** `topology/class-modules/capability-catalog.yaml`

**Add:**
- `cap.role.linux_host`
- `cap.role.monitoring_target`
- `cap.role.backup_target`

**Effort:** 1h
**Dependencies:** None

### T2.3: Add Linux Host Derivation Rule

**File:** `topology-tools/plugins/compilers/capability_compiler.py`

**Add:** Derive `cap.role.linux_host` when `cap.os.debian/ubuntu/linux` present.

**Effort:** 0.5h
**Dependencies:** T2.2

### T2.4: Expand CAPABILITY_ROLE_MAP

**File:** `topology-tools/plugins/generators/projections.py`

**Add mappings:**
```python
"cap.role.linux_host": "common",
"cap.role.monitoring_target": "node_exporter",
"cap.role.backup_target": "backup_client",
```

**Effort:** 0.5h
**Dependencies:** T2.2

### T2.5: Unit Tests

**Effort:** 1h
**Dependencies:** T2.4

---

## Phase 3: Ansible Role Templates (10h)

### T3.1: Create docker_host Role Templates

**Files:**
- `topology-tools/templates/ansible/host_vars/docker_host.yml.j2`
- `topology-tools/templates/ansible/playbooks/docker.yml.j2`

**Effort:** 3h

### T3.2: Create node_exporter Role Templates

**Files:**
- `topology-tools/templates/ansible/host_vars/node_exporter.yml.j2`
- `topology-tools/templates/ansible/playbooks/monitoring.yml.j2`

**Effort:** 2h

### T3.3: Create common Role Templates

**Files:**
- `topology-tools/templates/ansible/host_vars/common.yml.j2`
- `topology-tools/templates/ansible/playbooks/common.yml.j2`

**Effort:** 2h

### T3.4: Add Role Projection Builders

**File:** `topology-tools/plugins/generators/ansible_role_projections.py`

**Effort:** 3h

---

## Phase 4: Generator Integration (5.5h)

### T4.1: Implement Multi-Role Assignment

**File:** `topology-tools/plugins/generators/ansible_role_generator.py`

**Effort:** 2h

### T4.2: Add Capability-Driven Template Selection

**Effort:** 1.5h

### T4.3: Add Integration Tests

**Effort:** 2h

---

## Phase 5: Workflow Integration (4h)

### T5.1: Implement Taskfile ansible:role-runtime

**File:** `taskfiles/ansible.yml`

**Effort:** 1.5h

### T5.2: Implement Taskfile ansible:role-check

**Effort:** 0.5h

### T5.3: Add CI Validation

**File:** `.github/workflows/ci.yml`

**Effort:** 2h

---

## Summary

| Phase | Description | Hours | Cumulative |
|-------|-------------|-------|------------|
| **1** | Core Integration (publish/subscribe) | 6.5h | 6.5h |
| **2** | Ansible Integration | 4h | 10.5h |
| **3** | Ansible Templates | 10h | 20.5h |
| **4** | Generator Integration | 5.5h | 26h |
| **5** | Workflow Integration | 4h | 30h |

**Total:** 30 hours

---

## Validation Checkpoints

### After Phase 1 (Critical Gate)

```bash
# Verify subscribe works
.venv/bin/python topology-tools/compile-topology.py

# Check derived_capabilities in compiled output
jq '[.instances.devices[] | select(.derived_capabilities) |
    {id: .["@instance"], caps: .derived_capabilities[:3]}] | .[0:3]' \
    build/effective-topology.json

# Expected: Non-empty array with derived capabilities
```

### After Phase 2

```bash
# Verify Ansible projection sees derived caps
.venv/bin/python -c "
from plugins.generators.projections import build_ansible_role_projection
import json
with open('build/effective-topology.json') as f:
    data = json.load(f)
proj = build_ansible_role_projection(data)
print(f'Role assignments: {len(proj[\"role_assignments\"])}')"
```

### After Phase 4

```bash
ansible-playbook --syntax-check generated/home-lab/ansible/playbooks/*.yml
```

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Subscribe fails silently | Catch PluginDataExchangeError, log warning |
| Derivation inconsistency | Remove duplicate code in Phase 1 |
| Breaking compiled.json | Diff test before/after |
| Test failures | Full pytest suite after each phase |

---

## Files Modified

| File | Change Type | Phase |
|------|-------------|-------|
| `capability_compiler.py` | Extend (use shared module) | 1, 2 |
| `effective_model_compiler.py` | Modify (subscribe), Remove (methods) | 1 |
| `plugins.yaml` | Modify (add dependency) | 1 |
| `projections.py` | Modify (use get_all_capabilities) | 2 |
| `capability-catalog.yaml` | Add (3 capabilities) | 2 |
| `ansible_role_generator.py` | Modify (multi-role) | 4 |
| `ansible_role_projections.py` | Add (builders) | 3 |
| Templates (4 new) | Add | 3 |
| `taskfiles/ansible.yml` | Add (tasks) | 5 |
| `.github/workflows/ci.yml` | Modify (validation) | 5 |

---

## Approval Checklist

- [x] Phase 1 approved (CRITICAL - publish/subscribe) — SPC Analysis
- [x] Phase 2 approved (Ansible integration) — SPC Analysis
- [x] Phase 3 approved (Templates) — SPC Analysis
- [x] Phase 4 approved (Generator) — SPC Analysis
- [x] Phase 5 approved (Workflow) — SPC Analysis

**Approved via SPC Mode:** Steps 0-7 complete (2026-06-18)

---

## References

- ADR 0106: Capability-Driven Plugin Architecture
- ADR 0104: Ansible Role Generation from Topology
- SWOT Analysis: `SWOT-ADR0106-ADR0104.md`
- Amendments: `AMENDMENTS-ADR0106-ADR0104.md`
- Shared module: `topology-tools/capability_derivation.py`
- Plugin authoring: `topology-tools/docs/PLUGIN_AUTHORING.md`
