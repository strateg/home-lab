# SPC STEP 4: PROBLEM CLASSIFICATION

**Analysis Task:** Mermaid diagram generation — dependency graph visualization, unification, algorithm improvements, fixes

**Created:** 2026-04-22

**New Requirement Added:** Unified topology graph with domain/layer filtering

---

## Classification Methodology

Problems are classified by:
1. **Type** — Defect, Gap, Debt, Limitation
2. **Domain** — Which area is affected
3. **Impact** — User-facing, Developer-facing, System quality
4. **Priority** — Critical, High, Medium, Low
5. **Effort** — Small, Medium, Large
6. **Risk** — Breaking change risk (Low, Medium, High)

**No solutions are proposed in this step.**

---

## PROBLEM CLASS 1: Critical Defects (Must Fix)

### P1.1: ID Sanitization Inconsistency (Graph vs Table)

**Type:** Defect
**Source:** FACT 1.1
**Domain:** Service Dependencies
**Symptoms:**
- Graph shows `svc_grafana@docker_srv_orangepi5`
- Table shows `svc-grafana@docker.srv-orangepi5`
- User cannot correlate graph nodes to table entries

**Impact:** User-facing — confusing, looks like a bug
**Constraint Violation:** C7.2 (same instance_id must produce same safe_id)
**Priority:** 🔴 Critical
**Effort:** Small
**Risk:** Low (template-only fix)

---

### P1.2: Multiple Sanitization Patterns Across Templates

**Type:** Defect
**Source:** FACT 1.2, FACT 1.4
**Domain:** All diagram templates
**Symptoms:**
- 5 different inline sanitization patterns
- Pattern A: replace `.` and `-`
- Pattern B: replace `.`, `-`, `@`
- Pattern C: replace only `.`
- Same instance_id produces different sanitized IDs in different templates

**Impact:** System quality — non-deterministic, violates ADR 0005
**Constraint Violation:** C7.2, C1.8
**Priority:** 🔴 Critical
**Effort:** Medium
**Risk:** Medium (need to ensure all templates use same pattern)

---

### P1.3: Centralized `_safe_id()` Not Used Everywhere

**Type:** Defect
**Source:** FACT 1.3
**Domain:** Projection + Templates
**Symptoms:**
- `_safe_id()` exists in projections.py
- diagram_projection uses it (adds safe_id field)
- docs_projection does NOT add safe_id to service_dependencies
- Templates using docs_projection do inline sanitization

**Impact:** Developer-facing — code duplication, maintenance burden
**Constraint Violation:** C1.8 (ADR 0005 centralized helpers)
**Priority:** 🔴 Critical
**Effort:** Medium
**Risk:** Medium (need to change projection schema)

---

### P1.4: ADR 0005 Violation — Scattered Sanitization Logic

**Type:** Architectural Debt
**Source:** FACT 7.1
**Domain:** Templates
**Symptoms:**
- ADR 0005 mandates "centralized rendering helpers"
- Current implementation has sanitization logic scattered across 5+ templates
- Each template implements its own replace() filters

**Impact:** System quality — violates architectural decision, hard to change
**Constraint Violation:** C1.8
**Priority:** 🔴 Critical
**Effort:** Medium
**Risk:** Medium (architectural refactor)

---

## PROBLEM CLASS 2: High Priority Issues (Should Fix)

### P2.1: Two Separate Projection Paths

**Type:** Architectural Limitation
**Source:** FACT 2.1
**Domain:** Projection Architecture
**Symptoms:**
- diagram_generator uses build_diagram_projection()
- docs_generator uses build_docs_projection()
- Different schemas, different data availability
- Service dependencies only in docs_projection

**Impact:** Developer-facing — limits flexibility, hard to add features
**Constraint Violation:** None (but creates friction)
**Priority:** 🟡 High
**Effort:** Large
**Risk:** High (requires projection unification or bridge)

**Relation to REQ-NEW:** Unified topology graph needs data from BOTH projections (safe_id from diagram, service_dependencies from docs). Current split makes this hard.

---

### P2.2: Service Dependencies Not in Diagram Projection

**Type:** Gap
**Source:** FACT 2.2
**Domain:** Diagram Projection
**Symptoms:**
- build_diagram_projection() returns services with safe_id
- But does NOT include service_dependencies field
- Service dependency graph rendered by docs_generator, not diagram_generator

**Impact:** Developer-facing — inconsistent, diagram_generator can't render service deps
**Priority:** 🟡 High
**Effort:** Small
**Risk:** Low (add field to projection schema)

**Relation to REQ-NEW:** Unified topology graph needs service dependencies WITH safe_id. Currently impossible without merging projections.

---

### P2.3: Missing Node Dependency Graph

**Type:** Gap
**Source:** FACT 3.1, User Request
**Domain:** Feature
**Symptoms:**
- Service dependency graph exists
- Physical topology shows devices + data links
- But NO graph for: host dependencies (LXC → hypervisor), network dependencies (VLAN → router), storage dependencies

**Impact:** User-facing — cannot see full system dependencies
**Priority:** 🟡 High
**Effort:** Medium
**Risk:** Low (new feature, no breakage)

**Relation to REQ-NEW:** This IS the new requirement. Unified topology graph must show ALL dependencies, not just services.

---

### P2.4: Duplicate Logic Across Templates

**Type:** Technical Debt
**Source:** FACT 4.1
**Domain:** Templates
**Symptoms:**
- 5+ templates implement their own ID sanitization
- Code duplication, maintenance burden
- If sanitization logic changes, must update all templates

**Impact:** Developer-facing — high maintenance cost, bug risk
**Constraint Violation:** C1.8 (centralized helpers)
**Priority:** 🟡 High
**Effort:** Medium
**Risk:** Medium (template refactor)

---

### P2.5: No Test Coverage for Service Dependencies

**Type:** Gap
**Source:** FACT 8.1
**Domain:** Testing
**Symptoms:**
- test_projection_helpers.py tests other projections
- But NOT service_dependencies schema
- Changes to service_dependencies can break silently

**Impact:** System quality — regression risk
**Priority:** 🟡 High
**Effort:** Small
**Risk:** Low (add tests, no code change)

---

### P2.6: No Test Coverage for ID Sanitization Consistency

**Type:** Gap
**Source:** FACT 8.2
**Domain:** Testing
**Symptoms:**
- No test validates that _safe_id() and template inline sanitization produce same output
- Inconsistencies like P1.2 not caught by tests

**Impact:** System quality — defects slip through
**Priority:** 🟡 High
**Effort:** Small
**Risk:** Low (add tests)

---

## PROBLEM CLASS 3: Medium Priority Issues (Nice to Fix)

### P3.1: Deep Nesting in Docs Projection

**Type:** Limitation
**Source:** FACT 2.3
**Domain:** Projection Architecture
**Symptoms:**
- docs_projection nests domain projections: `{"network": {...}, "physical": {...}}`
- Templates access via `{{ projection.network.networks }}`
- Verbose, hard to read

**Impact:** Developer-facing — template verbosity
**Priority:** 🟢 Medium
**Effort:** Medium
**Risk:** Medium (template variable changes)

---

### P3.2: No Unified Dependency Graph

**Type:** Gap
**Source:** FACT 3.2, User Request
**Domain:** Feature
**Symptoms:**
- No visualization showing service + host + network + storage dependencies together
- Each domain has separate diagrams

**Impact:** User-facing — cannot see cross-domain dependencies
**Priority:** 🟢 Medium
**Effort:** Large
**Risk:** Low (new feature)

**Relation to REQ-NEW:** This is exactly the unified topology graph requirement.

---

### P3.3: No Dependency Cycle Detection

**Type:** Gap
**Source:** FACT 3.3
**Domain:** Validation
**Symptoms:**
- Service dependencies extracted without cycle validation
- Cyclic dependencies allowed (service A → B → A)
- Mermaid renders cycles, but may confuse users

**Impact:** User-facing — potentially invalid graphs
**Priority:** 🟢 Medium
**Effort:** Medium
**Risk:** Low (validation-only, no rendering change)

---

### P3.4: Inconsistent Variable Access Patterns in Templates

**Type:** Technical Debt
**Source:** FACT 4.2
**Domain:** Templates
**Symptoms:**
- Some templates: `{{ devices }}`
- Some templates: `{{ projection.services }}`
- Some templates: `{{ operations.backup_policies }}`
- No consistent pattern

**Impact:** Developer-facing — cognitive load, hard to learn
**Priority:** 🟢 Medium
**Effort:** Medium
**Risk:** Medium (template variable refactor)

---

### P3.5: Graph-Table Mismatch Confuses Users

**Type:** UX Issue
**Source:** FACT 9.1
**Domain:** User Experience
**Symptoms:**
- Graph shows sanitized IDs: `svc_grafana@docker_srv_orangepi5`
- Table shows original IDs: `svc-grafana@docker.srv-orangepi5`
- User must mentally map

**Impact:** User-facing — confusion, poor UX
**Priority:** 🟢 Medium (duplicate of P1.1, but UX perspective)
**Effort:** Small
**Risk:** Low

---

### P3.6: No Labels in Service Dependency Graph

**Type:** Limitation
**Source:** FACT 9.2
**Domain:** Feature
**Symptoms:**
- Dependency edges have no labels
- Cannot distinguish required vs optional dependencies
- No dependency reason shown

**Impact:** User-facing — graph shows THAT but not WHY
**Priority:** 🟢 Medium
**Effort:** Medium
**Risk:** Low (requires data model extension)

---

## PROBLEM CLASS 4: Low Priority Issues (Future Improvements)

### P4.1: Missing Template Schema Documentation

**Type:** Documentation Gap
**Source:** FACT 5.1
**Domain:** Documentation
**Symptoms:**
- Templates don't document which projection fields they expect
- Hard to understand template dependencies

**Impact:** Developer-facing — onboarding friction
**Priority:** 🔵 Low
**Effort:** Small
**Risk:** None (docs-only)

---

### P4.2: No Explicit Projection Contract Documentation

**Type:** Documentation Gap
**Source:** FACT 5.2
**Domain:** Documentation
**Symptoms:**
- Projection docstrings describe WHAT but not CONTRACT
- Missing: required fields, optional fields, types, breaking change policy

**Impact:** Developer-facing — schema drift risk
**Priority:** 🔵 Low
**Effort:** Small
**Risk:** None (docs-only)

---

### P4.3: Redundant Projection Building

**Type:** Performance Issue
**Source:** FACT 6.1
**Domain:** Performance
**Symptoms:**
- `_instance_groups()` called 6 times for same compiled_json
- Once in docs_projection + 5x in domain projections
- O(n) redundant parsing

**Impact:** System quality — performance (minor for current scale)
**Priority:** 🔵 Low
**Effort:** Medium
**Risk:** Medium (architectural change)

---

### P4.4: Deepcopy Memory Overhead

**Type:** Performance Issue
**Source:** FACT 6.2
**Domain:** Performance
**Symptoms:**
- Every device/service/lxc includes deepcopy of instance_data
- Memory overhead for large topologies

**Impact:** System quality — memory (minor for current scale)
**Priority:** 🔵 Low
**Effort:** Medium
**Risk:** Medium (may violate C3.1 immutability)

---

## NEW REQUIREMENT ANALYSIS

### REQ-NEW: Unified Topology Graph with Filtering

**Type:** Feature Request
**Source:** User
**Description:**
- New diagram (additional to existing)
- Shows: devices + services + networks + storage + operations
- Shows: physical links + host deps + service deps + network mgmt + storage bindings
- Filtering: by domain (physical/network/services/storage/ops) + by layer (L1-L7)
- Extensible architecture: universal graph core + specialized diagrams

**Blockers:**
1. **P2.1** — Two projection paths (need unified data source)
2. **P1.3** — safe_id not in docs_projection (need for all node types)
3. **P2.3** — Missing dependency types (need to extract host/network/storage deps)

**Prerequisites:**
1. Unified projection with ALL node types + ALL dependency types + safe_id for all
2. Graph rendering algorithm supporting filtering
3. Template supporting filter parameters

**Dependencies Needed:**
- `host_dependencies`: [{"node_id": "lxc-grafana", "depends_on": "srv-gamayun", "type": "hosted_on"}]
- `network_dependencies`: [{"node_id": "inst.vlan.servers", "depends_on": "rtr-mk", "type": "managed_by"}]
- `storage_dependencies`: [{"node_id": "svc-postgres", "depends_on": "vol-data", "type": "uses_volume"}]

**Complexity:** Large
**Effort:** 3-5 days (projection + template + tests)
**Risk:** Medium (new feature, but touches core projection)

---

## Problem Priority Matrix

| Priority | Count | Problems |
|----------|-------|----------|
| 🔴 Critical | 4 | P1.1, P1.2, P1.3, P1.4 |
| 🟡 High | 6 | P2.1, P2.2, P2.3, P2.4, P2.5, P2.6 |
| 🟢 Medium | 6 | P3.1, P3.2, P3.3, P3.4, P3.5, P3.6 |
| 🔵 Low | 4 | P4.1, P4.2, P4.3, P4.4 |
| **Total** | **20** | - |

---

## Problem Dependency Graph

```
REQ-NEW (Unified Topology Graph)
  ├─ BLOCKED BY: P2.1 (Two projection paths)
  ├─ BLOCKED BY: P1.3 (safe_id not everywhere)
  └─ BLOCKED BY: P2.3 (Missing node dependencies)

P1.1 (ID mismatch)
  └─ CAUSED BY: P1.3 (safe_id not in docs_projection)

P1.2 (Multiple sanitization patterns)
  └─ CAUSED BY: P1.4 (ADR 0005 violation)

P1.3 (safe_id not used everywhere)
  ├─ CAUSED BY: P2.1 (Two projection paths)
  └─ CAUSED BY: P1.4 (ADR 0005 violation)

P1.4 (Scattered sanitization)
  └─ ROOT CAUSE

P2.1 (Two projection paths)
  └─ ROOT CAUSE (architectural decision)

P2.3 (Missing node dependencies)
  └─ BLOCKS: REQ-NEW

P2.5, P2.6 (No tests)
  └─ ENABLES: Regression prevention
```

---

## Root Cause Analysis

**Root Cause 1: ADR 0005 Not Fully Implemented**
- Decision: "Use shared rendering helpers"
- Reality: Sanitization logic scattered across templates
- Leads to: P1.1, P1.2, P1.3, P1.4, P2.4

**Root Cause 2: Dual Projection Architecture**
- diagram_projection vs docs_projection split
- No unified data source
- Leads to: P2.1, P2.2, blocks REQ-NEW

**Root Cause 3: Service-Only Dependency Extraction**
- Only service dependencies extracted
- No host/network/storage dependencies
- Leads to: P2.3, blocks REQ-NEW

---

## Impact Analysis for REQ-NEW

**What REQ-NEW Requires:**

1. **Unified Projection** with all node types:
   - devices (with safe_id) ✅ from diagram_projection
   - services (with safe_id + dependencies) ❌ split across projections
   - networks (with safe_id) ✅ from diagram_projection
   - storage ❌ not in diagram_projection
   - operations ❌ not in diagram_projection

2. **All Dependency Types:**
   - service_dependencies ✅ exists
   - host_dependencies ❌ not extracted
   - network_dependencies ❌ not extracted
   - storage_dependencies ❌ not extracted
   - physical_links ✅ exists

3. **Filtering Logic:**
   - By domain ❌ not implemented
   - By layer ❌ not implemented

**Blockers Summary:**
- P2.1 (projection split) — HARD BLOCKER
- P1.3 (safe_id not everywhere) — HARD BLOCKER
- P2.3 (missing deps) — HARD BLOCKER

**Enablers:**
- Fix P1.3 → safe_id everywhere
- Fix P2.1 → unified projection OR projection merger
- Implement dependency extraction for host/network/storage

---

**PROBLEM CLASSIFICATION COMPLETE** ✅

**Total Problems:** 20 (4 critical, 6 high, 6 medium, 4 low)
**Root Causes:** 3
**REQ-NEW Blockers:** 3 hard blockers

Ready for **STEP 5: ADMISSIBLE SOLUTION SPACE**

**GO STEP 5?**
