# ADR 0084: Gap Analysis

## Goal

Define the gap between the current mixed execution model and the target model:

- Cross-platform dev plane
- Linux-backed deploy plane
- Simple environment check (not abstraction layer)

---

## Current State

| Aspect | Status | Issue |
|--------|--------|-------|
| Dev workflows | ✅ Cross-platform | Python-based validation and compilation |
| Terraform/OpenTofu | ⚠️ Mixed | Can run on Windows, but should share runtime with Ansible |
| Ansible | ❌ Linux-only | Requires WSL on Windows |
| WSL glue | ⚠️ Hard-coded | `service_chain_evidence.py` has WSL-specific logic |
| Execution model | ❌ Undocumented | No explicit plane boundary defined |

---

## Target State

| Aspect | Target | Implementation |
|--------|--------|----------------|
| Dev plane | Cross-platform | No changes needed |
| Deploy plane | Linux required | `check_deploy_environment()` |
| Terraform + Ansible | Unified runtime | Both run from Linux/WSL |
| Documentation | Clear separation | OPERATOR-ENVIRONMENT-SETUP.md |

---

## Gap Items

### G1: No explicit plane boundary

**Current:** Implicit separation, not documented.
**Target:** ADR 0084 defines Dev plane vs Deploy plane.
**Action:** ADR 0084 created ✅

### G2: No environment check

**Current:** Deploy tools don't verify execution environment.
**Target:** `check_deploy_environment()` fails fast on Windows.
**Action:** Implement in `scripts/orchestration/deploy/environment.py`

### G3: No operator setup guide

**Current:** Scattered tool installation notes.
**Target:** Unified `OPERATOR-ENVIRONMENT-SETUP.md`.
**Action:** Create guide with WSL setup, tool installation, verification.

### G4: ADR 0083 missing execution context

**Current:** ADR 0083 doesn't specify where `init-node.py` runs.
**Target:** ADR 0083 references ADR 0084 for execution model.
**Action:** Add Phase 0 to ADR 0083 implementation plan.

---

## What We Are NOT Doing

| Gap | Why Not Addressed |
|-----|-------------------|
| Runner abstraction | YAGNI — single-operator home-lab doesn't need it |
| Docker backend | Defer until CI/CD integration needed |
| Remote-linux backend | Defer until dedicated control VM scenario |
| Backend selector | No multiple backends to select from |

**Principle:** Solve the actual problem (Ansible needs Linux) with minimal code (environment check). Abstract later when concrete need arises.

---

## Risks if Unchanged

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Confusing error on Windows | High | Medium | Clear exit message with WSL instructions |
| Terraform/Ansible runtime drift | Medium | Low | Document unified execution model |
| Future abstraction harder | Low | Low | Simple check is easy to extend |

---

## Acceptance Signal

ADR 0084 is successfully adopted when:

1. ✅ Plane separation documented in ADR
2. [ ] `check_deploy_environment()` implemented
3. [ ] Deploy tooling fails fast on Windows with clear message
4. [ ] OPERATOR-ENVIRONMENT-SETUP.md guides Windows users to WSL
5. [ ] ADR 0083 Phase 0 references environment check
