# SPC STEP 3: DIAGNOSTIC ANALYSIS

**Analysis Task:** Mermaid diagram generation — dependency graph visualization, unification, algorithm improvements, fixes

**Created:** 2026-04-22

---

## Methodology

This is a **facts-only analysis**. All observations are documented without proposing solutions. Problems are classified in STEP 4.

---

## CATEGORY 1: ID Sanitization Issues

### FACT 1.1: Inconsistent ID Sanitization Between Graph and Table

**Location:** `generated/home-lab/docs/service-dependencies.md`

**Observation:**
- Mermaid graph node IDs: `svc_grafana@docker_srv_orangepi5` (sanitized)
- Table entries: `svc-grafana@docker.srv-orangepi5` (original)

**Evidence:**
```markdown
Graph: svc_grafana@docker_srv_orangepi5 --> svc_prometheus_docker_srv_orangepi5
Table: | svc-grafana@docker.srv-orangepi5 | svc-prometheus@docker.srv-orangepi5 |
```

**Root Cause:**
- Template `service-dependencies.md.j2` line 10: `{{ row.service_id | replace('.', '_') | replace('-', '_') }}`
- Template line 17: `{{ row.service_id }}` (no sanitization)

**Impact:** Graph uses sanitized IDs, table shows original IDs. Visual mismatch for users trying to correlate.

**Constraint Violation:** C7.2 — "Same instance_id MUST produce same safe_id across all diagrams"

---

### FACT 1.2: Multiple Inline Sanitization Patterns

**Location:** Multiple templates in `topology-tools/templates/docs/`

**Observation:**
Five different inline sanitization patterns exist across templates:

1. **Pattern A** (service-dependencies.md.j2 line 10):
   ```jinja2
   {{ row.service_id | replace('.', '_') | replace('-', '_') }}
   ```

2. **Pattern B** (service-dependencies.md.j2 line 10, depends_on):
   ```jinja2
   {{ row.depends_on | replace('.', '_') | replace('-', '_') | replace('@', '_') }}
   ```

3. **Pattern C** (network-diagram.md.j2 line 12):
   ```jinja2
   {{ zone.instance_id | replace('.', '_') }}
   ```

4. **Pattern D** (data-flow-topology.md.j2 line 11):
   ```jinja2
   {{ row.instance_id | replace('.', '_') | replace('-', '_') }}
   ```

5. **Pattern E** (physical-topology.md.j2 line 26):
   ```jinja2
   {{ link.endpoint_a.device_ref | default(...) | replace('.', '_') | replace('-', '_') }}
   ```

**Evidence:**
- Pattern A: 2 characters replaced (`.`, `-`)
- Pattern B: 3 characters replaced (`.`, `-`, `@`)
- Pattern C: 1 character replaced (`.`)
- Pattern D: 2 characters replaced (`.`, `-`)
- Pattern E: 2 characters replaced (`.`, `-`)

**Impact:** Same instance_id produces different sanitized IDs depending on which template renders it.

**Constraint Violation:** C7.2 — "Same instance_id MUST produce same safe_id across all diagrams"

---

### FACT 1.3: Centralized `_safe_id()` Function Exists But Not Used Everywhere

**Location:** `topology-tools/plugins/generators/projections.py:58-60`

**Observation:**
A centralized sanitization function exists:
```python
def _safe_id(value: str) -> str:
    """Make a string safe for use as a Mermaid node ID."""
    return value.replace(".", "_").replace("-", "_")
```

This function is used in `build_diagram_projection()` to add `safe_id` field to:
- devices (line 225)
- trust_zones (line 258)
- vlans (line 277)
- bridges (line 296)
- data_links (line 310)
- services (line 332)
- lxc (line 354)

**BUT:**
- `build_docs_projection()` does NOT add `safe_id` to service_dependencies (line 168)
- Templates using docs_projection perform inline sanitization instead

**Impact:** Duplication of logic, inconsistent results, violation of DRY principle.

**Constraint Violation:**
- C1.8 — "Use shared rendering helpers"
- ADR 0005 — "centralized rendering helpers"

---

### FACT 1.4: Inconsistent Sanitization Within Same Template

**Location:** `topology-tools/templates/docs/diagrams/physical-topology.md.j2`

**Observation:**
This template uses:
- **Pre-computed safe_id** for device nodes (line 15, 18, 20, 44-50)
- **Inline sanitization** for data_link endpoints (line 26-27)

**Evidence:**
```jinja2
Line 15: {{ device.safe_id }}@{ icon: "{{ device.icon }}", ... }
Line 26: {% set src = link.endpoint_a.device_ref | ... | replace('.', '_') | replace('-', '_') %}
```

**Impact:** Same device referenced as node uses safe_id, but same device referenced as link endpoint uses inline sanitization. Risk of mismatch if endpoint device_ref doesn't exactly match a device.instance_id.

---

## CATEGORY 2: Projection Architecture Issues

### FACT 2.1: Two Separate Projection Paths

**Location:**
- `diagram_generator.py` → `build_diagram_projection()`
- `docs_generator.py` → `build_docs_projection()`

**Observation:**
Two parallel projection builders exist with different schemas:

**diagram_projection schema:**
```python
{
    "devices": [...],      # with safe_id
    "trust_zones": [...],  # with safe_id
    "vlans": [...],        # with safe_id
    "bridges": [...],      # with safe_id
    "data_links": [...],   # with safe_id
    "services": [...],     # with safe_id
    "lxc": [...],          # with safe_id
    "counts": {...}
}
```

**docs_projection schema:**
```python
{
    "devices": [...],
    "services": [...],
    "service_dependencies": [...],  # NO safe_id
    "network": {...},
    "physical": {...},
    "security": {...},
    "storage": {...},
    "operations": {...},
    "counts": {...}
}
```

**Impact:** Templates must choose which projection to consume. Service dependency graph cannot use diagram_projection's safe_id because it's rendered by docs_generator.

---

### FACT 2.2: Service Dependencies Not in Diagram Projection

**Location:** `build_diagram_projection()` in projections.py:195

**Observation:**
The `build_diagram_projection()` function returns services with instance_id and safe_id, but does NOT extract or include service dependencies.

Service dependencies are only in `build_docs_projection()` (line 149-173).

**Impact:** diagram_generator cannot render service dependency graphs because the data is in the wrong projection.

---

### FACT 2.3: Domain Projections Are Nested in Docs Projection

**Location:** `build_docs_projection()` line 175-179

**Observation:**
```python
network_projection = build_network_projection(compiled_json)
physical_projection = build_physical_projection(compiled_json)
security_projection = build_security_projection(compiled_json)
storage_projection = build_storage_projection(compiled_json)
operations_projection = build_operations_projection(compiled_json)
```

Docs projection calls domain-specific projections and nests them in return value:
```python
return {
    ...
    "network": network_projection,
    "physical": physical_projection,
    ...
}
```

**Impact:** Templates access nested structures like `{{ projection.network.networks }}` or `{{ physical.devices }}`. Deep nesting makes template variables verbose.

---

## CATEGORY 3: Missing Features

### FACT 3.1: No Physical Node Dependency Graph

**Location:** User request: "Нужно создать диаграмму mermaid для визуализации связей между узлами, граф зависимостей"

**Observation:**
Service dependency graph exists (`service-dependencies.md`), but there is NO equivalent for:
- Device dependencies (which devices depend on which)
- Host dependencies (VM/LXC → hypervisor hosting relationship)
- Network dependencies (VLAN → router/switch management)

**Current State:**
- `physical-topology.md.j2` shows devices + data_links (L1 physical connections)
- But does NOT show logical dependencies (host_ref, managed_by_ref, etc.)

**Example Missing Visualization:**
```
lxc-grafana --> srv-gamayun (hosted on)
inst.vlan.servers --> rtr-mikrotik-chateau (managed by)
```

**Impact:** User cannot see dependency graph for physical/network topology, only for services.

---

### FACT 3.2: No Unified Dependency Graph

**Location:** User request: "унификацию улучшения алгоритмов"

**Observation:**
There is no unified dependency graph showing:
- Service dependencies
- Host dependencies
- Network dependencies
- Storage dependencies

in one visualization or with a common algorithm.

**Current State:**
- Service dependencies: rendered in `service-dependencies.md.j2`
- Data links: rendered in `physical-topology.md.j2`
- No other dependency types visualized

**Impact:** Cannot see cross-domain dependencies (e.g., service depends on network, network depends on device).

---

### FACT 3.3: No Dependency Cycle Detection

**Location:** Constraint Gap identified in STEP 2

**Observation:**
Service dependency extraction (projections.py:149-173) does NOT validate for cycles.

A service could depend on itself (directly or transitively), and this would not be detected or flagged.

**Impact:** Potential for invalid dependency graphs that cannot be resolved. Mermaid will render cyclic graphs, but they may be confusing to users.

---

## CATEGORY 4: Template Quality Issues

### FACT 4.1: Duplicate Logic Across Templates

**Location:** Multiple templates in `topology-tools/templates/docs/`

**Observation:**
The following templates all implement their own ID sanitization:
- `service-dependencies.md.j2`
- `data-flow-topology.md.j2`
- `network-diagram.md.j2`
- `rack-layout.md.j2`
- `physical-topology.md.j2` (partially)

**Evidence:** Grep results show 5+ templates with `replace('.', '_')` patterns.

**Impact:** Code duplication, maintenance burden, inconsistency risk.

**Constraint Violation:** C1.8 — "Use shared rendering helpers" (ADR 0005)

---

### FACT 4.2: Inconsistent Variable Access Patterns

**Location:** Templates accessing projection data

**Observation:**
Templates use different variable names and nesting levels:

- `diagrams/physical-topology.md.j2`: `{{ devices }}`, `{{ data_links }}`
- `diagrams/network-topology.md.j2`: `{{ trust_zones }}`, `{{ vlans }}`, `{{ bridges }}`
- `service-dependencies.md.j2`: `{{ service_dependencies }}`
- `data-flow-topology.md.j2`: `{{ projection.services }}`, `{{ operations.backup_policies }}`

**Impact:** No consistent access pattern. Some use top-level vars, some use `projection.X`, some use `operations.Y`.

---

## CATEGORY 5: Documentation and Metadata Issues

### FACT 5.1: Template Comments Missing Projection Schema

**Location:** All Jinja2 templates

**Observation:**
Templates do NOT document which projection fields they expect.

Example: `service-dependencies.md.j2` expects:
```jinja2
{% set deps = service_dependencies %}
```

But there is no comment indicating:
- Where `service_dependencies` comes from
- What schema it has
- Which projection builder produces it

**Impact:** Hard to understand template dependencies, hard to maintain.

---

### FACT 5.2: No Explicit Projection Contract Documentation

**Location:** Projection builder functions

**Observation:**
While docstrings exist (e.g., `build_diagram_projection()` line 196-206), they describe WHAT is returned but not the CONTRACT.

Missing:
- Required fields for each projection entry
- Optional fields
- Field type constraints
- Breaking change policy

**Impact:** Projection schema can drift, tests may not catch all breakage.

---

## CATEGORY 6: Performance and Optimization Issues

### FACT 6.1: Redundant Projection Building

**Location:** `build_docs_projection()` line 175-179

**Observation:**
`build_docs_projection()` calls 5 domain projections:
- build_network_projection()
- build_physical_projection()
- build_security_projection()
- build_storage_projection()
- build_operations_projection()

Each of these calls `_instance_groups(compiled_json)` independently.

**Evidence:** Check projections.py:18 and each domain projection file.

**Impact:** `_instance_groups()` is called 6 times (1 in docs_projection + 5 in domain projections) for the same compiled_json. Potential O(n) redundant parsing.

---

### FACT 6.2: Deepcopy of Instance Data

**Location:** `build_diagram_projection()` line 234

**Observation:**
```python
"instance_data": deepcopy(row.get("instance_data") or {}),
```

Every device/service/lxc entry includes a full deepcopy of instance_data.

**Impact:** Memory overhead for large topologies. instance_data can be large (contains all fields from compiled model).

**Note:** This may be intentional for isolation (C3.1), but worth noting for performance.

---

## CATEGORY 7: ADR Compliance Issues

### FACT 7.1: ADR 0005 Violation — Scattered Sanitization

**ADR:** ADR 0005 — "Introduce shared rendering helpers"

**Observation:**
ID sanitization is NOT centralized. Multiple templates implement their own sanitization (see FACT 1.2, FACT 4.1).

**Constraint Violation:** C1.8

**Impact:** Defeats the purpose of ADR 0005's centralization goal.

---

### FACT 7.2: ADR 0027 Compliance — Icon Modes Work

**ADR:** ADR 0027 — Icon mode contract (icon-nodes, compat, none)

**Observation:**
Templates `physical-topology.md.j2` and `network-topology.md.j2` correctly implement icon mode switching:

```jinja2
{% if use_mermaid_icons %}
    {{ device.safe_id }}@{ icon: "{{ device.icon }}", ... }
{% else %}
{% if icon_mode == 'compat' %}
    {{ device.safe_id }}["{{ device.instance_id }}<br/>{{ device.icon }}"]
{% else %}
    {{ device.safe_id }}["{{ device.instance_id }}<br/>{{ device.class_ref }}"]
{% endif %}
{% endif %}
```

**Impact:** ✅ This works correctly. No issue here.

---

### FACT 7.3: ADR 0079 Guidance — Tight Coupling Partially Resolved

**ADR:** ADR 0079 — V4→V5 migration, "tight coupling, scattered data resolution"

**Observation:**
V5 projection pattern successfully separates:
- Compiled model (input)
- Projection layer (transformation)
- Template layer (rendering)

BUT:
- Templates using docs_projection still perform inline sanitization (see FACT 1.3)
- Templates mix projection-provided data (safe_id) with inline transformations (replace filters)

**Impact:** Partial ADR 0079 compliance. Projection separation exists, but templates still have scattered logic.

---

## CATEGORY 8: Test Coverage Gaps

### FACT 8.1: No Tests for Service Dependency Projection

**Location:** Test suite

**Observation:**
- `test_projection_helpers.py` tests proxmox, mikrotik, ansible, bootstrap projections
- `test_generator_projection_contract.py` tests generator isolation
- BUT: No test for service_dependencies schema in `build_docs_projection()`

**Impact:** service_dependencies field schema is not contract-tested. Changes could break silently.

---

### FACT 8.2: No Tests for ID Sanitization Consistency

**Location:** Test suite

**Observation:**
No test validates that:
- `_safe_id()` produces same output as template inline sanitization
- Same instance_id produces same sanitized ID across all templates

**Impact:** Inconsistencies like FACT 1.2 are not caught by tests.

---

## CATEGORY 9: User Experience Issues

### FACT 9.1: Graph-Table Mismatch Confuses Users

**Location:** `generated/home-lab/docs/service-dependencies.md`

**Observation:**
User sees:
- Graph node: `svc_grafana@docker_srv_orangepi5`
- Table row: `svc-grafana@docker.srv-orangepi5`

**Impact:** User must mentally map sanitized IDs to original IDs. Not obvious which service is which if there are many similar names.

---

### FACT 9.2: No Labels in Service Dependency Graph

**Location:** `service-dependencies.md.j2`

**Observation:**
Graph edges have no labels:
```mermaid
svc_nextcloud@docker_srv_orangepi5 --> svc_postgresql
```

Could be enhanced with dependency metadata:
- Dependency type (required vs optional)
- Dependency reason (data store, monitoring, etc.)

**Current State:** Projection includes only `service_id` and `depends_on`. No metadata about dependency type.

**Impact:** Graph shows THAT dependencies exist, but not WHY or HOW CRITICAL they are.

---

## Summary Statistics

| Category | Facts Count | Severity |
|----------|-------------|----------|
| ID Sanitization Issues | 4 | 🔴 High |
| Projection Architecture Issues | 3 | 🟡 Medium |
| Missing Features | 3 | 🟡 Medium |
| Template Quality Issues | 2 | 🟡 Medium |
| Documentation Issues | 2 | 🟢 Low |
| Performance Issues | 2 | 🟢 Low |
| ADR Compliance Issues | 3 | 🟡 Medium |
| Test Coverage Gaps | 2 | 🟡 Medium |
| User Experience Issues | 2 | 🟡 Medium |
| **Total** | **23** | - |

---

## Critical Issues Summary

**HIGH Severity (must fix):**
1. FACT 1.1 — Graph-table ID mismatch
2. FACT 1.2 — Inconsistent sanitization patterns
3. FACT 1.3 — Centralized function not used
4. FACT 7.1 — ADR 0005 violation (scattered helpers)

**MEDIUM Severity (should fix):**
5. FACT 2.1 — Two projection paths
6. FACT 3.1 — Missing node dependency graph
7. FACT 4.1 — Duplicate logic across templates
8. FACT 8.1 — No service dependency tests

**LOW Severity (nice to have):**
9. FACT 5.1 — Missing template schema docs
10. FACT 6.1 — Redundant projection building

---

**DIAGNOSTIC ANALYSIS COMPLETE** ✅

**Total Facts Documented:** 23

Ready for **STEP 4: PROBLEM CLASSIFICATION**

**GO STEP 4?**
