# Superseded ADRs Comparison Analysis

**Date:** 2026-03-06
**Focus:** Comparing ADR 0062 with superseded ADRs 0058-0061

---

## Overview

ADR 0062 supersedes four prior ADRs that explored different aspects of the v5 architecture. This analysis examines what was preserved, refined, and clarified through consolidation.

---

## ADR Evolution Matrix

| Aspect | ADR 0058 | ADR 0059 | ADR 0060 | ADR 0061 | ADR 0062 (Final) |
|--------|----------|----------|----------|----------|------------------|
| **Focus** | Core/Module separation | Class-Object-Instance model | YAML->JSON compilation | Version/Profile governance | **All unified** |
| **Status** | Superseded | Superseded | Superseded | Superseded | **Accepted** |
| **Model Contract** | Abstract type/Implementation | Class-Object-Instance | N/A | Class-Object-Instance | **Class-Object-Instance** ✅ |
| **Capability Model** | N/A | 3-layer w/ promotion rules | N/A | Capability + packs | **Simplified 3-layer** ✅ |
| **Compilation** | N/A | N/A | 5-stage pipeline | N/A | **5-stage pipeline** ✅ |
| **Diagnostics** | N/A | N/A | Schema-first, error catalog | N/A | **Schema-first** ✅ |
| **Profiles** | N/A | N/A | N/A | prod/modeled/test-real | **3 mandatory profiles** ✅ |
| **Version Lock** | N/A | N/A | N/A | model.lock mandatory | **model.lock mandatory** ✅ |
| **Repository Split** | Two-repo target | Two-repo conditional | N/A | Base + instance repos | **Conditional, no rush** ✅ |
| **Migration Plan** | Conceptual | Conceptual | N/A | Conceptual | **8 detailed phases** ✅ |
| **Dual-Track** | Mentioned | Mentioned | N/A | N/A | **Explicit v4/v5 separation** ✅ |
| **Plugin Model** | Module manifest idea | Module manifest | N/A | N/A | **Deferred to ADR 0063** ✅ |

---

## ADR 0058: Core Abstraction Layer

### Key Contributions

1. **Core/Module separation concept**
   - Identified 55-60% device-agnostic codebase
   - 40-45% device-specific components
   - Critical coupling points documented

2. **Two-layer architecture**
   - Core layer (`topology-core/`)
   - Implementation layer (`topology-modules/`)

3. **Generator protocols**
   - `TerraformGeneratorBase`
   - `BootstrapGeneratorBase`

### What ADR 0062 Changed

| ADR 0058 | ADR 0062 | Rationale |
|----------|----------|-----------|
| "abstract type" | "Class" | Clearer terminology |
| "implementation" | "Object" | Aligns with OOP concepts |
| Two-repo target | Conditional extraction | More conservative approach |
| Conceptual layout | Explicit directory structure | Implementation-ready |

### What Was Preserved

- ✅ Core/module separation principle
- ✅ Generator base classes
- ✅ Device-agnostic validation
- ✅ Module isolation strategy

### What Was Refined

- Terminology standardized to Class-Object-Instance
- Repository split made conditional with criteria
- Workspace layout made explicit

**Assessment:** ADR 0058 provided solid architectural foundation. ADR 0062 refined terminology and added implementation detail.

---

## ADR 0059: Class-Object-Instance Module Contract

### Key Contributions

1. **Canonical model:** `Class -> Object -> Instance`
2. **Merge rules:** `Class.defaults -> Object.defaults -> Instance.overrides`
3. **Invariant protection:** Instance cannot violate class invariants
4. **Capability model:** 3-layer with promotion rules
5. **Module manifest contract**

### What ADR 0062 Changed

| ADR 0059 | ADR 0062 | Rationale |
|----------|----------|-----------|
| Conceptual merge rules | Normative merge rules | Made binding contract |
| Capability model details | Simplified capability model | Reduced complexity |
| Module manifest format TBD | Deferred to plugin model | Sequencing clarity |
| General promotion rules | Explicit "2+ reuse" threshold | Measurable criteria |

### What Was Preserved

- ✅ Class-Object-Instance model
- ✅ Merge precedence chain
- ✅ Invariant protection rules
- ✅ Capability catalog + class + object binding
- ✅ Capability promotion concept

### What Was Refined

- Capability model simplified (no deep inheritance)
- Promotion rule made explicit (2+ object reuse)
- Vendor namespace rule (`vendor.*`)
- Module manifest deferred to plugin architecture

**Assessment:** ADR 0059 established core model. ADR 0062 simplified and operationalized it.

---

## ADR 0060: YAML-to-JSON Compiler and Diagnostics

### Key Contributions

1. **5-stage compilation:** load → normalize → resolve → validate → emit
2. **Dual output:** YAML for humans, JSON for machines
3. **Structured diagnostics:** JSON + text
4. **Error catalog:** Versioned codes (E1xxx, E2xxx, etc.)
5. **Compiler entry point:** `compile-topology.py`

### What ADR 0062 Changed

| ADR 0060 | ADR 0062 | Rationale |
|----------|----------|-----------|
| Conceptual stages | Fixed normative stages | Made binding |
| Diagnostic contract described | Diagnostic contract + schemas | Added references |
| Error catalog concept | Error catalog + file path | Made concrete |
| Integration unclear | Integrated with migration phases | Clear sequencing |

### What Was Preserved

- ✅ 5-stage compilation pipeline
- ✅ YAML source / JSON canonical
- ✅ Structured diagnostics
- ✅ Error catalog with stable codes
- ✅ Compiler entry point

### What Was Refined

- Stage IDs made normative (load, normalize, resolve, validate, emit)
- Diagnostic schema references added
- Error catalog location specified
- Integration with capability validation clarified

**Assessment:** ADR 0060 was nearly complete. ADR 0062 added minor refinements and integration points.

---

## ADR 0061: Base Repo with Versioned Class-Object-Instance

### Key Contributions

1. **Repository model:** Base repo + instance repos
2. **model.lock:** Mandatory version pinning
3. **Profile system:** production / modeled / test-real
4. **Profile substitution rules**
5. **Capability signature matching for profiles**

### What ADR 0062 Changed

| ADR 0061 | ADR 0062 | Rationale |
|----------|----------|-----------|
| Repository split assumed | Repository split conditional | More conservative |
| Profile contract conceptual | Profile contract normative | Made binding |
| Lock format TBD | Lock schema referenced | Made concrete |
| Test profiles unclear | `test-real` explicitly defined | Clear semantics |

### What Was Preserved

- ✅ model.lock as mandatory
- ✅ Core + class + object version pinning
- ✅ Three profile system
- ✅ Profile substitution compatibility rules
- ✅ Capability signature matching

### What Was Refined

- Repository split made conditional with criteria
- `test-real` profile semantics clarified
- Lock schema reference added
- Profile map schema reference added
- Substitution rules made more explicit

**Assessment:** ADR 0061 established governance model. ADR 0062 made it concrete and added extraction criteria.

---

## Consolidation Benefits

### 1. Single Source of Truth

**Before:** Four ADRs with potential inconsistencies
**After:** One normative document

**Benefit:** No ambiguity about which ADR to follow

### 2. Complete Migration Plan

**Before:** Conceptual migration ideas scattered across ADRs
**After:** 8 detailed phases with exit criteria

**Benefit:** Implementation-ready roadmap

### 3. Explicit Timeline

**Before:** No deprecation timeline
**After:** Specific dates for dual-mode, warnings, removal

**Benefit:** Predictable evolution

### 4. Workspace Clarity

**Before:** Ambiguous about v4/v5 coexistence
**After:** Explicit dual-track structure

**Benefit:** No confusion during migration

### 5. Reduced Scope Creep

**Before:** Plugin model intermixed with core model
**After:** Plugin deferred to ADR 0063

**Benefit:** Focused incremental delivery

---

## What Was Lost in Consolidation

### 1. Detail on Core Layer Components

**ADR 0058** had extensive tables of:
- Base layer components with file paths
- Device-specific components by vendor
- Critical coupling points

**Status in ADR 0062:** Abstracted away

**Impact:** Low - detail was analytical, not normative

**Mitigation:** Gap analysis (04-current-state-gap-analysis.md) can recover this

### 2. Backward Compatibility Field Evolution

**ADR 0059** had table of legacy fields:
- `type`, `class`, `model`, `role`
- Mapping to new fields

**Status in ADR 0062:** Simplified to general statement

**Impact:** Low - migration script has field mapping logic

**Mitigation:** Migration script (`migrate-to-v5.py`) is source of truth

### 3. Capability Model Nuances

**ADR 0059** had more detail on:
- Class capability inheritance (rejected)
- Object capability override rules
- Edge cases

**Status in ADR 0062:** Simplified to essential rules

**Impact:** Low - simplification was intentional

**Mitigation:** Capability model is simpler and more maintainable

---

## Terminology Evolution

| Concept | ADR 0058 | ADR 0059-0061 | ADR 0062 |
|---------|----------|---------------|----------|
| Abstract entity | "abstract type" | "Class" | **"Class"** ✅ |
| Concrete implementation | "implementation" | "Object" | **"Object"** ✅ |
| Deployed node | "concrete topology entry" | "Instance" | **"Instance"** ✅ |
| Core layer | "topology-core" | "base repo" | **"core model"** ✅ |
| Module layer | "topology-modules" | "object modules" | **"object modules"** ✅ |
| Freeze period | N/A | N/A | **"dual mode"** ✅ |
| Warning period | N/A | N/A | **"compiler warns"** ✅ |

**Final Terminology:** Consistent and clear across all contracts.

---

## Supersession Quality Assessment

### Completeness: ✅ EXCELLENT

All essential concepts from superseded ADRs are preserved in ADR 0062.

### Clarity: ✅ EXCELLENT

Consolidation eliminated conflicts and ambiguities.

### Actionability: ✅ EXCELLENT

Migration plan provides clear implementation path.

### Traceability: ⚠️ GOOD

ADR 0062 references superseded ADRs but doesn't provide detailed mapping.

**Improvement:** This analysis document fills the traceability gap.

---

## Recommendations

### For Future Consolidations

1. **Include Terminology Map**
   - Table showing old → new terms
   - Helps readers migrating from old ADRs

2. **Preserve Analytical Detail**
   - Link to superseded ADRs for background
   - Or include key tables as appendices

3. **Document What Changed**
   - Brief changelog section
   - Explains why supersession was needed

### For ADR 0062 Implementation

1. **Create Bridge Documents**
   - Map legacy field names to v5 fields
   - Link code references to ADR concepts

2. **Maintain Superseded ADRs**
   - Keep in repository for historical reference
   - Mark clearly as superseded
   - Link to successor

3. **Version Contract Documents**
   - Track which version of contract code implements
   - Enable contract evolution

---

## Conclusion

The consolidation from ADRs 0058-0061 to ADR 0062 is **high quality**:

- ✅ All essential content preserved
- ✅ Ambiguities resolved
- ✅ Terminology standardized
- ✅ Implementation path clarified
- ✅ Timeline established

**Minor Gaps:**
- Some analytical detail lost (acceptable)
- No explicit changelog (compensated by this analysis)

**Overall Assessment:** ✅ **SUCCESSFUL CONSOLIDATION**

The superseded ADRs should be retained for historical reference, but ADR 0062 is the sole normative source going forward.
