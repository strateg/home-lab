# SWOT Analysis: Device State Commit System

**ADR Reference:** 0105 (Proposed)
**Analysis Date:** 2026-06-10
**SPC Mode:** Active

---

## Executive Summary

This SWOT analysis evaluates the proposed "Device State Commit System" concept for controlled state management across infrastructure devices (MikroTik, Proxmox, OrangePi, VPS). The concept proposes treating device state changes like git commits with pre/post validation and automatic rollback on failure.

### Concept Overview

```
topology.yaml (edit)
       |
       v
    COMPILE
       |
       v
    GENERATE (Terraform, Ansible, Bootstrap)
       |
       v
    STATE COMMIT REQUEST
       |
       +---> PRE-APPLY CHECKS
       |          |
       |          v (pass)
       |     APPLY (terraform apply / ansible-playbook)
       |          |
       |          v
       |     POST-APPLY CHECKS
       |          |
       |    (pass)|    (fail)
       |          |       |
       v          v       v
     COMMIT   ROLLBACK   ROLLBACK
     SUCCESS  TO PRIOR   TO PRIOR
              STATE      STATE
```

---

## SWOT Matrix

### Strengths (Internal Positive Factors)

| ID | Strength | Impact | Evidence from AS-IS |
|----|----------|--------|---------------------|
| S1 | **Aligns with Infrastructure-as-Data philosophy** | High | topology.yaml is already the single source of truth; this extends the model to runtime state |
| S2 | **Builds on proven ADR 0083-0085 foundation** | High | Deploy bundle/runner/workspace contracts already exist with 4 backends (native, wsl, docker, remote) |
| S3 | **State machine already implemented** | Medium | `scripts/orchestration/deploy/state.py` has working state transitions: `pending -> bootstrapping -> initialized -> verified` |
| S4 | **Adapter pattern is production-ready** | High | `BootstrapAdapter` ABC with preflight/execute/handover lifecycle exists in `adapters/base.py` |
| S5 | **Immutable deploy bundles provide audit trail** | High | `bundle.py` creates checksummed, versioned bundles with full provenance |
| S6 | **Terraform state provides inherent rollback capability** | Medium | Terraform state files allow `terraform state` operations and targeted destroy/recreate |
| S7 | **Structured logging infrastructure exists** | Medium | `InitNodeLogger` with JSONL audit trails in `.work/deploy-state/` |
| S8 | **Service-chain evidence pattern validates concept** | High | `service_chain_evidence.py` already implements multi-step plan/execute with failure handling |

### Weaknesses (Internal Negative Factors)

| ID | Weakness | Impact | Risk Mitigation |
|----|----------|--------|-----------------|
| W1 | **No native Terraform rollback mechanism** | Critical | Terraform does not have built-in rollback; must be implemented via state manipulation or re-apply |
| W2 | **MikroTik partial apply creates inconsistent state** | High | RouterOS API applies changes atomically per-resource, but multi-resource changes can partially fail |
| W3 | **Ansible idempotency does not equal reversibility** | High | Ansible can re-apply config, but cannot automatically reverse changes (no "ansible rollback") |
| W4 | **Hardware constraints limit snapshot-based rollback** | Medium | 8GB RAM on Proxmox limits VM/LXC snapshot capabilities |
| W5 | **Cross-device dependencies complicate rollback** | High | VLAN change on MikroTik affects Proxmox bridge config; rollback must be coordinated |
| W6 | **ADR 0083 is scaffold-only (hardware pending)** | Medium | `init_node.py` execution path exists but E2E tested only with mocks |
| W7 | **No pre-commit hook for topology validation** | Low | Changes can be committed without validation gate |
| W8 | **Secret-bearing rollback state needs secure storage** | Medium | Rollback artifacts may contain credentials requiring SOPS encryption |

### Opportunities (External Positive Factors)

| ID | Opportunity | Strategic Value | Implementation Path |
|----|-------------|-----------------|---------------------|
| O1 | **Unified configuration lifecycle across all devices** | Very High | Extend adapter pattern to cover commit/rollback alongside bootstrap |
| O2 | **Terraform import for existing infrastructure** | High | ADR 0083 D17 already defines import flow for brownfield devices |
| O3 | **MikroTik safe-mode integration** | High | RouterOS has `/system/safe-mode` with automatic revert on disconnect |
| O4 | **Proxmox snapshots for LXC/VM rollback** | Medium | Can snapshot before changes; limited by storage/RAM |
| O5 | **GitOps workflow integration** | High | Bundle hash links topology commit to deployed state |
| O6 | **Observability stack can validate post-apply health** | Medium | Prometheus/Grafana can provide automated health checks |
| O7 | **OCI Always Free tier provides test environment** | Medium | Oracle VPS can serve as isolated test target for rollback validation |
| O8 | **WireGuard tunnel enables secure remote apply** | Medium | Existing VPN infrastructure supports controlled apply window |

### Threats (External Negative Factors)

| ID | Threat | Severity | Mitigation Strategy |
|----|--------|----------|---------------------|
| T1 | **Network partition during apply causes split-brain** | Critical | Implement apply locks with lease expiry; require pre-apply connectivity check |
| T2 | **Rollback itself can fail** | Critical | Define rollback failure escalation path (manual intervention required) |
| T3 | **LTE failover complicates network-dependent rollback** | High | MikroTik LTE can change public IP; ensure rollback uses stable WireGuard tunnel |
| T4 | **Terraform state corruption prevents rollback** | High | Require state backups before apply; store in git-ignored but backed-up location |
| T5 | **Resource exhaustion during rollback** | Medium | Validate available resources before both apply and rollback |
| T6 | **Time-sensitive changes (certificates, DNS TTL)** | Medium | Some changes cannot be cleanly rolled back (expired cert, propagated DNS) |
| T7 | **Operator error in rollback decision** | Medium | Require explicit confirmation for destructive rollback operations |
| T8 | **Version drift between topology and device state** | Medium | Detect and warn when device state diverges from expected topology |

---

## Gap Analysis: AS-IS vs TO-BE

### Current State (AS-IS)

| Component | Status | Location |
|-----------|--------|----------|
| Topology compilation | Complete | `topology-tools/compile-topology.py` |
| Terraform generation | Complete | `plugins/generators/` for MikroTik, Proxmox, Oracle |
| Ansible generation | Complete | `base.generator.ansible_inventory`, `base.generator.ansible_role` |
| Deploy bundle creation | Complete | `scripts/orchestration/deploy/bundle.py` |
| Deploy runner abstraction | Complete | `scripts/orchestration/deploy/runner.py` (4 backends) |
| Bootstrap adapters | Scaffold | `adapters/netinstall.py`, `unattended.py`, `cloud_init.py`, `ansible_bootstrap.py` |
| State machine | Complete | `state.py` with legal transitions |
| Service-chain execution | Complete | `service_chain_evidence.py` with plan/execute/report |
| Handover verification | Scaffold | Adapter `handover()` method exists but minimal implementation |

### Target State (TO-BE)

| Component | Gap | Priority | Complexity |
|-----------|-----|----------|------------|
| **State Snapshot Service** | Missing | P1 | High |
| **Pre-Apply Validation Gate** | Partial (Terraform validate exists) | P1 | Medium |
| **Post-Apply Health Check Framework** | Missing | P1 | Medium |
| **Rollback Coordinator** | Missing | P1 | Critical |
| **Cross-Device Dependency Graph** | Missing | P2 | High |
| **MikroTik Safe-Mode Integration** | Missing | P2 | Medium |
| **Commit History/Audit Trail** | Partial (bundle checksums exist) | P2 | Low |
| **Operator Confirmation UX** | Partial (args flags exist) | P3 | Low |
| **Drift Detection** | Missing | P3 | Medium |

### Component Responsibility Matrix

| Concern | Current Owner | Proposed Owner | Change Required |
|---------|---------------|----------------|-----------------|
| Pre-apply validation | terraform validate | StateCommitOrchestrator | Integration |
| Apply execution | terraform apply / ansible-playbook | Existing (via runner) | None |
| Post-apply checks | None | HealthCheckFramework | New component |
| Rollback decision | None | RollbackCoordinator | New component |
| Rollback execution | Manual | RollbackCoordinator + Adapters | Extend adapters |
| State persistence | bundle.py + state.py | StateSnapshotService | New component |
| Audit logging | InitNodeLogger | Extend for commits | Extension |

---

## ADR Requirements

### New ADRs Required

| ADR # | Title | Scope | Dependencies |
|-------|-------|-------|--------------|
| 0105 | Device State Commit and Rollback Contract | Define commit/rollback lifecycle | ADR 0083, 0085 |
| 0106 | Pre/Post Apply Health Check Framework | Health validation contracts | ADR 0105 |
| 0107 | MikroTik Safe-Mode Rollback Integration | RouterOS-specific rollback | ADR 0105 |

### ADR Extensions Required

| ADR # | Extension | Reason |
|-------|-----------|--------|
| 0083 | Add commit/rollback states to state machine | Extend `LEGAL_TRANSITIONS` |
| 0085 | Define rollback bundle structure | Snapshot storage in bundle |
| 0074 | Add rollback generator outputs | Generate rollback artifacts |

---

## Risk Assessment Matrix

```
                    LIKELIHOOD
                    Low    Medium    High
            High  |  W8  |   W5   |  T2,T4 |
IMPACT    Medium  |  W7  |   W2   |  W1,T1 |
            Low   |  O4  |   T7   |   T8   |
```

### Critical Risks (Require Immediate Mitigation)

1. **T1 + W1: Network partition + No native Terraform rollback**
   - Mitigation: Implement state snapshot before apply; require explicit rollback trigger
   - Fallback: Manual recovery procedure documented

2. **T2 + W3: Rollback failure + Ansible non-reversibility**
   - Mitigation: Define "known good state" checkpoints; manual intervention escalation
   - Fallback: Restore from backup rather than rollback

3. **W5: Cross-device dependencies**
   - Mitigation: Build dependency graph; validate rollback order
   - Fallback: Full-topology rollback as atomic unit

---

## Recommendations

### Phase 1: Foundation (Priority P1)

1. **Define State Commit Lifecycle in ADR 0105**
   - States: `pending -> validating -> applying -> verifying -> committed | rolling_back -> rolled_back | failed`
   - Extend `state.py` with new states

2. **Implement Pre-Apply Validation Gate**
   - Integrate with existing `terraform validate` and `ansible --syntax-check`
   - Add topology-level validation (no orphan references, resource constraints)

3. **Create State Snapshot Service**
   - Capture Terraform state files before apply
   - Store in `.work/deploy-state/<project>/snapshots/`
   - Link to bundle_id for traceability

4. **Implement Post-Apply Health Check Framework**
   - Define health check contract per device type
   - MikroTik: API reachable, critical services running
   - Proxmox: API reachable, VMs/LXC status
   - Network: Critical IPs pingable

### Phase 2: Rollback Capability (Priority P2)

5. **Implement Rollback Coordinator**
   - Decision logic: automatic vs manual rollback
   - Timeout-based automatic rollback (safe-mode pattern)
   - Cross-device ordering awareness

6. **Integrate MikroTik Safe-Mode**
   - Leverage RouterOS `/system/safe-mode` for network changes
   - Automatic revert on connection loss

7. **Build Cross-Device Dependency Graph**
   - Parse topology for inter-device references
   - Validate rollback order respects dependencies

### Phase 3: UX and Observability (Priority P3)

8. **Implement Drift Detection**
   - Compare device state to expected topology
   - Warn before apply if drift detected

9. **Create Operator Confirmation UX**
   - Interactive confirmation for destructive changes
   - Dry-run with explicit diff output

10. **Integrate with Observability Stack**
    - Post-apply metrics collection
    - Automated health dashboards

---

## Implementation Effort Estimates

| Component | Effort (days) | Dependencies | Risk |
|-----------|---------------|--------------|------|
| ADR 0105 definition | 2 | None | Low |
| State machine extension | 1 | ADR 0105 | Low |
| Pre-apply validation | 3 | Existing validators | Medium |
| State snapshot service | 3 | bundle.py | Medium |
| Post-apply health checks | 5 | Adapter pattern | Medium |
| Rollback coordinator | 8 | All above | High |
| MikroTik safe-mode | 3 | Rollback coordinator | Medium |
| Dependency graph | 5 | Topology compiler | High |
| Drift detection | 5 | Terraform state | Medium |
| **Total** | **35 days** | | |

---

## Conclusion

The "Device State Commit System" concept is **architecturally sound** and **well-aligned** with the existing infrastructure-as-data philosophy. The project already has ~70% of the foundation in place through ADR 0083-0085 and the deploy domain implementation.

**Key Success Factors:**
1. Leverage existing adapter pattern for rollback operations
2. Start with MikroTik safe-mode integration as proof-of-concept
3. Accept that some changes are inherently non-reversible
4. Implement progressive rollback (per-device before cross-device)

**Key Risks to Monitor:**
1. Cross-device dependency coordination
2. Network partition during apply/rollback
3. Terraform state corruption scenarios

**Recommendation:** Proceed with ADR 0105 definition focusing on the commit lifecycle contract. Defer full rollback automation to Phase 2 after validating the health check framework.

---

## Appendix A: State Machine Extension

```yaml
# Proposed state transitions for commit lifecycle
COMMIT_TRANSITIONS:
  pending:
    - validating
  validating:
    - applying
    - failed
  applying:
    - verifying
    - rolling_back
  verifying:
    - committed
    - rolling_back
  committed:
    - pending  # new commit cycle
  rolling_back:
    - rolled_back
    - failed
  rolled_back:
    - pending  # retry
  failed:
    - pending  # retry with fixes
```

## Appendix B: Device-Specific Rollback Strategies

| Device | Primary Strategy | Fallback Strategy |
|--------|------------------|-------------------|
| MikroTik | Safe-mode + script revert | Restore from backup.rsc |
| Proxmox VMs | Snapshot restore | Re-create from topology |
| Proxmox LXC | Snapshot restore | Re-create from topology |
| OrangePi | Ansible re-apply previous state | Re-image SD card |
| Oracle VPS | Terraform destroy + re-create | OCI console restore |

## Appendix C: Related Files

| File | Purpose | Relevance |
|------|---------|-----------|
| `/home/nixos/workspaces/home-lab/scripts/orchestration/deploy/state.py` | State machine | Extend for commit states |
| `/home/nixos/workspaces/home-lab/scripts/orchestration/deploy/bundle.py` | Bundle creation | Add snapshot storage |
| `/home/nixos/workspaces/home-lab/scripts/orchestration/deploy/runner.py` | Execution backend | Use for apply/rollback |
| `/home/nixos/workspaces/home-lab/scripts/orchestration/deploy/adapters/base.py` | Adapter contract | Extend for rollback |
| `/home/nixos/workspaces/home-lab/scripts/orchestration/deploy/init_node.py` | Bootstrap orchestrator | Pattern for commit orchestrator |
| `/home/nixos/workspaces/home-lab/topology-tools/utils/service_chain_evidence.py` | Multi-step execution | Pattern for commit chain |
| `/home/nixos/workspaces/home-lab/adr/0083-unified-node-initialization-contract.md` | Init contract | Foundation ADR |
| `/home/nixos/workspaces/home-lab/adr/0085-deploy-bundle-and-runner-workspace-contract.md` | Bundle contract | Foundation ADR |
