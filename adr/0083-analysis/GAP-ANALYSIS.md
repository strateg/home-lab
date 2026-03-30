# ADR 0083: Gap Analysis

## Executive Summary

This document analyzes the gap between the current fragmented node initialization approach and the target unified initialization contract defined in ADR 0083.

---

## AS-IS State

### Device Initialization Inventory

| Device | Location | Lines | Day-0/Day-1 Mixed | Topology Integration | Handover Verification |
|--------|----------|-------|-------------------|---------------------|----------------------|
| MikroTik | `topology-tools/templates/bootstrap/mikrotik/` | ~100 | No (clean) | Yes | Manual |
| Proxmox | `archive/.../proxmox-post-install.sh` | 487 | **Yes** | No | None |
| Orange Pi | `topology/object-modules/orangepi/templates/` | ~20 | N/A (placeholder) | Partial | None |
| LXC | `archive/.../install-lxc-containers.sh` | ~200 | **Yes** | No | None |

### Current Bootstrap Artifacts

```
generated/home-lab/bootstrap/
  rtr-mikrotik-chateau/
    init-terraform.rsc           # Generated from topology
    terraform.tfvars.example     # Generated from topology

topology-tools/templates/bootstrap/
  mikrotik/
    init-terraform-minimal.rsc.j2
    backup-restore-overrides.rsc.j2
    exported-config-safe.rsc.j2
  proxmox/
    answer.toml.example.j2       # Exists
    script.sh.j2                 # Exists (post-install stub)

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

Every compute/router object module declares `initialization_contract`:

```yaml
initialization_contract:
  version: "1.0"
  mechanism: netinstall | unattended_install | cloud_init | terraform_managed
  requirements: [...]
  bootstrap:
    template: templates/bootstrap/...
    outputs: [...]
  handover:
    provider: <terraform-provider>
    checks: [...]
```

### Target Artifact Structure

```
generated/home-lab/bootstrap/
  INITIALIZATION-MANIFEST.yaml    # NEW: unified registry
  rtr-mikrotik-chateau/
    init-terraform.rsc
    terraform.tfvars.example
  hv-proxmox-xps/                 # NEW
    answer.toml
    post-install-minimal.sh
  sbc-orangepi5/                  # NEW
    user-data
    meta-data
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
| Initialization contract | N/A | Mark as `terraform_managed` |
| Object module update | Not done | Add contract with mechanism: terraform_managed |

### G6: Initialization Manifest Generator

| Item | Status | Action Required |
|------|--------|-----------------|
| Generator plugin | Missing | Create `base.generator.initialization_manifest` |
| Manifest schema | Missing | Define YAML schema |
| Status tracking | Missing | Design status persistence |

### G7: Initialization Orchestrator

| Item | Status | Action Required |
|------|--------|-----------------|
| `init-node.py` | Missing | Create orchestrator |
| Device adapters | Missing | Create per-mechanism adapters |
| Handover verification | Missing | Implement check suite |
| CLI interface | Missing | Design command interface |

---

## Risk Summary

| Risk ID | Description | Severity | Mitigation |
|---------|-------------|----------|------------|
| R1 | Large Proxmox script decomposition may break existing workflow | High | Preserve original, create new minimal version |
| R2 | Hardware testing required for full validation | Medium | Mock adapters for CI, manual hardware tests |
| R3 | Secret injection patterns differ across devices | Medium | Standardize on ADR 0072 SOPS model |
| R4 | Orange Pi cloud-init untested | Low | Test on actual hardware before release |
| R5 | LXC helper-scripts are external dependency | Low | Document as prerequisite, not responsibility |

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

## Next Steps

1. Create `IMPLEMENTATION-PLAN.md` with detailed phases
2. Create `CUTOVER-CHECKLIST.md` for migration gates
3. Begin Phase 1: Schema and contract definition
