# ADR 0083: Gap Analysis

## Executive Summary

This document analyzes the gap between the current fragmented node initialization approach and the target unified initialization contract defined in ADR 0083.

---

## AS-IS State

### Device Initialization Inventory

| Device | Location | Lines | Day-0/Day-1 Mixed | Topology Integration | Handover Verification |
|--------|----------|-------|-------------------|---------------------|----------------------|
| MikroTik | `topology/object-modules/mikrotik/templates/bootstrap/` | ~100 | No (clean) | Yes | Manual |
| Proxmox | `archive/.../proxmox-post-install.sh` | 487 | **Yes** | No | None |
| Orange Pi | `topology/object-modules/orangepi/templates/` | ~20 | N/A (placeholder) | Partial | None |
| LXC | `archive/.../install-lxc-containers.sh` | ~200 | **Yes** | No | None |

### Current Bootstrap Artifacts

```
generated/home-lab/bootstrap/
  rtr-mikrotik-chateau/
    init-terraform.rsc           # Generated from topology
    terraform.tfvars.example     # Generated from topology

topology/object-modules/mikrotik/templates/bootstrap/
  init-terraform.rsc.j2
  backup-restore-overrides.rsc.j2
  terraform.tfvars.example.j2

topology/object-modules/proxmox/templates/bootstrap/
  answer.toml.example.j2         # Exists
  script.sh.j2                   # Exists (post-install stub)

topology/object-modules/orangepi/templates/bootstrap/
  user-data.example.j2           # Placeholder only
```

### Issues Identified

1. **No Unified Contract Schema**
   - MikroTik: ADR 0057 defines contract informally in ADR text
   - Proxmox: No formal contract
   - Orange Pi: No contract
   - LXC: No contract (uses community scripts)

2. **Day-0/Day-1 Boundary Violations**
   - `proxmox-post-install.sh` contains:
     - HDD storage pool creation (day-1)
     - KSM optimization (day-1)
     - Package installation beyond API access (day-1)
     - Repository configuration (day-1)

3. **No Initialization Manifest**
   - No central registry of nodes and their initialization status
   - No machine-readable handover requirements

4. **Missing Validators**
   - No schema validation for initialization contracts
   - No pre-flight checks in v5 pipeline

5. **Secret Handling Inconsistency**
   - MikroTik: Ansible Vault -> `.work/native/`
   - Proxmox: Hardcoded or environment variables
   - Orange Pi: None documented

---

## TO-BE State

### Target Contract Structure

Compute/router object modules MAY declare `initialization_contract`. Objects without a contract are treated as **implicitly terraform-managed** — they require no bootstrap phase and are created entirely via Terraform:

```yaml
# OPTIONAL - only for devices requiring day-0 bootstrap
initialization_contract:
  version: "1.0"
  mechanism: netinstall | unattended_install | cloud_init | ansible_bootstrap
  requirements: [...]
  bootstrap:
    template: templates/bootstrap/...
    outputs: [...]
  handover:
    provider: <terraform-provider>
    checks: [...]
```

**Key principle**: No contract = implicit terraform-managed. This simplifies LXC, Cloud VM, and other Terraform-created resources.

### Target Artifact Structure

```
generated/home-lab/bootstrap/
  INITIALIZATION-MANIFEST.yaml    # NEW: static registry (read-only)
  rtr-mikrotik-chateau/
    init-terraform.rsc
    terraform.tfvars.example
  hv-proxmox-xps/                 # NEW
    answer.toml
    post-install-minimal.sh
  sbc-orangepi5/                  # NEW
    user-data
    meta-data

.work/native/bootstrap/
  INITIALIZATION-STATE.yaml       # NEW: mutable runtime status store
```

### Target Orchestration

```
scripts/orchestration/
  lane.py                         # Existing v5 pipeline
  init-node.py                    # NEW: initialization orchestrator
```

---

## Gap Items

### G1: Schema Definition

| Item | Status | Action Required |
|------|--------|-----------------|
| `initialization-contract.schema.json` | Missing | Create schema |
| Object module schema extension | Missing | Add `initialization_contract` field |
| Validator plugin | Missing | Create `base.validator.initialization_contract` |

### G2: MikroTik (Reference Implementation)

| Item | Status | Action Required |
|------|--------|-----------------|
| Bootstrap template | Complete | No change |
| ADR 0057 contract | Documented | Extract to YAML in object module |
| Generator plugin | Complete | Minor update to read contract |
| Handover checks | Implicit | Add explicit check definitions |

### G3: Proxmox VE

| Item | Status | Action Required |
|------|--------|-----------------|
| `answer.toml.j2` | Exists | Review and enhance |
| `post-install-minimal.sh` | Missing | Extract from 487-line script |
| Day-1 config extraction | Not done | Move to Terraform/Ansible |
| Object module contract | Missing | Create `obj.proxmox.ve.yaml` |
| Generator plugin | Missing | Create `obj.proxmox.generator.bootstrap` |
| **Pre-validation (D16)** | Missing | Implement mandatory answer.toml validation |
| **Day-1 leakage audit** | Not done | Audit existing script for day-1 config in bootstrap |

**Pre-Validation Requirement (D16):**

Because `unattended_install` is destructive (formats disks), `init-node.py` MUST validate `answer.toml` before prompting for USB media creation:

- TOML syntax validation (E9715)
- Required sections: `[global]` (E9710), `[network]` (E9711), `[disk-setup]` (E9712)
- Disk path validation (E9713)
- Network consistency check (W9714 warning)
- `--confirm-destructive` flag required

**Proxmox Script Decomposition:**

Current `proxmox-post-install.sh` contains:
```
Lines 1-50:    Repository setup           -> Phase 1 (Terraform)
Lines 51-120:  Package installation       -> Phase 2 (Ansible)
Lines 121-200: HDD storage pool           -> Phase 1 (Terraform)
Lines 201-280: Network bridge setup       -> Phase 1 (Terraform)
Lines 281-350: KSM optimization           -> Phase 2 (Ansible)
Lines 351-400: Laptop-specific settings   -> Phase 2 (Ansible)
Lines 401-450: Firewall basics            -> Phase 0 (Bootstrap)
Lines 451-487: API access + terraform user -> Phase 0 (Bootstrap)
```

**Minimal Bootstrap (Phase 0) should contain only:**
- Enable API access
- Create terraform user with API token
- Basic firewall for API access
- Set management IP (from answer.toml)

### G4: Orange Pi 5 (SBC)

| Item | Status | Action Required |
|------|--------|-----------------|
| `user-data.j2` | Placeholder | Complete implementation |
| `meta-data.j2` | Missing | Create |
| SSH key injection | Missing | Add from secrets |
| Network config | Missing | Add from topology |
| Object module contract | Missing | Add to `obj.orangepi.rk3588.debian.yaml` |
| Generator plugin | Exists stub | Complete implementation |

### G5: LXC Containers

| Item | Status | Action Required |
|------|--------|-----------------|
| Initialization contract | N/A | **No contract needed** (implicit terraform-managed) |
| Object module update | N/A | No change required — absence of contract = terraform-managed |
| Documentation | Not done | Document implicit pattern in object module comments |

**Note**: LXC containers and other Terraform-created resources do NOT need an explicit `initialization_contract`. The absence of a contract means the object is managed entirely by Terraform (day-1 onwards). This simplifies the schema and reduces boilerplate.

### G6: Initialization Manifest Generator

| Item | Status | Action Required |
|------|--------|-----------------|
| Generator plugin | Missing | Create `base.generator.initialization_manifest` |
| Manifest schema | Missing | Define YAML schema |
| Status tracking | Missing | Persist runtime status in `.work/native/bootstrap/INITIALIZATION-STATE.yaml` (not in `generated/`) |

### G7: Initialization Orchestrator

| Item | Status | Action Required |
|------|--------|-----------------|
| `init-node.py` | Missing | Create orchestrator |
| `BootstrapAdapter` ABC (D19) | **Specified** | Implement `adapters/base.py` with preflight/execute/handover lifecycle |
| Device adapters | Missing | Create per-mechanism adapters inheriting from `BootstrapAdapter` |
| Handover verification | Missing | Implement check suite |
| CLI interface | Missing | Design command interface |
| Structured logging (D20) | **Specified** | Implement dual-output logging (console + JSONL audit trail) |
| Inter-node dependency handling | **Not needed** | Pipeline stages provide natural ordering (D6); Terraform handles provider deps |

### G8: Existing Device Migration (D17)

| Item | Status | Action Required |
|------|--------|-----------------|
| `--import` flag | Missing | Implement in `init-node.py` |
| Handover-only verification | Missing | Run checks without bootstrap execution |
| State with `imported: true` | Missing | Track import vs bootstrap origin |
| Mixed fleet support | Missing | Document workflow for existing + new devices |

**Scenario**: Devices already operational (bootstrapped months ago) need to be brought into the initialization state tracking without re-bootstrapping. The `--import` flag runs handover checks only and creates state with `imported: true`.

### G9: Contract Drift Detection (D18)

| Item | Status | Action Required |
|------|--------|-----------------|
| `contract_hash` field | Missing | Add to state schema (SHA256 of contract YAML) |
| Hash computation | Missing | Implement in `init-node.py` |
| Drift warning | Missing | Warn when manifest hash != state hash |
| `--acknowledge-drift` flag | Missing | Update hash without re-bootstrap |
| `--force` for re-bootstrap | Exists (planned) | Clarify drift handling |

**Scenario**: When an `initialization_contract` changes (new requirement, different handover timeout), the system must detect this and warn the operator. Options: `--force` to re-bootstrap, or `--acknowledge-drift` to accept changes without re-bootstrap.

---

## Risk Summary

| Risk ID | Description | Severity | Mitigation |
|---------|-------------|----------|------------|
| R1 | Large Proxmox script decomposition may break existing workflow | High | Preserve original, create new minimal version |
| R2 | Hardware testing required for full validation | Medium | Mock adapters for CI, manual hardware tests |
| R3 | Secret injection patterns differ across devices | Medium | Standardize on ADR 0072 SOPS model |
| R4 | Orange Pi cloud-init untested | Low | Test on actual hardware before release |
| R5 | LXC helper-scripts are external dependency | Low | Document as prerequisite, not responsibility |
| R6 | Destructive Proxmox install without validation | High | Mandatory pre-validation (D16) with `--confirm-destructive` |
| R7 | Existing devices not in state tracking | Medium | `--import` flag for existing operational devices (D17) |
| R8 | Contract changes go unnoticed after bootstrap | Medium | Contract drift detection with `contract_hash` (D18) |
| R9 | Operator confusion about implicit terraform-managed | Low | Document pattern clearly in operator guide |

---

## Dependencies

### Internal Dependencies

- ADR 0057: MikroTik contract (reference implementation)
- ADR 0072: Secrets management (SOPS/age)
- ADR 0074: Generator architecture
- ADR 0080: Plugin data bus

### External Dependencies

- `netinstall-cli` for MikroTik
- Proxmox VE ISO with answer file support
- cloud-init for SBCs
- Terraform providers for each platform

---

## Additional Analysis Required

To finalize ADR quality and reduce implementation risk, complete these analyses:

1. **Plugin boundary analysis (C/O/I levels)** — ✅ COMPLETED
   See: `PLUGIN-BOUNDARY-ANALYSIS.md`
   All proposed plugins respect the 4-level boundary model. No violations found.

2. **Failure-mode and recovery analysis (FMEA)** — ✅ COMPLETED + UPDATED
   See: `FMEA.md`
   All 5 mechanisms analyzed with failure points, retry strategies, and recovery procedures.
   **Update**: Added mandatory Proxmox pre-validation with E9710-E9715 error codes per D16.

3. **Secrets and dataflow analysis** — ✅ COMPLETED
   See: `SECRETS-DATAFLOW.md`
   Full secret lifecycle traced from SOPS source to deploy execution. Assemble-stage plugin defined.

4. **State model and concurrency analysis** — ✅ COMPLETED + UPDATED
   See: `STATE-MODEL.md`
   Formal state machine, file locking, atomic writes, and edge cases documented.
   **Updates**:
   - Added `contract_hash` for drift detection (D18)
   - Added `imported` field for existing device migration (D17)
   - Added safety guard for `verified → pending` transition with `--confirm-reset`
   - Added `--import` state transition for operational devices

5. **Test and evidence matrix** — ✅ COMPLETED + UPDATED
   See: `TEST-MATRIX.md`
   Now 82 test cases defined across 8 categories. CI mock vs hardware E2E gates specified.
   **Updates**:
   - Added T-O13 through T-O18 for orchestrator tests (stale artifacts, import, reset, drift)
   - Added T-P01 through T-P08 for Proxmox pre-validation tests
   - Added T-S15 for implicit terraform-managed validation

6. **Runbook/task cutover impact analysis** — ✅ COMPLETED + UPDATED
   See: `CUTOVER-IMPACT.md`
   Taskfile changes, directory structure, documentation, CI, and operator workflow migration mapped.
   **Update**: Added existing device migration section (D17) with import vs bootstrap decision tree.

---

## Critical Review Improvements (2026-03-30)

Based on critical review of ADR 0083, the following improvements were incorporated:

| Issue | Resolution | Updated Files |
|-------|------------|---------------|
| `terraform_managed` mechanism redundant | Made `initialization_contract` OPTIONAL; no contract = implicit terraform-managed | ADR 0083, GAP-ANALYSIS.md |
| Proxmox pre-validation missing | Added D16 with mandatory validation and E9710-E9715 error codes | ADR 0083, FMEA.md, TEST-MATRIX.md |
| `verified → pending` needs safety guard | Added `--confirm-reset` flag and Terraform state warning | ADR 0083, STATE-MODEL.md |
| Existing device migration path missing | Added D17 with `--import` flag for operational devices | ADR 0083, STATE-MODEL.md, CUTOVER-IMPACT.md |
| No contract drift detection | Added D18 with `contract_hash` and `--acknowledge-drift` | ADR 0083, STATE-MODEL.md, TEST-MATRIX.md |
| T-O13 missing for stale artifacts | Added T-O13 through T-O18 for orchestrator tests | TEST-MATRIX.md |
| Proxmox day-1 audit task missing | Added task 3.0 for day-1 leakage audit | IMPLEMENTATION-PLAN.md |

---

## Next Steps

1. ~~Create `IMPLEMENTATION-PLAN.md` with detailed phases~~ — ✅ Done
2. ~~Create `CUTOVER-CHECKLIST.md` for migration gates~~ — ✅ Done
3. ~~Critical review and improvements~~ — ✅ Done (see table above)
4. Begin Phase 1: Schema and contract definition (ADR 0080 Waves A-H completed ✅)
