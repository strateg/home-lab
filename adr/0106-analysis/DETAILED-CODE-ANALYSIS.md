# ADR 0106 Detailed Code Analysis

**Analysis Date**: 2026-06-11
**Agent**: tech-lead-architect
**Status**: Complete

---

## Executive Summary

After deep code analysis, identified all files requiring migration, discovered additional patterns that were missed in the initial GAP analysis, and prepared detailed implementation guidance. The migration is well-structured but requires some refinements to handle edge cases and additional hardcoded patterns.

---

## Part 1: Detailed Code Analysis

### 1.1 Generators Analysis

#### 1.1.1 `bootstrap_projections.py` (Lines 43-70)

**Current Implementation:**
```python
# Lines 43-45: Variable initialization with vendor-named lists
proxmox_nodes: list[dict[str, Any]] = []
mikrotik_nodes: list[dict[str, Any]] = []
orangepi_nodes: list[dict[str, Any]] = []

# Lines 52-61: Primary mechanism-based routing (CORRECT approach)
mechanism = _resolve_initialization_mechanism(row)
if mechanism == "unattended_install":
    proxmox_nodes.append(export_row)
if mechanism == "netinstall":
    mikrotik_nodes.append(export_row)
if mechanism == "cloud_init":
    orangepi_nodes.append(export_row)

# Lines 64-69: Legacy fallback with hardcoded object_ref patterns (PROBLEMATIC)
if object_ref == "obj.proxmox.ve":
    proxmox_nodes.append(export_row)
if object_ref.startswith("obj.mikrotik."):
    mikrotik_nodes.append(export_row)
if object_ref.startswith("obj.orangepi."):
    orangepi_nodes.append(export_row)
```

**Analysis:**
- The file already uses `_resolve_initialization_mechanism()` for primary routing — this is CORRECT
- The hardcoded fallback (lines 64-69) exists for objects without `initialization_contract`
- Variable names (`proxmox_nodes`, `mikrotik_nodes`) couple output structure to vendor names

**Required Changes:**
1. Replace vendor-named variables with capability-grouped dicts
2. Remove hardcoded object_ref fallback once all objects have initialization_contract
3. Consider renaming output keys to mechanism-based names (breaking change)

---

#### 1.1.2 `wireguard_generator.py` (Lines 410-433)

**Current Implementation:**
```python
def _detect_platform(
    self, compiled: dict[str, Any], device_ref: str
) -> str:
    # Lines 426-429: Hardcoded string matching
    if "mikrotik" in object_ref.lower():
        return "mikrotik"
    if "oracle" in object_ref.lower() or "cloud_vm" in object_ref.lower():
        return "linux"
    if "linux" in object_ref.lower() or "ubuntu" in object_ref.lower():
        return "linux"
    return "unknown"
```

**Analysis:**
- Method signature uses `device_ref: str` but needs access to full object dict for capabilities
- Returns platform type string which maps to template selection
- Missing "proxmox" and "orangepi" patterns that exist elsewhere

**Required Changes:**
1. Change signature to accept object dict: `_detect_platform(self, obj: dict) -> str`
2. Use `get_platform_type(obj)` from capability_helpers
3. Caller sites (lines 251-256) must pass full object dict, not just device_ref

---

#### 1.1.3 `projections.py` (Lines 155-160)

**Current Implementation:**
```python
CAPABILITY_ROLE_MAP: dict[str, str] = {
    "cap.network.vpn_gateway": "wireguard_gateway",
    # Future capabilities commented out
}
```

**Analysis:**
- Only 1 active entry in the map
- Used by `build_ansible_role_projection()` for role assignments
- Does not include platform-based role mappings

**Required Changes:**
1. Expand map to include platform capabilities
2. Add role derivation from derived capabilities

---

#### 1.1.4 `capability_helpers.py` (Lines 1-80)

**Current Implementation:**
```python
def capability_expression_enabled(capabilities: dict[str, Any], enabled_by: str) -> bool
def get_capability_templates(capabilities: dict[str, Any], config: dict[str, Any]) -> dict[str, str]
```

**Analysis:**
- Missing key functions specified in ADR 0106:
  - `get_all_capabilities(obj)`
  - `has_capability(obj, cap)`
  - `filter_by_capability(objects, cap)`
  - `group_by_capability_prefix(objects, prefix)`
  - `get_platform_type(obj)`

**Required Changes:**
Add 5 new functions as specified in IMPLEMENTATION-PLAN.md

---

### 1.2 Validators Analysis

#### 1.2.1 `hypervisor_execution_model_validator.py` (Lines 28-35)

**Current Implementation:**
```python
_HYPERVISOR_CLASSES = {
    "class.compute.hypervisor",
    "class.compute.hypervisor.proxmox",
    "class.compute.hypervisor.vbox",
    "class.compute.hypervisor.hyperv",
    "class.compute.hypervisor.vmware",
    "class.compute.hypervisor.xen",
}
```

**Analysis:**
- Uses class_ref matching, not object_ref matching (correct pattern)
- This is actually capability-adjacent — checking class family membership
- Could be refactored to `has_capability(obj, "cap.compute.host.hypervisor")`

**Required Changes:**
1. Keep class_ref checks (they are structural, not vendor-specific)
2. Add capability check as supplementary validation

---

#### 1.2.2 `volume_format_compat_validator.py` (Lines 45-51)

**Current Implementation:**
```python
_HYPERVISOR_FORMAT_COMPAT: dict[str, set[str]] = {
    "class.compute.hypervisor.proxmox": {"qcow2", "raw", "vmdk"},
    "class.compute.hypervisor.vbox": {"vdi", "vmdk", "vhd", "raw"},
    "class.compute.hypervisor.hyperv": {"vhd", "vhdx"},
    "class.compute.hypervisor.vmware": {"vmdk"},
    "class.compute.hypervisor.xen": {"qcow2", "vhd", "raw"},
}
```

**Analysis:**
- Uses class_ref keys (not object_ref) — this is structural data about hypervisor types
- This is actually a FORMAT COMPATIBILITY MATRIX, not vendor detection
- Should remain as class_ref based or move to class definition

**Recommendation:**
- **Keep as-is** (this is hypervisor type data, not vendor detection)
- Consider moving to class module as `vm_constraints` schema
- Lower priority for ADR 0106 migration

---

#### 1.2.3 `vm_refs_validator.py` (Lines 245-258)

**Current Implementation:**
```python
# Line 246
if isinstance(platform, str) and platform.strip() and platform.strip().lower() != "proxmox":
```

**Analysis:**
- Checks if storage endpoint platform is "proxmox"
- This is a platform compatibility validation (VMs require Proxmox storage)
- Should use capability check

**Required Changes:**
```python
# After migration
if not has_capability(storage_target, "cap.platform.proxmox"):
```

---

#### 1.2.4 `lxc_refs_validator.py` (Lines 467-480)

**Identical pattern to vm_refs_validator.py** — same migration needed.

---

#### 1.2.5 `router_port_validator.py` (Lines 20-23)

**Current Implementation:**
```python
_VENDOR_RULES: tuple[_VendorRule, ...] = (
    _VendorRule(object_prefix="obj.mikrotik.", diagnostic_code="E7302"),
    _VendorRule(object_prefix="obj.glinet.", diagnostic_code="E7303"),
)
```

**Analysis:**
- Uses object_ref prefix matching
- Purpose: validate vendor-specific router port schemas
- This is a vendor-specific validation case

**Required Changes:**
```python
# After migration
_VENDOR_RULES: tuple[_VendorRule, ...] = (
    _VendorRule(platform_capability="cap.platform.routeros", diagnostic_code="E7302"),
    _VendorRule(platform_capability="cap.platform.openwrt", diagnostic_code="E7303"),
)
```

---

## Part 2: Discovered Additional Patterns

### 2.1 Additional Hardcoded Patterns Found

| File | Pattern | Line | Impact |
|------|---------|------|--------|
| `wireguard_generator.py` | `secrets.get("mikrotik", {})` | 267 | Low (secrets key naming) |
| `docker_refs_validator.py` | May have patterns | N/A | Review needed |
| `module_loader_compiler.py` | `path.name.startswith("obj.")` | 38 | False positive (structural) |

### 2.2 Patterns NOT Requiring Migration

| File | Pattern | Reason |
|------|---------|--------|
| `hypervisor_execution_model_validator.py` | `_HYPERVISOR_CLASSES` | Uses class_ref hierarchy (structural) |
| `volume_format_compat_validator.py` | `_HYPERVISOR_FORMAT_COMPAT` | Hypervisor type compatibility matrix |
| `vm_hypervisor_compat_validator.py` | `_DEFAULT_ALLOWED_*` | Hypervisor type defaults |

---

## Part 3: Additional Derived Capabilities

Based on code analysis, recommended additions to ADR 0106:

### 3.1 Missing Platform Capabilities

```yaml
# From class_ref patterns found in code
cap.platform.vbox:         # VirtualBox hypervisor
cap.platform.hyperv:       # Hyper-V hypervisor
cap.platform.vmware:       # VMware hypervisor
cap.platform.xen:          # Xen hypervisor
```

### 3.2 Missing Workload Capabilities

```yaml
# From workload type detection patterns
cap.workload.vm:           # Derived from class_ref = class.compute.workload.vm
cap.workload.lxc:          # Derived from class_ref = class.compute.workload.lxc
cap.workload.container:    # Derived from class_ref containing "docker" or "container"
```

### 3.3 Total New Capabilities

| Category | Original (ADR 0106) | Additional | Total |
|----------|---------------------|------------|-------|
| Platform | 4 | 4 | 8 |
| Bootstrap | 4 | 0 | 4 |
| Role | 5 | 0 | 5 |
| Vendor | 4 | 0 | 4 |
| Workload | 0 | 3 | 3 |
| **Total** | **17** | **7** | **24** |

---

## Part 4: Stage 2 (Generator Redesign) Assessment

### 4.1 Current Generator Architecture Issues

1. **Template Selection Hardcoded**:
   - `wireguard_generator.py` uses `if endpoint_a_platform == "mikrotik"` to select templates
   - Should use capability-based template matrix

2. **Output Path Hardcoded**:
   - Bootstrap generators produce vendor-named directories
   - Could be mechanism-based instead

3. **Multiple Generator Classes**:
   - Separate generators per object type
   - Could unify with capability dispatch

### 4.2 Stage 2 Scope Recommendations

**High Priority:**
1. Template capability matrix
2. Unified generator entry point

**Medium Priority:**
1. Output path normalization
2. Legacy alias removal

**Low Priority:**
1. Full generator consolidation
2. Dynamic template discovery

---

## Part 5: Optimized Implementation Order

### Wave 1: Foundation (6h) — No Dependencies

| Task | File | Effort |
|------|------|--------|
| 1.1 Add derived capabilities to catalog | `capability-catalog.yaml` | 1h |
| 1.2 Create derived capability compiler | `derived_capability_compiler.py` (NEW) | 3h |
| 1.3 Create plugin manifest entry | `manifest.yaml` | 1h |
| 1.4 Unit tests | `test_derived_capability_compiler.py` (NEW) | 1h |

### Wave 2: Capability Helpers (2h) — Depends on Wave 1

| Task | File | Effort |
|------|------|--------|
| 2.1 Extend helpers | `capability_helpers.py` | 1.5h |
| 2.2 Unit tests | `test_capability_helpers.py` (NEW) | 0.5h |

### Wave 3: Generator Refactoring (6h) — Depends on Wave 2

| Task | File | Effort |
|------|------|--------|
| 3.1 Platform detection | `wireguard_generator.py` | 2h |
| 3.2 Bootstrap grouping | `bootstrap_projections.py` | 2h |
| 3.3 Role mapping | `projections.py` | 2h |

### Wave 4: Validator Refactoring (4h) — Depends on Wave 2

| Task | File | Effort |
|------|------|--------|
| 4.1 Router ports | `router_port_validator.py` | 1h |
| 4.2 VM refs | `vm_refs_validator.py` | 1h |
| 4.3 LXC refs | `lxc_refs_validator.py` | 1h |
| 4.4 Review others | `docker_refs_validator.py` | 1h |

### Wave 5: Backward Compatibility (2h) — Depends on Waves 3-4

| Task | File | Effort |
|------|------|--------|
| 5.1 Legacy aliases | `projections.py` | 1h |
| 5.2 Integration tests | `test_derived_capabilities.py` (NEW) | 1h |

---

## Part 6: Dependencies Graph

```
Wave 1: Foundation
    │
    ▼
Wave 2: Capability Helpers
    │
    ├──────────────────┐
    │                  │
    ▼                  ▼
Wave 3: Generators    Wave 4: Validators
    │                  │
    └────────┬─────────┘
             │
             ▼
Wave 5: Backward Compat + Integration
```

---

## Part 7: Testing Strategy

### 7.1 Unit Tests

| Test File | Coverage |
|-----------|----------|
| `test_derived_capability_compiler.py` | Derivation rules, edge cases |
| `test_capability_helpers.py` | All 5 new functions |
| `test_bootstrap_projections.py` | Capability grouping |
| `test_wireguard_generator.py` | Platform detection |

### 7.2 Integration Tests

| Test | Description |
|------|-------------|
| `test_pipeline_with_derived_caps.py` | Full compile with derived caps |
| `test_generator_output_parity.py` | Diff test: before/after migration |
| `test_validator_with_capabilities.py` | Validators use capability checks |

### 7.3 Regression Test (Critical)

```bash
# Before migration
./topology-tools/compile-topology.py
cp -r generated/home-lab generated/home-lab.baseline

# After migration
./topology-tools/compile-topology.py
diff -r generated/home-lab generated/home-lab.baseline
```

---

## Part 8: Risk Assessment

### 8.1 High Risk Items

| Risk | Mitigation |
|------|------------|
| Derivation misses object without initialization_contract | Legacy fallback during Stage 1 |
| Breaking change to projection output keys | Use aliases, document deprecation |

### 8.2 Medium Risk Items

| Risk | Mitigation |
|------|------------|
| Performance regression | Derive at compile time, cache |
| Circular dependency between compiler and validator | Order in manifest |

### 8.3 Low Risk Items

| Risk | Mitigation |
|------|------------|
| Capability namespace explosion | Strict governance, prefix convention |

---

## Part 9: Recommendations

### 9.1 Immediate Actions

1. **Accept ADR 0106** — Design is sound and addresses real problems
2. **Start Wave 1** — Foundation can be implemented immediately
3. **Create test fixtures** — Mock objects with various capability combinations

### 9.2 Design Refinements

1. **Add missing platform capabilities** for VirtualBox, Hyper-V, VMware, Xen
2. **Add workload-type capabilities** (`cap.workload.vm`, `cap.workload.lxc`, `cap.workload.container`)
3. **Document capability precedence** — What happens when object has multiple platform caps?

### 9.3 Future Considerations (Stage 2)

1. **Template capability matrix** — Declare required caps in template metadata
2. **Unified generator dispatch** — Single entry point with capability routing
3. **Remove legacy aliases** — After deprecation period

---

## Appendix A: File Change Summary

| File | Status | Changes |
|------|--------|---------|
| `capability-catalog.yaml` | Extend | +24 derived capability definitions |
| `derived_capability_compiler.py` | New | ~150 lines |
| `capability_helpers.py` | Extend | +5 functions, ~80 lines |
| `bootstrap_projections.py` | Refactor | Replace vendor vars, remove fallback |
| `wireguard_generator.py` | Refactor | Change _detect_platform signature |
| `projections.py` | Extend | Expand CAPABILITY_ROLE_MAP |
| `router_port_validator.py` | Refactor | Use capability checks |
| `vm_refs_validator.py` | Refactor | Use has_capability() |
| `lxc_refs_validator.py` | Refactor | Use has_capability() |

---

## Appendix B: Patterns Classification

### B.1 Migrate (ADR 0106 Scope)

| Pattern | Files | Action |
|---------|-------|--------|
| `object_ref.startswith("obj.mikrotik.")` | 2 | Use `has_capability(cap.platform.routeros)` |
| `"mikrotik" in object_ref.lower()` | 1 | Use `get_platform_type()` |
| `platform != "proxmox"` | 2 | Use `has_capability(cap.platform.proxmox)` |
| `object_prefix="obj.glinet."` | 1 | Use `has_capability(cap.platform.openwrt)` |

### B.2 Keep As-Is (Structural)

| Pattern | Files | Reason |
|---------|-------|--------|
| `_HYPERVISOR_CLASSES` set | 1 | Class hierarchy check |
| `_HYPERVISOR_FORMAT_COMPAT` dict | 1 | Format compatibility matrix |
| `class_ref == "class.compute..."` | 3 | Structural validation |

### B.3 Future (Stage 2)

| Pattern | Files | Action |
|---------|-------|--------|
| Template selection by platform | 1 | Template capability matrix |
| Output path vendor naming | 2 | Mechanism-based naming |
