# ADR 0062 Consolidation Analysis

**Date:** 2026-03-06
**Focus:** Architecture consolidation and normative contracts

---

## Executive Summary

ADR 0062 consolidates four prior ADRs (0058-0061) into a single normative contract for Topology v5. This consolidation eliminates ambiguity and provides clear implementation guidance while preserving the architectural direction established by the superseded ADRs.

---

## Architecture Contracts Analysis

### 1. Canonical Model Contract

**Decision:** `Class -> Object -> Instance` with explicit merge order

```
Instance.object_ref -> Object.class_ref -> Class
Effective: Class.defaults -> Object.defaults -> Instance.overrides
```

**Strengths:**
- Clear inheritance chain with no ambiguity
- Explicit merge precedence prevents conflicts
- Enforces invariant protection (instance cannot violate class)

**Implementation Requirements:**
- Link validator (`instance -> object -> class`)
- Merge engine respecting precedence
- Invariant checker at instance level

**Current State:**
- ✅ Conceptual model defined
- ⚠️ No v5 topology data with `class_ref`/`object_ref` yet
- ❌ Merge engine not implemented
- ❌ Invariant validation not implemented

### 2. Simplified Capability Model

**Decision:** Three-layer capability contract

1. **Capability catalog:** canonical IDs (flat, stable)
2. **Class contract:** `required_capabilities`, `optional_capabilities`, `capability_packs`
3. **Object binding:** `enabled_capabilities`, optional `enabled_packs`

**Guardrails:**
- No deep inheritance trees
- Vendor-only capabilities use `vendor.*` prefix
- Promotion rule: object-local capability → class pack when reused 2+ times

**Strengths:**
- Avoids capability sprawl
- Clear promotion path from object to class
- Vendor isolation via namespace

**Risks:**
- Manual governance required for promotion decisions
- No automated detection of reuse threshold

**Current State:**
- ✅ Example capability catalog exists (`capability-catalog.example.yaml`)
- ✅ Example capability packs exist (`capability-packs.example.yaml`)
- ❌ No operational catalog populated
- ❌ Capability checker partially implemented

### 3. YAML Source, JSON Canonical

**Decision:** Compilation pipeline with 5 fixed stages

1. `load` (YAML + include resolution)
2. `normalize` (canonical structure)
3. `resolve` (ID/reference + class-object-instance linkage)
4. `validate` (JSON schema + semantic checks)
5. `emit` (canonical JSON + diagnostics)

**Strengths:**
- Clear separation: humans author YAML, machines consume JSON
- Staged compilation enables progressive validation
- Deterministic output for AI repair loops

**Implementation Requirements:**
- Compiler orchestrator (`compile-topology.py`)
- Stage-specific handlers
- Diagnostics aggregator

**Current State:**
- ✅ Compiler entry point exists (`topology-tools/compile-topology.py`)
- ⚠️ Implementation status unknown (need to examine)
- ❌ Not integrated with migration workflow

### 4. Diagnostics Contract

**Decision:** Schema-first diagnostics with stable error codes

- JSON for AI systems
- Text report for humans
- Error catalog with versioned codes (`E1xxx`, `E2xxx`, etc.)

**Schemas:**
- `topology-tools/schemas/diagnostics.schema.json`
- `topology-tools/data/error-catalog.yaml`

**Strengths:**
- Machine-readable for automation
- Stable codes enable tooling
- Dual output for different audiences

**Current State:**
- ✅ Diagnostics schema exists
- ✅ Error catalog exists
- ❌ Integration with validators not confirmed
- ❌ No examples of diagnostic output

### 5. Profile System

**Decision:** Three mandatory profiles

- `production`: canonical behavior
- `modeled`: virtual substitutions for simulation
- `test-real`: test behavior on real hardware

**Rules:**
- Replacement object must satisfy class contract
- Replacement must satisfy required capability signature
- `test-real` must not replace hardware without approval

**Current State:**
- ✅ Profile map schema exists
- ✅ Example profile map exists
- ❌ No operational profile maps
- ❌ Profile validation not implemented

### 6. Version Lock

**Decision:** Mandatory `model.lock` for controlled runs

Pins:
- `core_model_version`
- class versions
- object versions
- object->class compatibility metadata

**Current State:**
- ✅ model.lock schema exists
- ✅ Example model.lock exists
- ❌ No operational lock file
- ❌ Lock validation not in CI

### 7. Backward Compatibility Timeline

**Decision:** Phased deprecation of legacy fields

- **2026-03-06 to 2026-06-30:** Dual mode allowed
- **From 2026-07-01:** Compiler warns on legacy-only; CI blocks new legacy
- **No earlier than 2026-10-01:** Remove legacy-only support

**Assessment:**
- Timeline is reasonable (7-month grace period)
- Clear milestones
- Allows gradual migration

**Risks:**
- Need to track which entities are still legacy-only
- CI enforcement mechanism not defined

### 8. Dual-Track Repository Separation

**Decision:** Explicit v4/ and v5/ workspace separation

**v4 track (frozen):**
```
v4/topology/
v4/topology-tools/
v4/tests/
v4-generated/
v4-build/
v4-dist/
```

**v5 track (active):**
```
v5/topology/
  ├── class-modules/
  ├── object-modules/
  ├── instances/home-lab/
  ├── model.lock.yaml
  └── profile-map.yaml
v5/topology-tools/
v5/tests/
v5-generated/
v5-build/
v5-dist/
```

**Governance:**
- No new features in v4
- All new work goes to v5
- Separate CI lanes

**Current State:**
- ❌ **CRITICAL:** v4/ and v5/ directories do not exist
- ❌ Artifact roots not renamed
- ❌ CI not split into lanes

**Impact:**
This is **Phase 0** and is the foundation for all other migration work.

### 9. Plugin Microkernel Alignment

**Decision:** Defer plugin migration until model parity achieved

Order:
1. Establish v5 model parity
2. Migrate execution to plugin microkernel (ADR 0063)

**Assessment:**
- Correct sequencing
- Avoids compounding complexity
- ADR 0063 is marked "Proposed" not "Accepted"

### 10. Repository Extraction

**Decision:** No immediate split

Extraction allowed only when:
- At least 3 independent topology consumers
- Independent release cadence required
- Compatibility matrix automation exists

**Assessment:**
- Conservative and correct
- Premature extraction would add overhead
- Criteria are measurable

---

## Consolidation Quality Assessment

### What ADR 0062 Improves Over 0058-0061

| Aspect | ADRs 0058-0061 | ADR 0062 |
|--------|----------------|----------|
| **Clarity** | Split across 4 documents | Single normative source |
| **Migration Plan** | Conceptual only | 8 detailed phases with criteria |
| **Workspace Layout** | Ambiguous | Explicit directory structure |
| **Timeline** | Undefined | Specific dates and milestones |
| **Artifacts** | Partial naming | Comprehensive naming (v4-*, v5-*) |
| **Governance** | General principles | Explicit rules (no v4 features, etc.) |

### Remaining Ambiguities

1. **CI Implementation Details**
   - Listed as "Open Question #1"
   - pre-commit vs CI-only for path guards
   - **Impact:** Medium - affects developer workflow

2. **Rollback Window Duration**
   - Listed as "Open Question #2"
   - After v5 cutover, how long to maintain v4?
   - **Impact:** Medium - affects resource allocation

3. **Class/Object Boundary Cases**
   - When exactly to promote object-local capability to class?
   - Who governs promotion decisions?
   - **Impact:** Low - can be resolved during implementation

4. **Migration Script Authority**
   - Is `migrate-to-v5.py` normative or advisory?
   - What happens when script and manual changes conflict?
   - **Impact:** Low - operational detail

---

## Contract Completeness Matrix

| Contract Area | Defined | Implemented | Validated | Operational |
|---------------|---------|-------------|-----------|-------------|
| Class-Object-Instance model | ✅ | ❌ | ❌ | ❌ |
| Capability model | ✅ | ⚠️ | ❌ | ❌ |
| YAML->JSON compilation | ✅ | ⚠️ | ❌ | ❌ |
| Diagnostics schema | ✅ | ⚠️ | ❌ | ❌ |
| Profile system | ✅ | ❌ | ❌ | ❌ |
| Version lock | ✅ | ❌ | ❌ | ❌ |
| Dual-track layout | ✅ | ❌ | ❌ | ❌ |
| Migration phases | ✅ | Phase 0 not started | ❌ | ❌ |
| Backward compat timeline | ✅ | ❌ | ❌ | ❌ |
| Plugin microkernel | ⚠️ (ADR 0063) | ❌ | ❌ | ❌ |

**Legend:**
- ✅ Complete
- ⚠️ Partial
- ❌ Not started

---

## Recommendations

### Immediate (Week 1-2)

1. **Accept ADR 0063** if not already accepted
   - Required for Phase 7
   - Impacts v5 runtime architecture

2. **Clarify Open Questions**
   - CI path guard implementation
   - Rollback window duration
   - Document decisions in ADR amendment or separate decision record

### Short-term (Month 1)

3. **Execute Phase 0**
   - This is blocking all other work
   - See [03-migration-plan-assessment.md](03-migration-plan-assessment.md) for detailed checklist

4. **Audit Existing Infrastructure**
   - Examine `compile-topology.py` implementation
   - Test diagnostics output
   - Verify capability checker functionality

### Medium-term (Month 2-3)

5. **Build Migration Automation**
   - Enhance `migrate-to-v5.py` with validation
   - Create inventory scripts for Phase 1
   - Build parity comparison tools for Phase 6

6. **Establish Governance Process**
   - Capability promotion review process
   - Class/object module approval workflow
   - CI enforcement mechanism

---

## Conclusion

ADR 0062 provides a comprehensive and implementation-ready consolidation of the v5 architecture. The primary gap is **execution** - Phase 0 has not been started and is blocking all downstream work.

The consolidation quality is high:
- Clear contracts
- Explicit migration plan
- Measurable completion criteria
- Reasonable timelines

**Overall Assessment:** ✅ **READY FOR IMPLEMENTATION**

**Blocker:** Phase 0 execution required before any other migration work can proceed.
