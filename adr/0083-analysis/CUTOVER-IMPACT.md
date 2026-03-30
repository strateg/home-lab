# ADR 0083: Cutover Impact Analysis

## Purpose

Map required changes across Taskfiles, deploy guides, operator runbooks, and CI configuration to avoid broken transition paths during ADR 0083 adoption.

---

## Impacted Artifacts

### 1. Taskfile Changes

#### Current State

```
taskfiles/
  Taskfile.yml          # Root orchestration
  (various domain taskfiles)
```

#### Required Changes

| File | Change | Phase | Priority |
|------|--------|-------|----------|
| `Taskfile.yml` | Add `includes: deploy` for new deploy taskfile | Phase 4 | High |
| `taskfiles/deploy.yaml` | **NEW** - Deploy domain tasks | Phase 4 | High |
| `taskfiles/mikrotik.yaml` | Update paths from `scripts/orchestration/` to `scripts/orchestration/deploy/` | Phase 4 | High |

#### New `taskfiles/deploy.yaml`

```yaml
version: "3"

tasks:
  init:node:
    desc: Initialize a specific node (day-0 bootstrap)
    cmds:
      - python scripts/orchestration/deploy/init-node.py --node {{.NODE}}
    requires:
      vars: [NODE]

  init:all-pending:
    desc: Initialize all pending nodes
    cmds:
      - python scripts/orchestration/deploy/init-node.py --all-pending

  init:verify:
    desc: Verify handover for a specific node
    cmds:
      - python scripts/orchestration/deploy/init-node.py --verify-only --node {{.NODE}}
    requires:
      vars: [NODE]

  init:status:
    desc: Show initialization status of all nodes
    cmds:
      - python scripts/orchestration/deploy/init-node.py --status

  init:force:
    desc: Force re-initialization of a node
    cmds:
      - python scripts/orchestration/deploy/init-node.py --force --node {{.NODE}}
    requires:
      vars: [NODE]

  terraform:plan:
    desc: Run Terraform plan for a domain
    cmds:
      - python scripts/orchestration/deploy/apply-terraform.py --plan --domain {{.DOMAIN}}
    requires:
      vars: [DOMAIN]

  terraform:apply:
    desc: Apply Terraform configuration for a domain
    cmds:
      - python scripts/orchestration/deploy/apply-terraform.py --apply --domain {{.DOMAIN}}
    requires:
      vars: [DOMAIN]

  ansible:run:
    desc: Run Ansible playbook
    cmds:
      - python scripts/orchestration/deploy/run-ansible.py --playbook {{.PLAYBOOK}}
    requires:
      vars: [PLAYBOOK]
```

### 2. Scripts Directory Changes

#### Current State

```
scripts/
  orchestration/
    lane.py              # V5 pipeline orchestrator
  validation/
    (validation scripts)
```

#### Required Changes

| Change | Description | Phase |
|--------|-------------|-------|
| Create `scripts/orchestration/deploy/` | New deploy domain directory | Phase 4 |
| Create `scripts/orchestration/deploy/init-node.py` | Initialization orchestrator | Phase 4 |
| Create `scripts/orchestration/deploy/apply-terraform.py` | Terraform wrapper | Phase 6 |
| Create `scripts/orchestration/deploy/run-ansible.py` | Ansible wrapper | Phase 6 |
| Create `scripts/orchestration/deploy/adapters/` | Device-specific adapters | Phase 4 |

#### New Directory Structure

```
scripts/
  orchestration/
    lane.py              # V5 pipeline (unchanged)
    deploy/
      init-node.py         # NEW: initialization orchestrator
      apply-terraform.py   # NEW: terraform wrapper (Phase 6)
      run-ansible.py       # NEW: ansible wrapper (Phase 6)
      adapters/
        __init__.py
        base.py            # Abstract adapter interface
        netinstall.py      # MikroTik netinstall adapter
        unattended.py      # Proxmox unattended install adapter
        cloud_init.py      # Orange Pi cloud-init adapter
        terraform_managed.py  # LXC/Cloud VM (no-op adapter)
        ansible_bootstrap.py  # Generic Linux adapter
      checks/
        __init__.py
        api_reachable.py
        ssh_reachable.py
        credential_valid.py
        python_installed.py
        terraform_plan.py
  validation/
    (unchanged)
```

### 3. Documentation Changes

| Document | Change | Phase |
|----------|--------|-------|
| `docs/guides/NODE-INITIALIZATION.md` | **NEW** - Full operator guide | Phase 6 |
| `CLAUDE.md` | Add initialization workflow section | Phase 6 |
| `README.md` | Add initialization workflow to quick start | Phase 6 |

#### NODE-INITIALIZATION.md Outline

```markdown
# Node Initialization Guide

## Overview
## Prerequisites
## Quick Start
  ### Initialize MikroTik Router
  ### Initialize Proxmox Hypervisor
  ### Initialize Orange Pi SBC
  ### LXC Containers (Terraform-managed)
## Initialization Workflow
  ### Pipeline: Generate Bootstrap Artifacts
  ### Pipeline: Assemble Secret-Bearing Artifacts
  ### Deploy: Execute Bootstrap
  ### Deploy: Verify Handover
## Troubleshooting
  ### Common Failures and Recovery
  ### State File Management
## Reference
  ### CLI Options
  ### State Machine
  ### Handover Check Types
```

### 4. CLAUDE.md Updates

Add to the Common Workflows section:

```markdown
### 4. Node Initialization (Deploy Domain)

# Generate + assemble bootstrap artifacts
python scripts/orchestration/lane.py build-v5

# Initialize a new device
task deploy:init:node NODE=rtr-mikrotik-chateau

# Check initialization status
task deploy:init:status

# Verify handover after bootstrap
task deploy:init:verify NODE=rtr-mikrotik-chateau

# Apply Terraform configuration
task deploy:terraform:apply DOMAIN=mikrotik

# Run Ansible post-configuration
task deploy:ansible:run PLAYBOOK=mikrotik-firewall
```

### 5. CI Configuration Changes

| Change | Description | Phase |
|--------|-------------|-------|
| Add schema test job | Validates initialization-contract schema | Phase 1 |
| Add validator test job | Tests E97xx diagnostics | Phase 1 |
| Add generator test job | Tests bootstrap artifact generation | Phase 2 |
| Add assembler test job | Tests secret injection (mock SOPS) | Phase 5 |
| Add orchestrator test job | Tests init-node.py with mock adapters | Phase 4 |
| Skip hardware tests in CI | Mark with `@pytest.mark.hardware` | Phase 4 |

### 6. .gitignore Changes

| Entry | Reason | Phase |
|-------|--------|-------|
| `.work/native/bootstrap/` | Secret-bearing artifacts | Phase 5 |
| `INITIALIZATION-STATE.yaml` | Runtime mutable state | Phase 5 |
| `*.lock` | State file locks | Phase 4 |

Verify existing `.gitignore` already covers `.work/` directory.

---

## Operator Workflow Migration

### Before ADR 0083 (Current)

```
1. Manual: Flash MikroTik via WinBox or netinstall GUI
2. Manual: Run proxmox-post-install.sh via SSH
3. Manual: Flash Orange Pi SD card with Balena Etcher
4. Manual: Verify connectivity by ping/SSH
5. Run: python scripts/orchestration/lane.py build-v5
6. Run: cd generated/... && tofu apply
7. Run: ansible-playbook ...
```

### After ADR 0083 (Target)

```
1. Run: python scripts/orchestration/lane.py build-v5      (pipeline)
2. Run: task deploy:init:node NODE=rtr-mikrotik-chateau     (deploy, ONCE)
   -- or: task deploy:init:all-pending                       (deploy, ONCE)
3. Run: task deploy:init:status                              (verify)
4. Run: task deploy:terraform:apply DOMAIN=mikrotik          (deploy, MANY)
5. Run: task deploy:ansible:run PLAYBOOK=mikrotik-firewall   (deploy, MANY)
```

### Transition Period

During migration, both workflows MUST work:

| Workflow | Status | Until |
|----------|--------|-------|
| Manual flash + scripts | Supported | Phase 6 cutover |
| `init-node.py` automated | Available | Phase 4 onwards |
| Mixed (some manual, some automated) | Supported | Phase 6 cutover |

**Rule:** No existing manual workflow is broken until Phase 6 cutover is complete.

---

## Rollback Triggers

If any of these conditions occur during migration, rollback to pre-0083 workflow:

| Trigger | Severity | Action |
|---------|----------|--------|
| `init-node.py` fails for MikroTik hardware test | High | Revert to manual netinstall |
| Generated bootstrap artifacts differ from pre-0083 | High | Regression - revert generator changes |
| Secret leak detected in `generated/` | Critical | Immediate revert + security review |
| State file corruption under concurrent access | Medium | Fix locking, revert if persistent |
| Pipeline performance regression >20% | Low | Profile and optimize, no revert needed |

---

## Migration Timeline

```
Phase 1 (Schema)         ── Can start immediately after ADR 0080 Wave B
Phase 2 (Generators)     ── Parallel with Phase 3, after Phase 1
Phase 3 (Device Support) ── Parallel with Phase 2, after Phase 1
Phase 4 (Orchestration)  ── After Phases 2-3, requires ADR 0080 Wave E
Phase 5 (Assemble)       ── After Phase 4, requires ADR 0080 Wave F
Phase 6 (Documentation)  ── After Phase 5

Total estimated: ~15-20 working days (with parallel phases)
```

---

## Checklist for Each Phase Cutover

### Phase 1 Cutover
- [ ] Schema file created and meta-validated
- [ ] Validator plugin registered in base plugins.yaml
- [ ] All schema tests pass (T-S01..T-S14)
- [ ] All validator tests pass (T-V01..T-V08)

### Phase 2-3 Cutover
- [ ] MikroTik object module has initialization_contract
- [ ] Proxmox object module has initialization_contract
- [ ] Orange Pi object module has initialization_contract
- [ ] LXC object modules have initialization_contract
- [ ] All generator tests pass (T-G01..T-G12)
- [ ] Generated artifacts are regression-safe

### Phase 4 Cutover
- [ ] `scripts/orchestration/deploy/` directory created
- [ ] `init-node.py` passes all orchestrator tests (T-O01..T-O12)
- [ ] Handover checks pass all tests (T-H01..T-H08)
- [ ] Taskfile targets added and documented
- [ ] MikroTik hardware E2E test passes (T-E01)

### Phase 5 Cutover
- [ ] `base.assembler.bootstrap_secrets` plugin implemented
- [ ] All assembler tests pass (T-A01..T-A07)
- [ ] No secret leaks in generated/
- [ ] .gitignore covers .work/native/bootstrap/

### Phase 6 Cutover
- [ ] NODE-INITIALIZATION.md published
- [ ] CLAUDE.md updated
- [ ] Legacy scripts archived with migration notes
- [ ] ADR 0083 status changed to Accepted
- [ ] REGISTER.md updated
