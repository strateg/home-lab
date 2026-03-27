# V5 Production Readiness Plan

**Created:** 2026-03-15
**Revised:** 2026-03-27
**Goal:** Complete v4→v5 migration and achieve full production parity
**Current State:** Core infrastructure generation operational (Phases 0-6 complete, E2E validated 2026-03-24). Remaining: hardware identity closure, v4 validator parity cutover, documentation/diagram generation migration, operational documentation.

---

## Executive Summary

v5 architecture is **operational for deployable artifacts** with:
- 60 plugins (8 compilers, 36 validators, 11 generators, assemblers/builders)
- compile → validate → generate → terraform/ansible stage chain working
- E2E dry-run passing (0 errors, 14 warnings, 2026-03-24)
- ADR 0080 unified build pipeline with strict data-bus contracts

**Completed milestones:**
- ✅ Phase 0-6: baseline, generator SDK, projections, Terraform (Proxmox + MikroTik), Ansible, bootstrap
- ✅ ADR 0075/0074 master migration (monorepo separation, project-aware generators)
- ✅ ADR 0078 Phase 5 unified refactor (WP-001 through WP-006)
- ✅ ADR 0080 unified build pipeline (parallel execution, strict contracts)

**Remaining gaps (by priority):**
- P0: Hardware identity closure (Phase 7), v4 validator staged cutover
- P1: Documentation & diagram generation (ADR 0079, template parity delivered; icon-pack runtime hardening pending)
- P1: Cross-layer relation validators (ADR 0062)
- P2: Operational runbooks and multi-repo extraction (ADR 0076)

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
- [x] output ownership contract is documented and approved (project-qualified roots per ADR 0075).

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

- [x] Add unit tests with golden snapshots for projection outputs.
- [x] Add negative tests for missing mandatory fields and malformed refs.

### Phase 2 Definition of Done

- [x] templates can render using projections without reaching into raw compiled internals.
- [x] projection snapshots are stable between runs.

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

- [x] Add `v5/tests/plugin_regression/test_terraform_proxmox_parity.py`.
- [x] Compare generated files against v4 baseline (with documented intentional diffs).
- [x] Run `terraform fmt -check` and `terraform validate` in CI for generated Proxmox output.

### Phase 3 Definition of Done

- [x] Proxmox Terraform output is generated in `v5-generated/<project>/terraform/proxmox/`.
- [x] parity gate is green (or only approved diffs remain).

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

- [x] Drive optional resource generation from effective capabilities and platform traits.
- [x] Keep device-specific branching in projection layer, not templates.

### 4.3 Parity and Syntax Gates

- [x] Add `v5/tests/plugin_regression/test_terraform_mikrotik_parity.py`.
- [x] Run `terraform fmt -check` and `terraform validate` in CI for generated MikroTik output.

### Phase 4 Definition of Done

- [x] MikroTik Terraform output is generated in `v5-generated/<project>/terraform/mikrotik/`.
- [x] parity gate is green (or only approved diffs remain).

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

- [x] Implement runtime inventory assembly flow for environment-specific materialization.
- [x] Keep secrets externalized; committed inventory remains safe placeholders/examples.

### 5.3 Parity and Validation

- [x] Add `v5/tests/plugin_regression/test_ansible_inventory_parity.py`.
- [x] Validate generated inventory with `ansible-inventory --list`.

### Phase 5 Definition of Done

- [x] Ansible inventory output is generated in `v5-generated/<project>/ansible/inventory/production/`.
- [x] parity and inventory validation are green.

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

- [x] bootstrap artifacts are generated under `v5-generated/<project>/bootstrap/<device-id>/`.
- [x] all committed bootstrap outputs are release-safe (no real secrets).

---

## Phase 7: Hardware Identity Capture and Placeholder Closure

**Duration estimate:** 3-4 days
**Prerequisite:** Can run in parallel after Phase 3 starts

### 7.1 Discovery Utility

- [x] Create `v5/topology-tools/discover-hardware-identity.py`:
  - SSH/API collection for MAC and serial where available
  - YAML patch output for instance shard updates

### 7.2 Instance Updates

- [x] Replace placeholder identities/placeholders in strict-gated instance shards (`projects/home-lab/topology/instances/**`).
- [x] Ensure identity-related fields satisfy ADR0068 format rules.

### 7.3 Enforcement Gate

- [x] Keep `E6806` enforcement mode in strict mode.
- [x] Add CI check that blocks unresolved placeholder markers in strict profiles (`tests/test_strict_profile_placeholder_contract.py`).

### Phase 7 Definition of Done

- [x] no unresolved placeholder markers remain in strict-gated instance shards.
- [x] identity capture process is repeatable and documented.

---

## Phase 8: Integration, CI Hardening, and Cutover

**Duration estimate:** 1 week
**Prerequisite:** Phases 3-7
**Status:** ✅ Core complete (E2E validated 2026-03-24). Cutover documentation remaining.

### 8.1 Unified End-to-End Gate

- [x] Add E2E workflow:
  - compile topology
  - run generator plugins
  - run Terraform validation
  - run Ansible inventory validation
- [x] E2E dry-run executed (2026-03-24): 0 errors, 14 warnings, 69 infos
  - Terraform Proxmox: init + fmt + validate ✅
  - Terraform MikroTik: init + fmt + validate ✅
  - Ansible inventory: 15 hosts ✅
  - Bootstrap: 3 devices ✅

### 8.2 Deployment Dry-Run

- [x] Execute `terraform plan` in test environment for both targets.
- [x] Execute Ansible `--check` on representative hosts.
- [x] Record blockers and rollback actions.

### 8.3 Documentation and ADR Updates

- [ ] Update `README.md` and `README-РУССКИЙ.md` with v5 deploy workflow.
- [x] Update `topology-tools/docs/MANUAL-ARTIFACT-BUILD.md` with new artifact roots.
- [x] Create ADR for v5 generator architecture and update ADR cutover milestones.
- [ ] Mark v4 lane as maintenance-only once v5 deployment gate is stable.

### 8.4 Cosmetic Warning Cleanup

- [x] W7845 (SSL certificates): Added `security.ssl_certificate: self-signed` to HTTPS services.
- [ ] W7888 (9 warnings): Migrate LXC to resource profiles — requires resource profile taxonomy.
- [x] W7816 (IP reuse): Expected for gateway/postgres — documented as intentional.

### Phase 8 Definition of Done

- [x] v5 lane is operational for deployable artifacts.
- [x] CI gate is fully green on plugin/generator/parity checks.
- [x] runbook published: `docs/runbooks/V5-E2E-DRY-RUN.md`.
- [ ] v4 lane marked maintenance-only in README.

---

## Phase 9: V4 Validator Parity Cutover (NEW)

**Prerequisite:** Phase 8
**Status:** Active — staged cutover baseline (ADR 0078 deprecation matrix)
**Tracking:** `adr/plan/0078-v4-validator-deprecation-matrix.md`

All 30 v4 validators have v5 plugin replacements registered. Current status: `Covered/Partial` for all rows. Staged cutover requires parity fixture locks per domain.

### 9.1 Foundation Domain

- [ ] Lock file_placement warning semantics parity fixture.
- [ ] Lock include_contract parity fixture.
- [ ] Close storage-related edge fixtures for device_taxonomy.

### 9.2 Governance Domain

- [ ] Lock version field warning-semantics parity.
- [ ] Close class-taxonomy coupling edge cases for `network_manager_device_ref` defaults.

### 9.3 Network Domain

- [ ] Create non-VLAN legacy payload shape parity fixtures.
- [ ] Lock firewall policy scope edge case fixtures.
- [ ] Lock `check_reserved_ranges` non-VLAN shape fixtures.
- [ ] Lock `check_runtime_network_reachability` active-only payload parity.
- [ ] Close `check_single_active_os_per_device` legacy inventory parity decision.

### 9.4 References Domain

- [ ] Lock host_os non-extension payload path fixtures.
- [ ] Lock vm_refs architecture/capability/storage/bridge parity fixtures.
- [ ] Lock lxc_refs architecture/capability/storage/deprecation parity fixtures.
- [ ] Lock service_refs runtime/dependency/external_services warning parity.
- [ ] Lock DNS, certificate, backup, security_policy fixture parity.

### 9.5 Storage Domain

- [ ] Lock hardware edge fixture parity for device_storage_taxonomy.
- [ ] Lock media-attachment edge fixtures for l1_media_inventory.
- [ ] Lock infer_from warning semantics for l3_storage_refs.

### 9.6 Cutover Execution

- [ ] Disable v4 checks batch-wise after parity evidence for each domain.
- [ ] Update `taskfiles/validate.yml` to v5-only validation path.
- [ ] Verify `task test:parity-v4-v5` green after each batch.
- [ ] Update `framework.lock.yaml` and verify `rehearse_rollback` readiness.

### Phase 9 Definition of Done

- [ ] All v4 validator checks disabled with parity evidence.
- [ ] `task validate:v5` is the sole validation path.
- [ ] No v4 fallback required in release lane.

---

## Phase 10: Documentation and Diagram Generation Migration (NEW)

**Prerequisite:** Phase 8
**Status:** Active (ADR 0079 accepted)
**Tracking:** `adr/0079-v5-documentation-and-diagram-generation-migration.md`

V5 now has 19 documentation templates (+ diagram index/legend pages); remaining work is icon-pack runtime hardening.

### 10.1 Phase A — Network Layer Diagrams

- [x] IP allocation table template.
- [x] VLAN topology diagram template.
- [x] DNS/DHCP overview template.
- [x] Network projection module for docs generator.

### 10.2 Phase B — Physical Layer Diagrams

- [x] Rack layout diagram template.
- [x] UPS/power distribution diagram template.
- [x] Physical connectivity diagram (enhanced).
- [x] Physical projection module.

### 10.3 Phase C — Security Layer Diagrams

- [x] Trust zone firewall policy diagram template.
- [x] VPN topology diagram template.
- [x] Security posture matrix template.
- [x] Security projection module.

### 10.4 Phase D — Application & Storage Diagrams

- [x] Service dependency graph template.
- [x] Data flow diagram (logs, metrics, backups) template.
- [x] Storage architecture diagram template.
- [x] Application/storage projection modules.

### 10.5 Phase E — Operations Diagrams

- [x] Monitoring stack topology template.
- [x] QoS/traffic shaping diagram template.
- [x] Backup schedule overview template.
- [x] Operations projection module.

### 10.6 Phase F — Icon System & Tooling

- [x] Icon manager: centralized resolver module introduced for docs/diagrams.
- [x] Icon mapping registry (class/service/zone mappings) integrated.
- [ ] SVG caching and Mermaid icon-node rendering.
- [x] Icon legend template and diagrams-index template.
- [x] Mermaid render validation quality gate.

### Phase 10 Definition of Done

- [x] 19 documentation templates generating (parity with v4).
- [ ] Icon system operational with si/mdi packs.
- [x] Mermaid render validation in CI pipeline.
- [x] All generated docs stable between deterministic runs.

---

## Phase 11: ADR 0058-0071 Remaining Backlog Closure (NEW)

**Prerequisite:** Phases 8-9
**Status:** Active (partial items resolved)
**Tracking:** `adr/0058-0071-remaining-work.md`

### 11.1 P0 Items

- [x] ADR 0069 status promotion completed (`Accepted`, evidence in register + cutover docs).
- [x] ADR 0068 enforcement policy rollout completed (`warn` → `warn+gate-new` → `enforce`).
- [x] ADR 0068 placeholder closure: strict-gated profiles are free of unresolved placeholders; CI guard added.
- [ ] Remove stale contract examples and normalize to canonical IDs.

### 11.2 P1 Items

- [ ] ADR 0063: decide and lock YAML-validator tail (complete migration or explicit non-goal).
- [ ] ADR 0062: convert `planned` cross-layer relations to executable backlog:
  - `storage.pool_ref`, `storage.volume_ref` — validator ownership + acceptance tests.
  - `network.bridge_ref`, `network.vlan_ref` — validator ownership + acceptance tests.
  - `observability.target_ref`, `operations.target_ref` — validator ownership + acceptance tests.
  - `power.source_ref` — validator ownership + acceptance tests.

### 11.3 P2 Items

- [ ] Documentation consistency sweep: add/refresh "historical/superseded" headers.
- [ ] Ensure `adr/PLUGIN-RUNTIME-ADR-MAP.md` remains authoritative entry map.

### Phase 11 Definition of Done

- [x] ADR 0069 is `Accepted`.
- [x] E6806 enforce mode blocks unresolved placeholders deterministically.
- [ ] All 7 cross-layer relations have owner, validator, and acceptance test.
- [ ] No stale "planned" or contradictory statements in active ADR docs.

---

## Phase 12: Operational Readiness (NEW)

**Prerequisite:** Phases 8, 10
**Status:** Not started

### 12.1 Operational Documentation

- [ ] Deployment procedures (step-by-step for Proxmox, MikroTik, services).
- [ ] Troubleshooting guides per infrastructure component.
- [ ] Backup/restore procedures.
- [ ] Disaster recovery playbook.
- [ ] Monitoring alert runbooks.

### 12.2 Ansible Service Playbooks Integration

- [ ] Full Nextcloud deployment playbook (role exists, needs integration).
- [ ] Full PostgreSQL deployment playbook (role exists, needs integration).
- [ ] Full Redis deployment playbook (role exists, needs integration).
- [ ] Monitoring stack playbooks (Prometheus, Grafana, Loki, AlertManager).
- [ ] Secret distribution via Ansible (SOPS/age integration per ADR 0072).

### 12.3 Advanced Infrastructure

- [ ] Terraform remote state backend configuration.
- [ ] VPN server Terraform for external VPS (business decision required).
- [ ] W7888 resource profile taxonomy for LXC migration.

### Phase 12 Definition of Done

- [ ] All operational runbooks published in `docs/runbooks/`.
- [ ] Service deployment chain tested: topology → compile → generate → terraform apply → ansible deploy.
- [ ] DR procedures validated with documented recovery time.

---

## Phase 13: Multi-Repository Extraction (DEFERRED)

**Prerequisite:** Phases 8-12 stable
**Status:** Deferred (ADR 0076)
**Tracking:** `adr/plan/0076-multi-repo-extraction-plan.md`

- [ ] Separate framework from project into independent repositories.
- [ ] Establish cross-repo CI/CD pipelines.
- [ ] Define dependency lock and integrity verification.
- [ ] Separate roadmap and risk assessment.

---

## Cross-Phase Quality Gates

| Gate | Required In |
|------|-------------|
| `make validate-v5` green | Every phase entry |
| Plugin manifest schema validation | Every plugin change |
| Deterministic output test | All generators |
| Parity tests vs v4 baseline | Phases 3-6, 9 |
| Terraform `fmt` + `validate` | Phases 3-4, Phase 8 |
| `ansible-inventory --list` | Phase 5, Phase 8 |
| Secret-safe artifact scan | Phases 6-8 |
| V4/v5 parity lane green | Phase 9 cutover batches |
| Mermaid render validation | Phase 10 |

---

## Success Criteria

1. **Generator parity:** ✅ v5 emits Terraform/Ansible/bootstrap outputs equivalent to v4 baseline (validated 2026-03-24).
2. **Deterministic artifacts:** ✅ Repeated runs produce stable outputs.
3. **Strict placeholder compliance:** ✅ Enforced — strict-gated instance placeholders are CI-blocked (2026-03-27).
4. **Deployable workflow:** ✅ `terraform plan/apply` and Ansible runs succeed using v5-generated artifacts.
5. **Operational cutover:** Partial — v5 is default lane; v4 still active as fallback (Phase 9).
6. **Documentation parity:** ✅ 19/19 templates generating (+ diagrams/index pages); icon-pack runtime hardening remains.
7. **Validator cutover:** In progress — staged v4 deprecation (Phase 9).

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Baseline instability delays generator work | ✅ Resolved: Phase 0 gate passed |
| Template incompatibility | ✅ Resolved: Projection layer + per-generator parity tests |
| Hidden schema drift in compiled model | ✅ Resolved: Projection contract tests with snapshot coverage |
| Secret leakage in generated outputs | ✅ Resolved: Example-only artifacts + CI scanning |
| v4 regression during migration | ✅ Resolved: v4 frozen as reference baseline |
| V4 validator cutover breaks validation | Staged batch cutover with parity fixtures per domain |
| Docs migration scope creep | ADR 0079 phased approach (A-F) with independent milestones |
| Cross-layer relation validators incomplete | ADR 0062 executable backlog with per-relation ownership |

---

## Dependencies

```
Phase 0 (Baseline) ✅
    └── Phase 1 (Generator SDK) ✅
            └── Phase 2 (Projection Layer) ✅
                    ├── Phase 3 (Terraform Proxmox) ✅
                    ├── Phase 4 (Terraform MikroTik) ✅
                    └── Phase 5 (Ansible) ✅
                            └── Phase 6 (Bootstrap) ✅
                                    └── Phase 8 (Integration/Cutover) ✅ core / remaining docs
                                            ├── Phase 9 (V4 Validator Cutover)
                                            ├── Phase 10 (Docs/Diagrams Migration)
                                            ├── Phase 11 (ADR Backlog Closure)
                                            └── Phase 12 (Operational Readiness)
                                                    └── Phase 13 (Multi-Repo) [DEFERRED]

Phase 7 (Hardware Identity) ─── in parallel ───┘
```

---

## Tracking

Progress is tracked in:
- GitHub Issues (one issue per phase + sub-task checklist)
- this document (checkbox updates + DoD status)
- ADR status updates at milestone completion
- `adr/plan/0078-v4-validator-deprecation-matrix.md` (validator parity)
- `adr/0079-v5-documentation-and-diagram-generation-migration.md` (docs migration)
- `adr/0058-0071-remaining-work.md` (ADR backlog)

---

## Completion Summary

### Completed Phases

| Phase | Completed | Key Evidence |
|-------|-----------|--------------|
| Phase 0: Baseline | 2026-03-15 | `validate-v5` green, diagnostics zero errors |
| Phase 1: Generator SDK | 2026-03-17 | `base_generator.py`, `plugins.yaml` contracts |
| Phase 2: Projections | 2026-03-18 | `projections.py`, snapshot tests stable |
| Phase 3: Terraform Proxmox | 2026-03-19 | 8 `.tf` files, fmt + validate green |
| Phase 4: Terraform MikroTik | 2026-03-19 | 12 `.tf` files, fmt + validate green |
| Phase 5: Ansible Inventory | 2026-03-20 | `hosts.yml` + 15 host_vars, inventory --list green |
| Phase 6: Bootstrap | 2026-03-20 | 3 device bootstrap packages |
| ADR 0075/0074 Master | 2026-03-24 | E2E validated, 271 tests passed |
| ADR 0078 Phase 5 | 2026-03-23 | WP-001-006 complete, 58/58 gates green |
| ADR 0080 Build Pipeline | 2026-03-27 | Strict contracts, parallel execution |
| Phase 8: E2E Core | 2026-03-24 | 0 errors, 14 warnings, dry-run passing |

### Active/Remaining Phases

| Phase | Status | Blocking? |
|-------|--------|-----------|
| Phase 7: Hardware Identity | Completed (placeholder closure + strict CI gate, 2026-03-27) | - |
| Phase 8.3: Cutover Docs | README updates remaining | P1 |
| Phase 9: V4 Validator Cutover | Active (staged, all rows Covered/Partial) | P0 |
| Phase 10: Docs/Diagrams | Active (template parity delivered; icon-pack runtime hardening pending) | P1 |
| Phase 11: ADR Backlog | Active (governance closure done; relation backlog pending) | P1 |
| Phase 12: Operational Readiness | Not started | P2 |
| Phase 13: Multi-Repo | Deferred | P2 |
