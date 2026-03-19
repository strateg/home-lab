# V5 Production Readiness Plan

**Created:** 2026-03-15  
**Revised:** 2026-03-15  
**Goal:** Enable real home network modeling and deployment through v5 lane  
**Current State:** plugin-first compiler is operational, but v5 still lacks deployable Terraform/Ansible/bootstrap artifacts

---

## Executive Summary

v5 architecture is model-complete with:
- plugin microkernel runtime in production path
- compile -> validate -> generate stage wiring
- contract validators and diagnostics in place

**Blocking gap:** deployment generators are missing from v5.

This revised plan adds:
- a mandatory baseline stabilization phase before generator work
- explicit artifact output ownership and path contract
- projection layer between compiled model and templates
- parity gates in each implementation phase (not only at the end)
- realistic migration scope for template and tool parity

---

## Planning Principles (Normative)

1. **Baseline first:** do not start generator implementation while `validate-v5` is red.
2. **Projection-first generation:** generator templates must consume stable projection views, not raw topology internals.
3. **Single artifact contract:** output roots and ownership must be fixed before first non-trivial generator lands.
4. **Continuous parity:** every generator phase includes parity and syntax validation gates.
5. **Secret-safe by default:** committed artifacts remain examples/placeholders only.

---

## Phase 0: Baseline Stabilization (New)

**Duration estimate:** 2-3 days  
**Prerequisite:** None

### 0.1 Data Consistency Fixes

- [x] Resolve canonical instance reference drift in v5 shards (for example `target_ref` aliases vs canonical instance IDs).
- [x] Ensure layer-contract validation and compile validation both pass on the same source set.
- [x] Remove stale references to legacy migration-only instance identifiers where runtime expects canonical IDs.
- [x] Complete baseline local wired network modeling for active LAN devices with explicit endpoint ports and linked L1/L2 instances.

### 0.2 Runtime/Output Contract Freeze

- [x] Define artifact target roots for v5 generators (`v5-generated/...`) and keep `v5-build/...` for compiler artifacts/diagnostics.
- [x] Add an explicit generator output root config contract to plugin context.
- [x] Keep backward-compatible CLI behavior while introducing explicit generator artifact root wiring.

### 0.3 Baseline Gate

- [x] Required green commands:
  - `make validate-v5`
  - `python v5/topology-tools/compile-topology.py --topology v5/topology/topology.yaml --strict-model-lock`
- [x] Capture baseline diagnostics snapshot in `v5-build/diagnostics/`.

### Phase 0 Definition of Done

- [x] `validate-v5` is green.
- [x] compile diagnostics have zero errors in strict mode.
- [ ] output ownership contract is documented and approved.

---

## Phase 1: Generator SDK and Output Contract

**Duration estimate:** 1 week  
**Prerequisite:** Phase 0

### 1.1 Generator Base Infrastructure

- [x] Create `v5/topology-tools/plugins/generators/base_generator.py`:
  - shared Jinja2 environment/bootstrap
  - deterministic collection ordering helpers
  - atomic file write helper (tmp + rename)
  - standardized generated-file manifest output

- [x] Add generator plugin contract conventions to `v5/topology-tools/plugins/plugins.yaml`:
  - stage: `generate`
  - order: after `effective_json`/`effective_yaml`
  - input: `ctx.compiled_json` (authoritative), not disk file reads

- [x] Add tests:
  - `v5/tests/plugin_integration/test_generator_base.py`
  - deterministic output order test
  - atomic write behavior test

### 1.2 Template Migration Inventory (Corrected Scope)

- [x] Inventory v4 templates for migration:
  - `terraform/proxmox`: `provider`, `versions`, `bridges`, `vms`, `lxc`, `variables`, `outputs`, `terraform.tfvars.example`
  - `terraform/mikrotik`: `provider`, `interfaces`, `firewall`, `dhcp`, `dns`, `addresses`, `qos`, `vpn`, `containers`, `variables`, `outputs`
  - `ansible`: `hosts`, `group_vars_all`, `host_vars`
  - `bootstrap/*`: proxmox, mikrotik, orangepi5

- [x] Create v5 template layout:
  - `v5/topology-tools/templates/terraform/proxmox/`
  - `v5/topology-tools/templates/terraform/mikrotik/`
  - `v5/topology-tools/templates/ansible/`
  - `v5/topology-tools/templates/bootstrap/`

### Phase 1 Definition of Done

- [x] generator base is used by at least one real generator plugin.
- [x] generator output contract is test-covered.
- [x] template inventory + mapping matrix is documented.

---

## Phase 2: Projection Layer (Compiled Model -> Tool Views)

**Duration estimate:** 4-5 days  
**Prerequisite:** Phase 1

### 2.1 Implement Projections

- [x] Create projection helpers in `v5/topology-tools/plugins/generators/projections.py`:
  - `build_proxmox_projection(compiled_json)`
  - `build_mikrotik_projection(compiled_json)`
  - `build_ansible_projection(compiled_json)`
  - `build_bootstrap_projection(compiled_json)`

- [x] Ensure projections are:
  - deterministic (stable sort keys)
  - schema-checked
  - independent from template-specific naming quirks

### 2.2 Projection Contract Tests

- [ ] Add unit tests with golden snapshots for projection outputs.
- [x] Add negative tests for missing mandatory fields and malformed refs.

### Phase 2 Definition of Done

- [ ] templates can render using projections without reaching into raw compiled internals.
- [ ] projection snapshots are stable between runs.

---

## Phase 3: Terraform Proxmox Generator

**Duration estimate:** 1-1.5 weeks  
**Prerequisite:** Phase 2

### 3.1 Generator Implementation

- [x] Create `v5/topology-tools/plugins/generators/terraform_proxmox_generator.py`.
- [x] Generate:
  - `provider.tf`
  - `versions.tf`
  - `bridges.tf`
  - `vms.tf`
  - `lxc.tf`
  - `variables.tf`
  - `outputs.tf`
  - `terraform.tfvars.example`

### 3.2 Registration and Wiring

- [x] Register plugin in `plugins.yaml` with explicit order/depends_on and output path config.

### 3.3 Parity and Syntax Gates

- [ ] Add `v5/tests/plugin_regression/test_terraform_proxmox_parity.py`.
- [ ] Compare generated files against v4 baseline (with documented intentional diffs).
- [ ] Run `terraform fmt -check` and `terraform validate` in CI for generated Proxmox output.

### Phase 3 Definition of Done

- [x] Proxmox Terraform output is generated in `v5-generated/terraform/proxmox/`.
- [ ] parity gate is green (or only approved diffs remain).

---

## Phase 4: Terraform MikroTik Generator

**Duration estimate:** 1-1.5 weeks  
**Prerequisite:** Phase 2

### 4.1 Generator Implementation

- [x] Create `v5/topology-tools/plugins/generators/terraform_mikrotik_generator.py`.
- [x] Generate:
  - `provider.tf`
  - `interfaces.tf`
  - `firewall.tf`
  - `dhcp.tf`
  - `dns.tf`
  - `addresses.tf`
  - `qos.tf`
  - `vpn.tf`
  - `containers.tf`
  - `variables.tf`
  - `outputs.tf`
  - `terraform.tfvars.example`

### 4.2 Capability-Driven Behavior

- [ ] Drive optional resource generation from effective capabilities and platform traits.
- [ ] Keep device-specific branching in projection layer, not templates.

### 4.3 Parity and Syntax Gates

- [ ] Add `v5/tests/plugin_regression/test_terraform_mikrotik_parity.py`.
- [ ] Run `terraform fmt -check` and `terraform validate` in CI for generated MikroTik output.

### Phase 4 Definition of Done

- [ ] MikroTik Terraform output is generated in `v5-generated/terraform/mikrotik/`.
- [ ] parity gate is green (or only approved diffs remain).

---

## Phase 5: Ansible Inventory Generator and Runtime Assembly

**Duration estimate:** 1 week  
**Prerequisite:** Phase 2

### 5.1 Generator Implementation

- [x] Create `v5/topology-tools/plugins/generators/ansible_inventory_generator.py`.
- [x] Generate:
  - `hosts.yml`
  - `group_vars/all.yml`
  - `host_vars/*.yml`

### 5.2 Runtime Assembly (ADR 0051 Compliance)

- [ ] Implement runtime inventory assembly flow for environment-specific materialization.
- [ ] Keep secrets externalized; committed inventory remains safe placeholders/examples.

### 5.3 Parity and Validation

- [ ] Add `v5/tests/plugin_regression/test_ansible_inventory_parity.py`.
- [ ] Validate generated inventory with `ansible-inventory --list`.

### Phase 5 Definition of Done

- [x] Ansible inventory output is generated in `v5-generated/ansible/inventory/production/`.
- [ ] parity and inventory validation are green.

---

## Phase 6: Bootstrap Generators

**Duration estimate:** 1 week  
**Prerequisite:** Phases 3-5

### 6.1 Proxmox Bootstrap

- [x] Create `v5/topology-tools/plugins/generators/bootstrap_proxmox_generator.py`.
- [x] Generate:
  - `answer.toml.example`
  - post-install scripts package
  - README/run instructions

### 6.2 MikroTik Bootstrap

- [x] Create `v5/topology-tools/plugins/generators/bootstrap_mikrotik_generator.py`.
- [x] Generate:
  - `init-terraform.rsc`
  - `backup-restore-overrides.rsc`
  - `terraform.tfvars.example`

### 6.3 Orange Pi Bootstrap

- [x] Create `v5/topology-tools/plugins/generators/bootstrap_orangepi_generator.py`.
- [x] Generate:
  - cloud-init `user-data.example`
  - `meta-data`
  - README

### Phase 6 Definition of Done

- [x] bootstrap artifacts are generated under `v5-generated/bootstrap/<device-id>/`.
- [x] all committed bootstrap outputs are release-safe (no real secrets).

---

## Phase 7: Hardware Identity Capture and Placeholder Closure

**Duration estimate:** 3-4 days  
**Prerequisite:** Can run in parallel after Phase 3 starts

### 7.1 Discovery Utility

- [ ] Create `v5/topology-tools/discover-hardware-identity.py`:
  - SSH/API collection for MAC and serial where available
  - YAML patch output for instance shard updates

### 7.2 Instance Updates

- [ ] Replace placeholder identities in `v5/topology/instances/l1_devices/` where still unresolved.
- [ ] Ensure identity fields satisfy ADR0068 format rules.

### 7.3 Enforcement Gate

- [ ] Keep `E6806` enforcement mode in strict mode.
- [ ] Add CI check that blocks unresolved placeholder markers in strict profiles.

### Phase 7 Definition of Done

- [ ] no unresolved placeholder markers remain in strict-gated instance shards.
- [ ] identity capture process is repeatable and documented.

---

## Phase 8: Integration, CI Hardening, and Cutover

**Duration estimate:** 1 week  
**Prerequisite:** Phases 3-7

### 8.1 Unified End-to-End Gate

- [ ] Add E2E workflow:
  - compile topology
  - run generator plugins
  - run Terraform validation
  - run Ansible inventory validation

### 8.2 Deployment Dry-Run

- [ ] Execute `terraform plan` in test environment for both targets.
- [ ] Execute Ansible `--check` on representative hosts.
- [ ] Record blockers and rollback actions.

### 8.3 Documentation and ADR Updates

- [ ] Update `README.md` and `README-РУССКИЙ.md` with v5 deploy workflow.
- [ ] Update `v5/topology-tools/docs/MANUAL-ARTIFACT-BUILD.md` with new artifact roots.
- [ ] Create ADR for v5 generator architecture and update ADR cutover milestones.
- [ ] Mark v4 lane as maintenance-only once v5 deployment gate is stable.

### Phase 8 Definition of Done

- [ ] v5 lane is operational for deployable artifacts.
- [ ] CI gate is fully green on plugin/generator/parity checks.
- [ ] runbook and rollback docs are complete.

---

## Cross-Phase Quality Gates

| Gate | Required In |
|------|-------------|
| `make validate-v5` green | Every phase entry |
| Plugin manifest schema validation | Every plugin change |
| Deterministic output test | All generators |
| Parity tests vs v4 baseline | Phases 3-6 |
| Terraform `fmt` + `validate` | Phases 3-4, Phase 8 |
| `ansible-inventory --list` | Phase 5, Phase 8 |
| Secret-safe artifact scan | Phases 6-8 |

---

## Success Criteria

1. **Generator parity:** v5 emits Terraform/Ansible/bootstrap outputs equivalent to v4 baseline (except approved diffs).
2. **Deterministic artifacts:** repeated runs produce stable outputs.
3. **Strict placeholder compliance:** unresolved placeholder markers are blocked in strict mode.
4. **Deployable workflow:** `terraform plan/apply` and Ansible runs succeed in test environment using v5-generated artifacts.
5. **Operational cutover:** v5 is default lane for new deployment work; v4 remains maintenance-only.

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Baseline instability delays generator work | Mandatory Phase 0 gate; no generator implementation before green baseline |
| Template incompatibility | Projection layer + incremental migration with per-generator parity tests |
| Hidden schema drift in compiled model | Projection contract tests with snapshot/golden coverage |
| Secret leakage in generated outputs | Example-only committed artifacts + CI scanning |
| v4 regression during migration | Freeze v4 logic; use v4 outputs as reference baseline only |

---

## Dependencies

```
Phase 0 (Baseline)
    └── Phase 1 (Generator SDK)
            └── Phase 2 (Projection Layer)
                    ├── Phase 3 (Terraform Proxmox)
                    ├── Phase 4 (Terraform MikroTik)
                    └── Phase 5 (Ansible)
                            └── Phase 6 (Bootstrap)
                                    └── Phase 8 (Integration/Cutover)

Phase 7 (Hardware Identity) ─────────────┘
```

---

## Tracking

Progress is tracked in:
- GitHub Issues (one issue per phase + sub-task checklist)
- this document (checkbox updates + DoD status)
- ADR status updates at milestone completion
