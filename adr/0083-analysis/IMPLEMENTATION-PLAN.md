# ADR 0083: Implementation Plan

## Overview

This plan implements the Unified Node Initialization Contract in 6 phases, progressing from schema definition to cutover.

---

## Phase 1: Contract Schema and Validation

**Goal:** Define the initialization contract schema and add validation to v5 pipeline.

### Tasks

| ID | Task | Outputs | Acceptance Criteria |
|----|------|---------|---------------------|
| 1.1 | Create `initialization-contract.schema.json` | `schemas/initialization-contract.schema.json` | Valid JSONSchema 2020-12 |
| 1.2 | Extend object module schema | Updated `object-module.schema.json` | `initialization_contract` field optional |
| 1.3 | Create validator plugin manifest | `plugins.yaml` entry | `base.validator.initialization_contract` |
| 1.4 | Implement validator plugin | `plugins/validators/initialization_contract.py` | Validates contracts against schema |
| 1.5 | Add unit tests | `tests/validators/test_initialization_contract.py` | 100% branch coverage |

### Gate

- [ ] Schema passes JSONSchema meta-validation
- [ ] Validator loads and runs without errors
- [ ] Tests pass

---

## Phase 2: MikroTik Full IaC Implementation

**Goal:** Implement complete MikroTik IaC pipeline per `MIKROTIK-IAC-PATTERN.md`.

### Tasks

| ID | Task | Outputs | Acceptance Criteria |
|----|------|---------|---------------------|
| 2.1 | Add `initialization_contract` to MikroTik object | `topology/object-modules/mikrotik/obj.mikrotik.chateau_lte7_ax.yaml` | Contract valid per schema |
| 2.2 | Update bootstrap generator to read contract | `topology/object-modules/mikrotik/plugins/generators/bootstrap_mikrotik_generator.py` | Reads contract from compiled topology |
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
| 3.1 | Create Proxmox object module | `topology/object-modules/proxmox/obj.proxmox.ve.yaml` | With initialization_contract |
| 3.2 | Create `answer.toml.j2` template | `topology/object-modules/proxmox/templates/bootstrap/answer.toml.j2` | Topology-driven values |
| 3.3 | Create `post-install-minimal.sh.j2` | `topology/object-modules/proxmox/templates/bootstrap/post-install-minimal.sh.j2` | Only API access, terraform user |
| 3.4 | Update bootstrap generator plugin | `topology/object-modules/proxmox/plugins/generators/bootstrap_proxmox_generator.py` | Produces answer.toml + minimal script |
| 3.5 | Document day-1 migration | `docs/guides/PROXMOX-DAY1-MIGRATION.md` | Storage, packages, optimizations |
| 3.6 | Add Terraform source templates for day-1 | `topology/object-modules/proxmox/templates/terraform/` | Storage pools, bridges generated from source templates |
| 3.7 | Add Ansible source templates for day-2 | `topology/object-modules/proxmox/templates/ansible/` | KSM, packages, platform settings generated from source templates |

### Gate

- [ ] Minimal bootstrap script < 50 lines
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
| 4.4 | Complete bootstrap generator | `plugins/generators/bootstrap_orangepi.py` | Produces cloud-init files |
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

### Tasks

| ID | Task | Outputs | Acceptance Criteria |
|----|------|---------|---------------------|
| 5.1 | Create manifest generator plugin | `topology-tools/plugins/generators/initialization_manifest_generator.py` | Produces read-only `generated/<project>/bootstrap/INITIALIZATION-MANIFEST.yaml` |
| 5.2 | Define manifest and runtime-state schemas | `schemas/initialization-manifest.schema.json`, `schemas/initialization-state.schema.json` | Static manifest separated from mutable runtime state |
| 5.3 | Create `init-node.py` orchestrator | `scripts/orchestration/init-node.py` | CLI with --node, --all-pending, --verify-only and state file updates in `.work/native/` |
| 5.4 | Implement netinstall adapter | `scripts/orchestration/adapters/netinstall.py` | MikroTik bootstrap execution |
| 5.5 | Implement unattended adapter | `scripts/orchestration/adapters/unattended.py` | Proxmox ISO preparation hints |
| 5.6 | Implement cloud-init adapter | `scripts/orchestration/adapters/cloud_init.py` | SD card preparation hints |
| 5.7 | Implement handover verification | `scripts/orchestration/verify.py` | All check types |
| 5.8 | Add Taskfile targets | `taskfiles/init.yaml` | `task init:node`, `task init:verify` |
| 5.9 | Integration tests with mocks | `tests/orchestration/test_init_node.py` | All adapters tested |

### Gate

- [ ] Manifest generation integrated in v5 pipeline (read-only output under `generated/`)
- [ ] Runtime state written only under `.work/native/bootstrap/`
- [ ] `init-node.py --node rtr-mikrotik-chateau` works (mock)
- [ ] `init-node.py --verify-only` checks all handover conditions
- [ ] Taskfile targets documented

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
| Phase 1: Schema | 2-3 days | None |
| Phase 2: MikroTik | 1-2 days | Phase 1 |
| Phase 3: Proxmox | 3-5 days | Phase 1 |
| Phase 4: Orange Pi/LXC | 2-3 days | Phase 1 |
| Phase 5: Orchestration | 4-5 days | Phases 2-4 |
| Phase 6: Documentation | 2-3 days | Phase 5 |

**Total:** ~15-20 working days

---

## Parallel Work Opportunities

- Phase 2 (MikroTik) and Phase 3 (Proxmox) can run in parallel after Phase 1
- Phase 4 (Orange Pi) can start during Phase 3
- Documentation can start during Phase 5

---

## Success Metrics

1. **Contract coverage:** 100% of compute/router objects have `initialization_contract`
2. **Bootstrap boundary:** All day-0 scripts < 100 lines
3. **Manifest/state accuracy:** INITIALIZATION-MANIFEST.yaml reflects all nodes and runtime statuses are tracked in `.work/native/bootstrap/INITIALIZATION-STATE.yaml`
4. **Handover verification:** All nodes pass automated handover checks
5. **Test coverage:** > 80% for new code
