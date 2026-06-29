# Architecture Analysis

**Date:** 2026-06-27
**Analyst:** Claude Code (claude-opus-4-5-20251101)
**Scope:** Full architectural review of Home-Lab Infrastructure-as-Data system
**Status:** Complete

---

## Executive Summary

The home-lab system is a mature Infrastructure-as-Data platform with strong ADR governance and developed plugin architecture. Key metrics:

| Metric | Value |
|--------|-------|
| Model Version | 5.0.0 (Class-Object-Instance) |
| Classes | 50 (L1-L7) |
| Objects | 128 |
| Instances | 164 |
| Plugins | 98+ across 6 pipeline stages |
| Tests | 1614 |
| ADRs | 110+ |
| Capabilities | 188+ |

**Overall Assessment:** B+ (Good with identified improvement areas)

---

## Critical Architectural Issues

### Issue 1: Monolithic Compiler

**File:** `topology-tools/compile-topology.py`
**Size:** 1828 lines of code

**Problem:** V5Compiler class has multiple responsibilities:
- AI advisory/assisted sessions management
- Framework lock verification
- Plugin registry management
- Diagnostics handling
- Multiple stage orchestration

**Violation:** Single Responsibility Principle (SOLID)

**Impact:**
- High cognitive load for developers
- Difficult to test in isolation
- Regression risk on changes

**Evidence:**
```python
class V5Compiler:
    # Lines 1-200: initialization and AI session handling
    # Lines 200-500: framework verification
    # Lines 500-900: plugin loading and registry
    # Lines 900-1200: stage orchestration
    # Lines 1200-1828: diagnostics and reporting
```

---

### Issue 2: Monolithic Plugin Configuration

**File:** `topology-tools/plugins/plugins.yaml`
**Size:** 2934 lines

**Problem:** Single file contains all 98+ plugin definitions with:
- Full configurations
- Dependencies
- Schemas
- Execution parameters

**Violation:** ADR 0082 module-pack composition principle

**Impact:**
- Navigation difficulty
- Merge conflicts in parallel development
- Long configuration load time
- Risk of accidental dependency changes

---

### Issue 3: Hardcoded Vendor Logic

**Problem:** Plugin selection uses string pattern matching instead of capabilities:

```python
# Current (problematic)
if "mikrotik" in object_ref.lower():
    return "mikrotik"

# Should be
if object.has_capability("network.routing.routeros"):
    return "mikrotik"
```

**Related ADR:** 0106 (Status: Proposed - not implemented)

**Violation:** Open/Closed Principle, Infrastructure-as-Data principles

**Impact:**
- Adding new device vendor requires code changes
- Fragile string-based logic

---

### Issue 4: Stalled Migration Status

**File:** `projects/home-lab/project.yaml`

```yaml
status: migration
legacy_metadata:
  generated_at: '2026-03-08T23:24:31+00:00'
  source_mapping: projects/home-lab/_legacy/v4-to-v5-mapping.yaml
```

**Problem:** Project in "migration" status for 4+ months (since March 2026)

**Impact:**
- Unclear applicability of legacy conventions
- Potential use of legacy artifacts from archive
- Uncertainty in project operational state

---

## Medium Priority Issues

### Issue 5: Layer Contract Desynchronization

**File:** `topology/layer-contract.yaml`

**Problem:** `class_layers` enumerated manually, not generated from class metadata:

```yaml
class_layers:
  class.compute.edge_node:
    allowed_layers: [L1, L4]
  class.compute.hypervisor:
    allowed_layers: [L1, L4]
  # ... 50+ manual entries
```

**Risk:** Desynchronization between `@layer` annotations in class YAML and layer-contract.yaml

---

### Issue 6: Incomplete ADRs in Proposed Status

**Found 4 ADRs stuck in Proposed status:**

| ADR | Title | Impact |
|-----|-------|--------|
| 0105 | Device State Commit and Rollback Contract | No rollback capability |
| 0106 | Capability-Driven Plugin Architecture | Vendor hardcoding continues |
| 0108 | Specification-Driven Development Contract | No formal spec validation |
| 0110 | Universal Network Zone and VLAN Configuration | Zone complexity |

**Risk:** Architectural decisions made without formalization create "grey zones"

---

### Issue 7: Object Module Duplication

**Problem:** 14 LXC objects with ~80% identical structure:

```
obj.proxmox.lxc.debian12.base.yaml
obj.proxmox.lxc.debian12.docker.yaml
obj.proxmox.lxc.debian12.gitea.yaml
obj.proxmox.lxc.debian12.grafana.yaml
... (10 more)
```

**Differences:** Only `@object`, `@title`, and specific configs vary

**Recommendation:** Use capability packs or parameterized templates

---

### Issue 8: Missing Dependency Graph Validation

**Problem:** Object dependencies (extends, refs) not formalized as DAG with validation

**Risk:**
- Circular dependencies possible
- Orphaned objects
- Broken refs during refactoring

---

### Issue 9: Superseded ADR Noise

**Statistics:**
- ADRs 0006-0025: Almost all superseded
- Indicates early architectural instability

**Recommendation:** Archive superseded ADRs to separate folder

---

### Issue 10: Capability Governance Gap

**File:** `topology/class-modules/capability-catalog.yaml`
**Size:** 188+ capabilities

**Problems:**
- No lifecycle policy (deprecation, versioning)
- No ownership assignment for capability domains
- Some capabilities marked deprecated inline without formal process

---

## Positive Architecture Aspects

| Aspect | Assessment | Notes |
|--------|------------|-------|
| ADR Governance | Excellent | 110+ documented decisions |
| Test Coverage | Very Good | 1614 tests with CI |
| Plugin Architecture | Good | 6-stage pipeline, microkernel pattern |
| Secrets Management | Good | SOPS/age integration (ADR 0072) |
| Framework/Project Separation | Good | Clean boundaries (ADR 0075, 0076) |
| AI Runtime Integration | Good | Advisory and assisted modes |
| Capability Design | Good | 188+ capabilities cataloged |

---

## Technical Debt Assessment

### Quantitative Assessment

| Category | Debt Volume | Priority |
|----------|-------------|----------|
| Compiler monolithicity | 1828 LOC in single class | Critical |
| Configuration monolith | 2934 lines in plugins.yaml | Critical |
| Migration debt | v4 legacy "migration" 4+ months | High |
| Incomplete ADRs | 4 Proposed without implementation | Medium |
| Object duplication | 14 LXC objects with 80%+ overlap | Low |

### Qualitative Assessment (Tech Debt Quadrant)

**Type:** Deliberate + Prudent

System was consciously built as monolith with decomposition plan (ADR 0063, 0069, 0080). Debt accumulates due to functionality priority over refactoring.

### SQALE Assessment (Simplified)

| Aspect | Rating | Comment |
|--------|--------|---------|
| Maintainability | C+ | Good documentation, high complexity |
| Reliability | B | 1614 tests, CI pipeline |
| Security | B | SOPS/age secrets, ADR 0072 |
| Testability | B+ | High coverage, plugin contract tests |

### Critical Debt Remediation Estimate

**Total:** 60-80 person-hours for critical issues (R1-R4)

---

## Architecture Diagrams

### Current State

```
┌─────────────────────────────────────────────────────────────────┐
│                        V5Compiler (1828 LOC)                    │
│  ┌──────────┬──────────┬──────────┬──────────┬──────────┐      │
│  │    AI    │ Framework│  Plugin  │  Stage   │Diagnostics│      │
│  │ Sessions │   Lock   │ Registry │Orchestr. │          │      │
│  └──────────┴──────────┴──────────┴──────────┴──────────┘      │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    plugins.yaml (2934 lines)                     │
│  ┌────────────────────────────────────────────────────────┐     │
│  │  98+ plugins: discoverers, compilers, validators,      │     │
│  │  generators, assemblers, builders - ALL IN ONE FILE    │     │
│  └────────────────────────────────────────────────────────┘     │
└─────────────────────────────────────────────────────────────────┘
```

### Target State

```
┌─────────────────┐
│CompilerOrchestra│  (thin orchestrator)
└────────┬────────┘
         │
    ┌────┴────┬─────────────┬──────────────┐
    ▼         ▼             ▼              ▼
┌───────┐ ┌───────┐ ┌────────────┐ ┌────────────┐
│  AI   │ │Frame- │ │  Plugin    │ │Diagnostics │
│Session│ │work   │ │  Registry  │ │  Manager   │
│Manager│ │Lock   │ │  Manager   │ │            │
└───────┘ └───────┘ └────────────┘ └────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                    plugins/ (sharded)                            │
│  manifests/                                                      │
│  ├── discoverers.yaml (~300 lines)                              │
│  ├── compilers.yaml (~500 lines)                                │
│  ├── validators.yaml (~600 lines)                               │
│  ├── generators.yaml (~800 lines)                               │
│  ├── assemblers.yaml (~400 lines)                               │
│  └── builders.yaml (~300 lines)                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## References

- ADR 0063: Plugin Architecture
- ADR 0069: Compiler Design
- ADR 0072: Secrets Management
- ADR 0075: Framework Separation
- ADR 0076: Project Separation
- ADR 0080: Pipeline Stages
- ADR 0082: Module-Pack Composition
- ADR 0106: Capability-Driven Architecture (Proposed)

---

## Metadata

```yaml
analysis_date: 2026-06-27
analysis_type: architectural_review
scope: full_system
methodology: tech-lead-architect-agent
findings:
  critical: 4
  medium: 6
  positive: 7
debt_estimate_hours: 60-80
overall_rating: B+
```
