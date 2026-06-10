# SWOT Analysis: Simplified Device State Management (ADR 0105 Revised)

**ADR Reference:** 0105 (Revised — Industry Best Practices)
**Analysis Date:** 2026-06-10
**SPC Mode:** Active
**Supersedes:** `SWOT-ANALYSIS.md` (original complex approach)

---

## Executive Summary

This SWOT analysis evaluates the **simplified** ADR 0105 approach to device state management. Unlike the original complex "State Commit System" (now archived), this approach uses industry best practices from each tool:

- Terraform remote backend + VCS rollback
- MikroTik safe-mode for automatic rollback
- Ansible block/rescue/always for error handling
- Native platform metadata for snapshot propagation

---

## Concept Overview

```
topology.yaml (git SHA)
       │
       ▼
    COMPILE (ADR 0074, deterministic)
       │
       ▼
    GENERATE (Terraform, Ansible)
       │
       ▼
    BACKUP (D5: export + encrypt + transfer)
       │
       ▼
    APPLY (D3: safe-mode, D8: propagate snapshot)
       │
       ▼
    OPERATOR MANUAL VERIFICATION
       │
       ├──► Success ──► task deploy:confirm ──► rollback_point: true
       │                    (MANDATORY)
       └──► Failure ──► AUTO-REVERT (safe-mode) or manual rollback
```

**Key:** Without `task deploy:confirm`, apply is recorded but NOT a rollback point.

---

## SWOT Matrix

### Strengths (Internal Positive Factors)

| ID | Strength | Impact | Evidence |
|----|----------|--------|----------|
| S1 | **No custom systems (C19 compliance)** | Critical | D1-D10 use only native Terraform/Ansible/RouterOS/Proxmox/OCI mechanisms |
| S2 | **Aligned with project philosophy** | High | Topology = source of truth; Class→Object→Instance model preserved |
| S3 | **Explicit rollback points (D7)** | High | `rollback_point: true` set ONLY after operator `task deploy:confirm` |
| S4 | **Snapshot propagation to devices (D8)** | High | Each device knows its topology lineage via native metadata |
| S5 | **Secure backups (D5)** | High | SOPS/age encryption, transferred to deploy machine |
| S6 | **MikroTik safe-mode integration (D3)** | High | Hardware-level automatic rollback on connectivity loss |
| S7 | **Idempotent reproducibility** | High | Re-apply same snapshot = no change; reset + apply = same result |
| S8 | **Pre/post deploy verification (D10)** | Medium | Scripts query native APIs to verify snapshot consistency |
| S9 | **Low implementation effort** | Medium | ~28 hours across 3 phases; bash scripts + existing tools |
| S10 | **Git as rollback source (D6)** | High | `git checkout <sha> + compile + apply` = rollback |
| S11 | **Multi-device consistency groups (D11)** | High | Tracks related devices, warns on inconsistent rollback |
| S12 | **Documented recovery procedures (D12)** | High | Clear paths for partial apply failure recovery |
| S13 | **Capability-driven backup generation (D13)** | High | Backup roles generated from topology, scales with device count |

### Weaknesses (Internal Negative Factors)

| ID | Weakness | Impact | Mitigation |
|----|----------|--------|------------|
| W1 | **No single orchestrator** | Medium | Manual coordination required; could add Taskfile wrappers |
| W2 | **Tool-specific knowledge required** | Medium | Operator must know Terraform, Ansible, RouterOS; documentation helps |
| W3 | **Per-device verification** | Low | No central registry; must query each device API |
| W4 | **MikroTik safe-mode 9min timeout** | Low | Fixed by RouterOS; complex changes may exceed 100 action limit |
| W5 | **WiFi access-list Terraform gap** | Low | terraform-routeros doesn't support; use Ansible workaround |

### Opportunities (External Positive Factors)

| ID | Opportunity | Strategic Value | Implementation Path |
|----|-------------|-----------------|---------------------|
| O1 | **Taskfile unification** | High | Wrap all D1-D10 in `task deploy:*` commands |
| O2 | **CI/CD integration** | High | GitLab/GitHub Actions can automate compile→apply→verify |
| O3 | **Observability integration** | Medium | Post-apply health checks can feed Prometheus/Grafana |
| O4 | **Cross-project reuse** | Medium | ADR 0105 pattern applicable to other IaC projects |
| O5 | **terraform-routeros provider improvements** | Low | Community may add WiFi access-list support |

### Threats (External Negative Factors)

| ID | Threat | Severity | Mitigation |
|----|--------|----------|------------|
| T1 | **Network partition during apply** | High | MikroTik safe-mode auto-reverts; Terraform state versioning |
| T2 | **Terraform state corruption** | High | Remote backend versioning; backup before apply (D5) |
| T3 | **Operator error in rollback decision** | Medium | Explicit acknowledgment required (D7); verification scripts (D10) |
| T4 | **Device API unavailable for verification** | Medium | Scripts handle timeout gracefully; retry logic |
| T5 | **Snapshot metadata parsing failure** | Low | Structured format in script source; fallback to comment field |

---

## Comparison: Original vs Simplified Approach

| Aspect | Original (Archived) | Simplified (Current) |
|--------|---------------------|----------------------|
| Custom state machine | Yes (8 states) | No (use git + Terraform) |
| Snapshot service | Yes (custom) | No (native metadata) |
| Rollback coordinator | Yes (custom) | No (safe-mode + VCS revert) |
| Health check framework | Yes (custom ABC) | No (bash scripts + APIs) |
| Cross-device dependency graph | Yes (planned) | No (per-device rollback) |
| Implementation effort | 35 days | 28 hours |
| C19 compliance | Partial | **Full** |

---

## Gap Analysis Summary

| Gap ID | Description | Status | Resolution |
|--------|-------------|--------|------------|
| G1 | No explicit rollback point definition | ✅ CLOSED | D7 extended with `rollback_point` field |
| G2 | No formal acknowledgment mechanism | ✅ CLOSED | D7 acknowledgment workflow |
| G3 | No link git SHA ↔ device state | ✅ CLOSED | D8 snapshot propagation |
| G4 | Backup not encrypted | ✅ CLOSED | D5 amended with SOPS/age |
| G5 | Backup not transferred | ✅ CLOSED | D5 amended with SCP + cleanup |

**All identified gaps are now closed.**

---

## Risk Assessment Matrix

```
                    LIKELIHOOD
                    Low         Medium      High
            High  │           │    T1     │         │
   IMPACT  Medium │    T5     │    T2     │         │
            Low   │    W4     │    T3,T4  │   W3    │
                  └───────────┴───────────┴─────────┘
```

**Highest Risk:** T1 (Network partition) — mitigated by MikroTik safe-mode
**Second Risk:** T2 (State corruption) — mitigated by remote backend versioning + backups

---

## Constraint Satisfaction Matrix

| Constraint | Satisfied | Evidence |
|------------|-----------|----------|
| C01: Topology = source of truth | ✅ | D6, D7 — git SHA is the identifier |
| C05: Secrets encrypted | ✅ | D5 — SOPS/age for backups |
| C19: No custom systems | ✅ | D1-D10 use only native mechanisms |
| C21: Rollback Point definition | ✅ | D7 — `rollback_point: true` |
| C22: Idempotency | ✅ | Terraform/Ansible inherent property |
| C24: Snapshot to all devices | ✅ | D8 — native metadata per platform |
| C25: Device knows snapshot | ✅ | D8 — queryable via API |
| C26: Verification | ✅ | D10 — pre-deploy script |
| C27: Confirmation | ✅ | D10 — post-deploy script |
| C28: Backup encrypted | ✅ | D5 — SOPS/age |
| C29: Backup transferred | ✅ | D5 — SCP to deploy machine |
| C30: Operator confirmation mandatory | ✅ | D7 — `task deploy:confirm` required for rollback_point |

**All critical constraints satisfied.**

---

## Implementation Priority

| Phase | Focus | Effort | Risk |
|-------|-------|--------|------|
| Phase 1 | Foundation (D1-D5) | 8h | Low |
| Phase 2 | Automation (D6-D7) | 8h | Low |
| Phase 3 | Snapshot Propagation (D8-D10) | 12h | Medium |
| Phase 4 | Multi-Device & Recovery (D11-D12) | 8h | Medium |
| Phase 5 | Capability-Driven Backup (D13) | 6h | Low |
| **Total** | | **42h** | |

---

## Conclusion

The simplified ADR 0105 approach is **architecturally sound** and **fully compliant** with project constraints (C01-C30).

**Key Success Factors:**
1. Uses only industry-standard, tool-native mechanisms (C19)
2. Git SHA as unified snapshot identifier
3. Explicit rollback points with acknowledgment workflow
4. Secure, encrypted backups transferred to deploy machine
5. Per-device snapshot propagation via native metadata
6. Multi-device consistency groups for coordinated rollback (D11)
7. Documented recovery procedures for partial failures (D12)
8. Capability-driven backup role generation from topology (D13)

**Key Differences from Original:**
1. No custom state machine — use git + Terraform state
2. No custom snapshot service — use native metadata
3. No custom rollback coordinator — use safe-mode + VCS revert
4. Backup roles generated from capabilities — scales with device count
5. 42 hours vs 35 days implementation

**Recommendation:** Proceed with ADR 0105 implementation in 5 phases.

---

## References

- `adr/0105-device-state-commit-and-rollback-contract.md` — ADR document (D1-D12)
- `adr/0105-analysis/SIMPLIFIED-BEST-PRACTICES.md` — Industry patterns
- `adr/0105-analysis/SNAPSHOT-PROPAGATION-DESIGN.md` — D8/D9/D10 details
- `adr/0105-analysis/TECH-LEAD-REVIEW.md` — Architecture critique and recommendations
- `adr/0105-analysis/SWOT-ANALYSIS.md` — Original analysis (archived)
