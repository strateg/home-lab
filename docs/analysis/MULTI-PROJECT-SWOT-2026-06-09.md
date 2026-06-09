# SWOT Analysis: Multi-Project Architecture

**Date:** 2026-06-09
**Mode:** SPC (Strict Process Compliance)
**Analyst:** tech-lead-architect agent

---

## Executive Summary

The multi-project architecture is **architecturally sound** with strong foundations in ADR 0075/0076/0081. The framework/project boundary, lock verification, and artifact distribution are well-specified and implemented.

However, the architecture is **operationally unproven** at N > 1 scale. The single `home-lab` project provides no validation of isolation guarantees, resource contention, or parallel execution correctness.

---

## Materials Reviewed

| # | Document | Status |
|---|----------|--------|
| 1 | CLAUDE.md | Read |
| 2 | ADR 0075 (framework-project-separation) | Read |
| 3 | ADR 0063 (plugin-microkernel) | Read |
| 4 | ADR 0076 (framework-distribution-multi-repo) | Read |
| 5 | ADR 0081 (framework-runtime-artifact-1:N) | Read |
| 6 | projects/home-lab/project.yaml | Read |
| 7 | topology/topology.yaml | Read |
| 8 | topology/framework.yaml | Read |
| 9 | multi_project_runner.py | Read |
| 10 | plugin_manifest_discovery.py | Read |
| 11 | framework.lock.yaml | Read |
| 12 | PROJECT-BOOTSTRAP-AND-FRAMEWORK-INTEGRATION.md | Read |

---

## Constraints Register

| ID | Constraint | Source | Type |
|----|------------|--------|------|
| C01 | Framework/project boundary separation | ADR 0075 | Structural |
| C02 | Single source of truth: topology.yaml | ADR 0062 | Architectural |
| C03 | Project-qualified output paths | ADR 0075 | Path resolution |
| C04 | Framework lock verification in strict mode | ADR 0076 | Security |
| C05 | Plugin discovery order: framework→class→object→project | ADR 0063 | Deterministic |
| C06 | 6-stage pipeline lifecycle | ADR 0080 | Runtime |
| C07 | Project self-sufficiency principle | ADR 0081 | Architectural |
| C08 | 1:N architecture (one framework, N projects) | ADR 0081 | Scalability |
| C09 | No legacy paths.* fallback | ADR 0075 | Migration |
| C10 | Version compatibility matrix | ADR 0075/0076 | Compatibility |
| C11 | Artifact exclusions (tests, ADRs, etc.) | ADR 0081 | Distribution |
| C12 | Dual-root path resolution | ADR 0081 | Path mechanics |
| C13 | Plugin ID global uniqueness | ADR 0063 | Plugin system |
| C14 | Hardware constraint: 8GB RAM | CLAUDE.md | Resource |
| C15 | Deterministic plugin merge order | ADR 0063 | Runtime |

---

## Diagnostic Findings

### FACT 1: Framework/Project Separation is Implemented
- `topology/` contains framework contracts (class-modules, object-modules)
- `projects/home-lab/` contains project-specific data (instances, secrets)
- `topology.yaml` explicitly declares `framework:` and `project:` sections

### FACT 2: Project Discovery Mechanism Exists
- `multi_project_runner.py` implements `discover_projects()` method
- Discovery scans `projects/` directory for `project.yaml`
- Currently only `home-lab` project exists

### FACT 3: Parallel Multi-Project Compilation is Implemented
- `MultiProjectRunner` supports async parallel execution
- Uses asyncio semaphore (`max_workers=4` default)
- Each project gets isolated PluginRegistry and PipelineState

### FACT 4: Plugin Discovery Supports Project-Level Plugins
- Discovery order: base_manifest → class_modules → object_modules → project_plugins
- Deterministic merge via lexicographic sorting
- Duplicate plugin IDs are hard errors

### FACT 5: Lock/Verification Contract is Complete
- `framework.lock.yaml` captures: version, source, revision, integrity hash
- Verification gates: E7822, E7823, E7824
- Version compatibility: E7811/E7812/E7813

### FACT 6: Two Consumption Modes Documented
- **Artifact-first** (canonical): zip distribution
- **Submodule** (legacy): git submodule reference

### FACT 7: Bootstrap Tooling Exists
- `bootstrap-project-repo.py`: generates manifests and lock
- `init-project-repo.py`: full project scaffolding

### FACT 8: Generated Outputs are Project-Namespaced
- Output structure: `generated/home-lab/`
- Contains: terraform/, ansible/, bootstrap/, docs/, wireguard/

### FACT 9: Only One Project Currently Exists
- `projects/home-lab/` is the sole project
- Multi-project runner has never been executed with N > 1

### FACT 10: Co-location Mode is Active
- Repository serves dual role: framework + project
- Tests reference both framework and project paths

---

## Problem Classification

| # | Finding | Category | Severity |
|---|---------|----------|----------|
| P01 | Single project in repository | Completeness | Low |
| P02 | No multi-project runtime validation | Testing | Medium |
| P03 | Parallel execution never validated with N>1 | Testing | Medium |
| P04 | Submodule still mentioned as option | Documentation | Low |
| P05 | Complex command-line interfaces | Usability | Medium |
| P06 | Project plugin root not widely used | Utilization | Low |
| P07 | Hardware constraint not project-aware | Resource | Low |
| P08 | No cross-project dependency support | Feature | N/A (by design) |
| P09 | Artifact trust (signature/provenance) phased | Security | Low |
| P10 | Path resolution requires dual understanding | Complexity | Medium |

---

## SWOT Analysis

### Strengths

| # | Strength | Evidence |
|---|----------|----------|
| S1 | **Well-Defined Boundary Contract** | ADR 0075, explicit framework/project sections in topology.yaml |
| S2 | **Comprehensive Lock/Verification System** | SHA-256 integrity, E7822-E7824 gates, version compatibility |
| S3 | **Deterministic Plugin Discovery Order** | Framework→class→object→project cascade, lexicographic sorting |
| S4 | **Artifact-First Distribution Model** | Self-contained framework artifact, SBOM provisions |
| S5 | **Parallel Compilation Infrastructure** | Async execution, isolated registries, semaphore-based limiting |
| S6 | **Comprehensive Tooling Ecosystem** | bootstrap-project-repo.py, init-project-repo.py, lock tools |
| S7 | **Dual-Root Path Resolution** | Same compiler in monorepo and standalone modes |

### Weaknesses

| # | Weakness | Impact |
|---|----------|--------|
| W1 | **No Real Multi-Project Validation** | Theoretical isolation not empirically tested |
| W2 | **Complex Command-Line Interface** | High cognitive load, error-prone manual invocation |
| W3 | **Co-location Coupling** | Mixed framework/project paths in tests |
| W4 | **Limited External Adoption Documentation** | No end-to-end tutorial for new projects |
| W5 | **Submodule Flow Still Documented** | Confusion about recommended path |
| W6 | **No Project-to-Project Dependency Model** | Projects fully isolated by design |
| W7 | **Trust Verification is Phased** | Signatures reserved but not enforced |

### Opportunities

| # | Opportunity | Benefit |
|---|-------------|---------|
| O1 | **Second Project as Validation Fixture** | Validate multi-project runtime with `projects/test-lab/` |
| O2 | **Task UX Layer for Complex Commands** | Reduce cognitive load via Go-Task wrappers |
| O3 | **Project Template Distribution** | Faster onboarding via cookiecutter/template |
| O4 | **Cross-Project Observability** | Unified diagnostics dashboard for N projects |
| O5 | **Framework Version Catalog** | Registry of releases with compatibility notes |
| O6 | **Hardware-Aware Compilation** | RAM budget allocation per project |
| O7 | **External Framework Repository Extraction** | True 1:N with independent release cadence |
| O8 | **Supply Chain Security Hardening** | SLSA, in-toto, Sigstore integration |

### Threats

| # | Threat | Risk |
|---|--------|------|
| T1 | **Untested Scalability** | Unknown behavior with 5+ concurrent projects |
| T2 | **Version Skew Risks** | Breaking changes require coordinated updates |
| T3 | **Operational Complexity Burden** | Lock management overhead × N projects |
| T4 | **Path Resolution Edge Cases** | Windows/Linux paths, symlink handling |
| T5 | **Plugin Collision Risk** | Global namespace with multiple project plugins |
| T6 | **Documentation Drift** | ADRs, guides, code may diverge |
| T7 | **Dependency on Co-located Development** | Breaking changes discovered late |
| T8 | **Orphaned Projects Risk** | No lifecycle management contract |

---

## Key Recommendation Areas

> Note: These are areas for potential action, not solutions (per SPC scope).

1. **Validation gap** — Multi-project runtime with N > 1
2. **UX simplification** — Complex CLI operations
3. **Supply chain security** — Completion of phased features
4. **Documentation consolidation** — External adopter path

---

## References

- ADR 0063: Plugin-based compiler architecture
- ADR 0075: Framework/project separation
- ADR 0076: Framework distribution and multi-repo
- ADR 0081: Framework runtime artifact 1:N

---

**Analysis completed under SPC protocol.**
