# ADR 0106 Gap Analysis

**Analysis Date**: 2026-06-11
**SPC Mode**: Steps 0-5 Complete

---

## Executive Summary

Current plugin architecture contains **12 files** with hardcoded vendor name checks that violate Infrastructure-as-Data principle. The capability system exists (188+ capabilities) but is underutilized. Solution: Derived Capabilities model where compiler auto-derives platform/bootstrap/role/vendor capabilities from object metadata.

---

## AS-IS State

### Current Capability Usage

```
                    CAPABILITY UTILIZATION
  ┌─────────────────────────────────────────────────┐
  │ Capability Catalog: 188 capabilities            │
  │ ├── L7 Operations: 10 caps (ADR 0105)           │
  │ ├── L6 Observability: 15 caps                   │
  │ ├── L5 Services: 25 caps                        │
  │ ├── L4 Platform: 45 caps                        │
  │ └── L3/L2/L1: 93 caps                           │
  │                                                  │
  │ Plugin Usage: ~5% utilization                   │
  │ ├── capability_expression_enabled(): 1 caller   │
  │ └── CAPABILITY_ROLE_MAP: 1 entry                │
  └─────────────────────────────────────────────────┘
```

### Hardcoded Patterns Found

| Pattern Type | Occurrences | Example |
|--------------|-------------|---------|
| `object_ref.startswith("obj.mikrotik.")` | 4 | bootstrap_projections.py:45 |
| `"mikrotik" in object_ref.lower()` | 3 | wireguard_generator.py:410 |
| `class_ref == "class.compute.hypervisor.proxmox"` | 2 | hypervisor_execution_model_validator.py:48 |
| `platform != "proxmox"` | 2 | vm_refs_validator.py:72 |
| Hardcoded sets `_HYPERVISOR_CLASSES` | 3 | volume_format_compat_validator.py:22 |

### Problems Identified (10 total)

| ID | Problem | Impact |
|----|---------|--------|
| P1 | `bootstrap_projections.py` hardcodes `obj.mikrotik.*`, `obj.proxmox.ve`, `obj.orangepi.*` | High |
| P2 | `wireguard_generator.py` uses `if "mikrotik" in object_ref.lower()` | High |
| P3 | `projections.py` `CAPABILITY_ROLE_MAP` has only 1 entry | Medium |
| P4 | `capability_helpers.py` underutilized | Medium |
| P5 | `hypervisor_execution_model_validator.py` hardcodes `class.compute.hypervisor.proxmox` | Medium |
| P6 | `volume_format_compat_validator.py` has `_HYPERVISOR_FORMAT_COMPAT` dict | Medium |
| P7 | `vm_hypervisor_compat_validator.py` has `_DEFAULT_ALLOWED_*` constants | Medium |
| P8 | `vm_refs_validator.py` uses `platform != "proxmox"` | Low |
| P9 | `lxc_refs_validator.py` uses `platform != "proxmox"` | Low |
| P10 | `router_port_validator.py` checks `obj.mikrotik.`, `obj.glinet.` prefixes | Medium |

---

## TO-BE State

### Derived Capabilities Architecture

```
                    DERIVED CAPABILITIES FLOW
  ┌─────────────────────────────────────────────────┐
  │ COMPILE STAGE                                   │
  │ ┌───────────────────────────────────────────┐   │
  │ │ derived_capability_compiler.py             │   │
  │ │                                            │   │
  │ │ Input: object with class_ref, vendor,     │   │
  │ │        initialization_contract.mechanism   │   │
  │ │                                            │   │
  │ │ Rules:                                     │   │
  │ │ ├── class_ref → cap.platform.*             │   │
  │ │ ├── mechanism → cap.bootstrap.*            │   │
  │ │ ├── enabled_caps → cap.role.*              │   │
  │ │ └── vendor → cap.vendor.*                  │   │
  │ │                                            │   │
  │ │ Output: obj["derived_capabilities"] = [...]│   │
  │ └───────────────────────────────────────────┘   │
  └─────────────────────────────────────────────────┘
                        │
                        ▼
  ┌─────────────────────────────────────────────────┐
  │ GENERATE STAGE                                  │
  │ ┌───────────────────────────────────────────┐   │
  │ │ capability_helpers.py                      │   │
  │ │                                            │   │
  │ │ has_capability(obj, "cap.platform.proxmox")│   │
  │ │ filter_by_capability(objs, "cap.role.*")  │   │
  │ │ group_by_capability_prefix(objs, "cap.b") │   │
  │ │ get_platform_type(obj) → "proxmox"        │   │
  │ └───────────────────────────────────────────┘   │
  └─────────────────────────────────────────────────┘
```

### New Capability Namespaces (17 capabilities)

| Namespace | Capabilities | Source |
|-----------|--------------|--------|
| `cap.platform.*` | proxmox, routeros, openwrt, debian | class_ref |
| `cap.bootstrap.*` | cloud_init, netinstall, unattended, manual | mechanism |
| `cap.role.*` | hypervisor, router, edge_node, vpn_endpoint, container_host | enabled_capabilities |
| `cap.vendor.*` | proxmox, mikrotik, orangepi, oracle | vendor field |

---

## Gap Matrix

| Gap | AS-IS | TO-BE | Delta |
|-----|-------|-------|-------|
| Capability derivation | Manual in code | Automatic compiler | +1 compiler |
| Capability helpers | 1 function | 5 functions | +4 functions |
| Generator hardcodes | 14 patterns | 0 patterns | -14 patterns |
| Validator hardcodes | 10 patterns | 0 patterns | -10 patterns |
| Capability catalog | 188 caps | 205 caps | +17 caps |
| Backward compat | N/A | Legacy aliases | +1 mapping |

---

## Risk Summary

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Derivation misses edge case | Medium | Medium | Unit tests for all rules |
| Performance regression | Low | Low | Compile-time derivation |
| Breaking change to API | Low | High | Legacy aliases in Stage 1 |
| Incomplete migration | Medium | Medium | Wave-based approach |

---

## Decision: Option B (Derived Capabilities)

User selected **Option B** over alternatives:

| Option | Description | Selected |
|--------|-------------|----------|
| A: Full capability migration | All checks via explicit capabilities | No |
| **B: Derived capabilities** | Compiler auto-derives from metadata | **Yes** |
| C: Hybrid approach | Mixed explicit + convention-based | No |

**Rationale**: Minimizes topology changes while maximizing plugin flexibility. Capabilities become "markers/annotations of functionality" derived from existing object metadata.

---

## References

- `adr/capabilities-analysis/SWOT-CAPABILITIES.md` - Capability system SWOT
- `topology/class-modules/capability-catalog.yaml` - Current catalog
- ADR 0063, 0074, 0080 - Plugin architecture
