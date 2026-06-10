# Tech-Lead-Architect Review: ADR 0105

**Review Date:** 2026-06-10
**Reviewer:** tech-lead-architect agent
**ADR Version Reviewed:** Initial Proposed draft

---

## Executive Summary

ADR 0105 presents a well-structured approach to device state management using industry best practices. The simplified design (compared to the archived complex approach) correctly prioritizes tool-native mechanisms over custom systems.

**Recommendation:** Address Critical issues (C1-C3) before accepting ADR. Current status should be **Draft** pending resolution.

---

## Issue Classification

### Critical (Must Fix Before Acceptance)

| ID | Issue | Impact | Resolution |
|----|-------|--------|------------|
| C1 | **ADR 0085 Integration Gap** | Deploy state hierarchy not aligned with ADR 0085 bundle contract | ✅ RESOLVED: Updated D7 to use `.work/deploy-state/<project>/` |
| C2 | **Partial Apply Failure** | No documented recovery procedure for mid-apply Terraform failures | ✅ RESOLVED: Added D12 with recovery procedures |
| C3 | **Multi-Device Rollback** | No coordination mechanism when multiple devices change together | ✅ RESOLVED: Added D11 with consistency groups |

### High Priority (Should Address in Phase 1)

| ID | Issue | Impact | Recommendation |
|----|-------|--------|----------------|
| H1 | **Safe-mode Action Limit** | MikroTik safe-mode has 100 action limit; complex changes may exceed | Document mitigation: chunk large changes, or disable safe-mode with explicit operator acknowledgment |
| H2 | **State Recovery Procedure** | Terraform state corruption scenario not fully covered | Add D12 supplement for state recovery from remote backend versioning |
| H3 | **Generator Integration** | D8/D9 require generator template changes not yet specified | Add implementation guidance for existing generators |

### Medium Priority (Address Before Phase 2)

| ID | Issue | Impact | Recommendation |
|----|-------|--------|----------------|
| M1 | **Bundle ID Propagation** | D7/D8 use git_commit but ADR 0085 uses bundle_id | Clarify: git_commit is topology snapshot, bundle_id is deploy execution input; both should be tracked |
| M2 | **Verification Timeout** | D10 verification scripts lack timeout specification | Add configurable timeout (default 30s) with retry logic |
| M3 | **Ansible Integration** | D4 block/rescue/always pattern not integrated with D7 history | Consider logging Ansible execution outcomes to history.yaml |
| M4 | **Secret Rotation** | Backup encryption key rotation not addressed | Reference ADR 0072 key rotation procedure for age keys |

### Low Priority (Nice to Have)

| ID | Issue | Impact | Recommendation |
|----|-------|--------|----------------|
| L1 | **Observability** | No metrics/alerting integration | Consider Prometheus metrics for deploy success/failure tracking |
| L2 | **Dry-run Mode** | No safe preview of what `task deploy:confirm` will do | Add `--dry-run` flag to confirmation command |
| L3 | **History Pruning** | No retention policy for history.yaml | Add optional pruning with configurable retention |

---

## Strengths Identified

1. **Strong C19 Compliance** — Uses only industry-standard, tool-native mechanisms
2. **Clear Mental Model** — Topology snapshot → compile → apply → confirm → rollback point
3. **Explicit Operator Confirmation** — Critical safety gate with `task deploy:confirm`
4. **Per-Platform Metadata** — Each platform uses native storage (script/tags/freeform_tags)
5. **Encrypted Backups** — SOPS/age encryption with secure transfer workflow
6. **Idempotent Design** — Re-apply same snapshot = no change

---

## Gaps in Current Design

### Gap 1: Deploy Bundle Lifecycle Integration

ADR 0085 D1 defines deploy bundles as immutable execution inputs. ADR 0105 should clarify how:
- Bundle creation triggers backup (D5)
- Bundle execution maps to apply workflow
- Bundle ID is recorded alongside git SHA in history

**Suggested Addition to D7:**

```yaml
applies:
  - timestamp: "2026-06-10T14:00:00Z"
    git_commit: "abc12345..."      # Topology snapshot
    bundle_id: "b-202d573bd9d0"    # Execution bundle (ADR 0085)
    # ...
```

### Gap 2: Cross-ADR Dependency Matrix

| This ADR | Depends On | Integration Point |
|----------|------------|-------------------|
| D7 history location | ADR 0085 D6 | `.work/deploy-state/<project>/` |
| D5 backup workflow | ADR 0072 | SOPS/age encryption |
| D8/D9 generator changes | ADR 0074 | Generator template contracts |
| Rollback execution | ADR 0084 | DeployRunner workspace |

### Gap 3: MikroTik Safe-Mode Edge Cases

**100-action limit scenario:**

```
Large VLAN reconfiguration:
- 20 VLANs × 3 operations each = 60 actions
- 10 firewall rules × 4 operations each = 40 actions
- Total: 100 actions (at limit)

One more change = safe-mode history overflow
```

**Mitigation recommendations:**
1. Chunk large changes into multiple safe-mode sessions
2. For infrastructure refresh, explicitly disable safe-mode with operator acknowledgment
3. Document in `docs/guides/MIKROTIK-SAFE-MODE.md`

---

## Implementation Notes

### Phase Alignment

| ADR 0105 Phase | ADR 0085 Prerequisite | Notes |
|----------------|----------------------|-------|
| Phase 1 (D1-D5) | Core bundle contract | Can proceed independently |
| Phase 2 (D6-D7) | D6 state location | Must align paths |
| Phase 3 (D8-D10) | Generator integration | Needs coordination |
| Phase 4 (D11-D12) | None | New addition for C2/C3 |

### Test Coverage Requirements

| Decision | Unit Test | Integration Test | E2E Test |
|----------|-----------|------------------|----------|
| D3 Safe-mode | Mock API | Staging router | Production router |
| D5 Backup | File encryption | Transfer workflow | Full backup/restore |
| D7 History | Schema validation | File persistence | Multi-device tracking |
| D8 Metadata | Template rendering | API query | Cross-platform verify |
| D11 Consistency | Group creation | Rollback warning | Multi-device rollback |
| D12 Recovery | Failure injection | State restoration | Full recovery flow |

---

## Conclusion

ADR 0105 is architecturally sound after Critical issue resolution. The simplified approach correctly avoids over-engineering while providing necessary operational controls.

**Post-Review Status:** Draft → Proposed (after C1-C3 resolution verified)

**Next Actions:**
1. ✅ C1-C3 resolved in ADR document
2. Update SWOT analysis with D11/D12
3. Add H1-H3 implementation notes to Phase 1 documentation
4. Create `docs/guides/DEPLOY-RECOVERY.md` runbook

---

## References

- ADR 0083: Unified Node Initialization Contract
- ADR 0084: Cross-Platform Dev Plane and Linux Deploy Plane
- ADR 0085: Deploy Bundle and Runner Workspace Contract
- ADR 0072: Unified Secrets Management with SOPS and age
- ADR 0074: V5 Generator Architecture
