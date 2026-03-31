# ADR 0083: Implementation Plan

## Overview

This plan implements the Unified Node Initialization Contract in 8 phases (0-6 + 5a), progressing from environment setup through schema definition to cutover.

**Status note:** This plan is no longer fully deferred: scaffold work for Phase 5.3 started (`init_node` CLI/state baseline), Phase 0 environment precheck is wired into `init-node`, non-`--plan-only` mode returns explicit `not-implemented` until adapters are integrated, unknown node targets fail fast (`node-not-found`), Phase 1 schema/validator baseline is in place, Phase 2.1/2.2 baseline is started (MikroTik contract + contract-aware bootstrap projection routing), and Phase 3.1 baseline is started (Proxmox contract declaration).

### Dependencies

| ADR 0083 Phase | Dependency | Status |
|----------------|------------|--------|
| Phase 0 | ADR 0084 (Execution Plane) | ✅ ADR created |
| Phase 1-6 | ADR 0080 Wave B-H | ✅ All waves completed |

---

## Phase 0: Execution Environment (ADR 0084 Integration)

**Goal:** Implement deploy plane environment check per ADR 0084.

**Rationale:** Deploy tooling (`init-node.py`, Terraform, Ansible) requires Linux. Windows operators must use WSL. This phase ensures fast-fail with clear instructions.

### Tasks

| ID | Task | Outputs | Acceptance Criteria |
|----|------|---------|---------------------|
| 0.1 | Create environment module | `scripts/orchestration/deploy/environment.py` | `check_deploy_environment()` implemented ✅ |
| 0.2 | Add unit tests | `tests/orchestration/test_environment.py` | T-E01..T-E05 pass ✅ |
| 0.3 | Create operator setup guide | `docs/guides/OPERATOR-ENVIRONMENT-SETUP.md` | WSL setup, tool installation documented ✅ |

### Implementation

```python
# scripts/orchestration/deploy/environment.py

import platform

def check_deploy_environment(...) -> DeployEnvironmentReport:
    host_platform = platform.system()
    runner = get_runner(...)
    tools = check_runner_tools(runner, ["bash"])
    issues = [f"Required tool '{tool}' is not available" for tool, ok in tools.items() if not ok]
    return DeployEnvironmentReport(
        ready=len(issues) == 0,
        platform=host_platform,
        runner=runner.name,
        issues=issues,
        tools=tools,
    )
```

### Gate

- [x] Environment check implemented (~50 lines)
- [x] Windows execution fails with WSL instructions
- [x] Unit tests pass (T-E01..T-E05)
- [x] OPERATOR-ENVIRONMENT-SETUP.md created

---

## Phase 1: Contract Schema and Validation

**Goal:** Define the initialization contract schema and add validation to v5 pipeline.

### Tasks

| ID | Task | Outputs | Acceptance Criteria |
|----|------|---------|---------------------|
| 1.1 | Create `initialization-contract.schema.json` | `schemas/initialization-contract.schema.json` | Valid JSONSchema 2020-12 ✅ |
| 1.2 | Extend object module schema | Updated `object-module.schema.json` | `initialization_contract` field optional (pending: no standalone object-module schema file in current repo layout) |
| 1.3 | Create validator plugin manifest | `plugins.yaml` entry | `base.validator.initialization_contract` ✅ |
| 1.4 | Implement validator plugin | `topology-tools/plugins/validators/initialization_contract_validator.py` | Validates contracts against schema ✅ |
| 1.5 | Add tests | `tests/test_initialization_contract_schema.py`, `tests/plugin_integration/test_initialization_contract_validator.py` | schema + plugin integration tests pass ✅ |

### Gate

- [x] Schema passes JSONSchema meta-validation
- [x] Validator loads and runs without errors
- [x] Tests pass

---

## Phase 2: MikroTik Full IaC Implementation

**Goal:** Implement complete MikroTik IaC pipeline per `MIKROTIK-IAC-PATTERN.md`.

### Tasks

| ID | Task | Outputs | Acceptance Criteria |
|----|------|---------|---------------------|
| 2.1 | Add `initialization_contract` to MikroTik object | `topology/object-modules/mikrotik/obj.mikrotik.chateau_lte7_ax.yaml` | Contract valid per schema ✅ |
| 2.2 | Update bootstrap generator to read contract | `topology/object-modules/_shared/plugins/bootstrap_projections.py` | Reads contract from compiled topology ✅ |
| 2.3 | Create minimal bootstrap template | `topology/object-modules/mikrotik/templates/bootstrap/init-terraform.rsc.j2` | <50 lines, day-0 only |
| 2.4 | Expand Terraform source templates for day-1 | `topology/object-modules/mikrotik/templates/terraform/` | Bridge, VLAN, IP, WG resources generated from source templates |
| 2.5 | Align projection logic with ownership split | `topology/object-modules/mikrotik/plugins/projections.py` | Projection separates Terraform-owned and Ansible-owned objects |
| 2.6 | Add Ansible source templates for post-handover ops | `topology/object-modules/mikrotik/templates/ansible/` | Service hardening and operational tasks generated from templates |
| 2.7 | Update plugin manifest mappings | `topology/object-modules/mikrotik/plugins.yaml` | Correct template->artifact mappings for Terraform/Ansible/bootstrap |
| 2.8 | Add generator integration tests | `tests/plugin_integration/test_bootstrap_generators.py` | E2E generation passes without editing `generated/` sources |
| 2.9 | Add ownership regression tests | `tests/plugin_integration/test_terraform_mikrotik_generator.py` | No Terraform/Ansible overlap for same objects |
| 2.10 | Add Taskfile targets | `taskfiles/mikrotik.yaml` | `task mikrotik:*` commands |
| 2.11 | Validate generation lane | `task validate:v5` + plugin integration suite | Generated artifacts are deterministic and policy-compliant |

### Gate

- [ ] MikroTik contract validates
- [ ] Bootstrap script <50 lines
- [ ] OpenTofu plan succeeds (mock)
- [ ] Ansible playbooks lint clean
- [ ] Object ownership matrix enforced (no overlap)

---

## Phase 3: Proxmox Bootstrap Decomposition

**Goal:** Create minimal Proxmox bootstrap and move day-1 config to Terraform/Ansible.

### Tasks

| ID | Task | Outputs | Acceptance Criteria |
|----|------|---------|---------------------|
| 3.0 | **Audit existing Proxmox generator for day-1 leakage** | Audit report | Identify all day-1 config in current post_install_scripts |
| 3.1 | Create Proxmox object module | `topology/object-modules/proxmox/obj.proxmox.ve.yaml` | With initialization_contract ✅ |
| 3.2 | Create `answer.toml.j2` template | `topology/object-modules/proxmox/templates/bootstrap/answer.toml.j2` | Topology-driven values |
| 3.3 | Create `post-install-minimal.sh.j2` | `topology/object-modules/proxmox/templates/bootstrap/post-install-minimal.sh.j2` | Only API access, terraform user |
| 3.4 | Update bootstrap generator plugin | `topology/object-modules/proxmox/plugins/generators/bootstrap_proxmox_generator.py` | Produces answer.toml + minimal script |
| 3.5 | **Implement Proxmox pre-validation (D16)** | `scripts/orchestration/deploy/validators/proxmox.py` | E9710-E9715 error codes |
| 3.6 | Document day-1 migration | `docs/guides/PROXMOX-DAY1-MIGRATION.md` | Storage, packages, optimizations |
| 3.7 | Add Terraform source templates for day-1 | `topology/object-modules/proxmox/templates/terraform/` | Storage pools, bridges generated from source templates |
| 3.8 | Add Ansible source templates for day-2 | `topology/object-modules/proxmox/templates/ansible/` | KSM, packages, platform settings generated from source templates |

### Gate

- [ ] Day-1 leakage audit completed (task 3.0)
- [ ] Minimal bootstrap script < 50 lines
- [ ] Pre-validation catches malformed answer.toml (E9710-E9715)
- [ ] `--confirm-destructive` required for unattended_install mechanism
- [ ] API access works after bootstrap
- [ ] Terraform can connect and plan
- [ ] Original script archived with migration notes

---

## Phase 4: Orange Pi and Other Devices

**Goal:** Complete cloud-init bootstrap for SBCs and document terraform_managed pattern.

### Tasks

| ID | Task | Outputs | Acceptance Criteria |
|----|------|---------|---------------------|
| 4.1 | Complete Orange Pi object module | `topology/object-modules/orangepi/obj.orangepi.rk3588.debian.yaml` | With initialization_contract |
| 4.2 | Implement `user-data.j2` | `topology/object-modules/orangepi/templates/bootstrap/user-data.j2` | SSH keys, network, python |
| 4.3 | Implement `meta-data.j2` | `topology/object-modules/orangepi/templates/bootstrap/meta-data.j2` | Instance ID, hostname |
| 4.4 | Complete bootstrap generator | `topology/object-modules/orangepi/plugins/generators/bootstrap_orangepi_generator.py` | Produces cloud-init files |
| 4.5 | Add LXC contract pattern | `topology/object-modules/lxc/*.yaml` | mechanism: terraform_managed |
| 4.6 | Add Cloud VM contract pattern | Documentation | Reference for future cloud instances |

### Gate

- [ ] cloud-init files validate
- [ ] Orange Pi boots with generated user-data (manual test)
- [ ] SSH access works after first boot
- [ ] LXC instances document terraform_managed pattern

---

## Phase 5: Initialization Manifest and Orchestration

**Goal:** Create unified manifest generator and initialization orchestrator.

**Progress snapshot (2026-03-31):**
- `5.3` scaffold started: `init_node` CLI/status/plan + deploy-state baseline.
- `5.4` scaffold started: adapter ABC/dataclasses + factory placeholder.
- `5.10` scaffold started: legal state-transition helpers in `state.py`.

### Tasks

| ID | Task | Outputs | Acceptance Criteria |
|----|------|---------|---------------------|
| 5.1 | Create manifest generator plugin | `topology-tools/plugins/generators/initialization_manifest_generator.py` | Produces read-only `generated/<project>/bootstrap/INITIALIZATION-MANIFEST.yaml` |
| 5.2 | Define manifest and runtime-state schemas | `schemas/initialization-manifest.schema.json`, `schemas/initialization-state.schema.json` | Static manifest separated from mutable runtime state |
| 5.3 | Create `init-node.py` orchestrator | `scripts/orchestration/deploy/init-node.py` | CLI with --node, --all-pending, --verify-only, --force, --status |
| 5.4 | Implement `BootstrapAdapter` ABC and result dataclasses (D19) | `scripts/orchestration/deploy/adapters/base.py` | ABC with preflight/execute/handover/cleanup lifecycle; AdapterStatus, PreflightCheck, BootstrapResult, HandoverCheckResult dataclasses |
| 5.5 | Implement netinstall adapter | `scripts/orchestration/deploy/adapters/netinstall.py` | MikroTik bootstrap execution |
| 5.6 | Implement unattended adapter | `scripts/orchestration/deploy/adapters/unattended.py` | Proxmox ISO preparation hints |
| 5.7 | Implement cloud-init adapter | `scripts/orchestration/deploy/adapters/cloud_init.py` | SD card preparation hints |
| 5.8 | Implement ansible_bootstrap adapter | `scripts/orchestration/deploy/adapters/ansible_bootstrap.py` | Generic Linux bootstrap |
| 5.9 | Implement handover verification | `scripts/orchestration/deploy/checks/` | All check types with retry/backoff |
| 5.10 | Implement state machine | `scripts/orchestration/deploy/state.py` | Atomic writes, file locking, legal transitions |
| 5.11 | Implement structured logging (D20) | `scripts/orchestration/deploy/logging.py` | Dual output (console + JSONL), audit trail for destructive ops, E97xx codes |
| 5.12 | Add Taskfile targets | `taskfiles/deploy.yaml` | `task deploy:init:*` commands |
| 5.13 | Integration tests with mocks | `tests/orchestration/test_init_node.py` | All adapters and state transitions tested |

### Gate

- [ ] Manifest generation integrated in v5 pipeline (read-only output under `generated/`)
- [ ] Runtime state written only under `.work/deploy-state/<project>/`
- [ ] `BootstrapAdapter` ABC enforced for all 4 adapters (D19)
- [ ] `init-node.py --node rtr-mikrotik-chateau` works (mock)
- [ ] `init-node.py --verify-only` checks all handover conditions
- [ ] `init-node.py --status` displays node summary
- [ ] State machine transitions are correct (T-O07, T-O08)
- [ ] Structured logging produces both console output and JSONL audit trail (D20)
- [ ] Destructive operations logged with pre-validation and confirmation status
- [ ] Taskfile targets documented

---

## Phase 5a: Assemble Stage Integration

**Goal:** Implement secret injection via assemble stage plugin.

**Dependency:** Requires ADR 0080 Wave F (Assemble Pluginization).

### Tasks

| ID | Task | Outputs | Acceptance Criteria |
|----|------|---------|---------------------|
| 5a.1 | Implement `base.assembler.bootstrap_secrets` | `topology-tools/plugins/assemblers/bootstrap_secrets_assembler.py` | Renders secrets into `.work/deploy/bundles/<bundle_id>/artifacts/` |
| 5a.2 | Add secret-leak scanner | assemble.verify phase check | Detects secrets in `generated/` |
| 5a.3 | Add assembler tests | `tests/plugin_integration/test_bootstrap_secrets_assembler.py` | T-A01..T-A07 pass |
| 5a.4 | Verify .gitignore coverage | `.gitignore` | `.work/deploy/` ignored |

### Gate

- [ ] Assembled artifacts contain resolved secrets
- [ ] No secrets in `generated/` (leak scanner passes)
- [ ] `.work/deploy/` in .gitignore
- [ ] SOPS decryption failure produces clear E97xx error

---

## Phase 6: Documentation and Cutover

**Goal:** Complete documentation and migrate operators to new workflow.

### Tasks

| ID | Task | Outputs | Acceptance Criteria |
|----|------|---------|---------------------|
| 6.1 | Create operator guide | `docs/guides/NODE-INITIALIZATION.md` | All device types covered |
| 6.2 | Update CLAUDE.md | Updated CLAUDE.md | Initialization workflow documented |
| 6.3 | Archive legacy scripts | `archive/migrated-and-archived/` | With migration notes |
| 6.4 | Update ADR 0083 status | ADR file | Status: Accepted |
| 6.5 | Hardware E2E test | Test report | At least MikroTik validated |

### Gate

- [ ] Documentation reviewed
- [ ] At least one device type validated on real hardware
- [ ] Legacy scripts archived with notes
- [ ] CLAUDE.md updated

---

## Timeline Summary

| Phase | Duration | Dependencies |
|-------|----------|--------------|
| Phase 0: Environment | 1 day | ADR 0084 |
| Phase 1: Schema | 2-3 days | Phase 0 |
| Phase 2: MikroTik | 1-2 days | Phase 1 |
| Phase 3: Proxmox | 3-5 days | Phase 1 |
| Phase 4: Orange Pi/LXC | 2-3 days | Phase 1 |
| Phase 5: Orchestration | 4-5 days | Phases 2-4 |
| Phase 5a: Assemble | 2-3 days | Phase 5 |
| Phase 6: Documentation | 2-3 days | Phase 5a |

**Total:** ~18-25 working days

---

## Parallel Work Opportunities

- Phase 2 (MikroTik) and Phase 3 (Proxmox) can run in parallel after Phase 1
- Phase 4 (Orange Pi) can start during Phase 3
- Phase 5a (Assemble) is blocked on ADR 0080 Wave F but can be prototyped earlier
- Documentation can start during Phase 5

---

## Success Metrics

1. **Contract coverage:** 100% of compute/router objects have `initialization_contract`
2. **Bootstrap boundary:** All day-0 scripts < 100 lines
3. **Manifest/state accuracy:** INITIALIZATION-MANIFEST.yaml reflects all nodes and runtime statuses are tracked in `.work/deploy-state/<project>/nodes/INITIALIZATION-STATE.yaml`
4. **Handover verification:** All nodes pass automated handover checks
5. **Test coverage:** > 80% for new code (74 test cases defined in TEST-MATRIX.md)
6. **Secret isolation:** Zero secrets in `generated/` (assemble.verify enforced)
7. **Plugin boundaries:** All plugins pass boundary analysis (PLUGIN-BOUNDARY-ANALYSIS.md)
