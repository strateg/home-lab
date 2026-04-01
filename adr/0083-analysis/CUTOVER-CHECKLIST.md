# ADR 0083: Cutover Checklist

**Status note:** ADR 0085 and ADR 0084 are now Accepted with core implementation complete. ADR 0083 scaffold baseline is merged; adapter execute() methods and hardware tests remain for production readiness.

**Last updated:** 2026-03-31

## Pre-Cutover Gates

### Schema and Validation

- [x] `schemas/initialization-contract.schema.json` created and passes meta-validation
- [x] Object module schema extended with `initialization_contract` field
- [x] `base.validator.initialization_contract` plugin implemented (`topology-tools/plugins/validators/initialization_contract_validator.py`)
- [x] Validator unit tests pass (83 tests in orchestration suite)

### MikroTik Reference Implementation

- [x] `obj.mikrotik.chateau_lte7_ax.yaml` has valid `initialization_contract` (netinstall mechanism)
- [x] Bootstrap generator reads contract from compiled topology (`bootstrap_mikrotik_generator.py`)
- [x] Generated artifacts unchanged (regression test passes)
- [x] ADR 0057 compliance verified

### Proxmox Bootstrap

- [x] Proxmox object module created with `initialization_contract` (unattended_install mechanism)
- [x] `answer.toml.j2` template exists in bootstrap directory
- [x] `post-install-minimal.sh.j2` template exists with bootstrap scope
- [ ] Day-1 config documented for Terraform migration (hardware validation pending)
- [ ] Day-2 config documented for Ansible migration (hardware validation pending)
- [ ] Original `proxmox-post-install.sh` archived with migration notes

### Orange Pi Bootstrap

- [x] Orange Pi object module has valid `initialization_contract` (cloud_init mechanism)
- [x] `user-data.example.j2` template exists
- [x] Contract specifies `user_data` and `meta_data` outputs
- [ ] cloud-init files validated with `cloud-init schema --config-file` (hardware test)

### LXC/Cloud Patterns (Implicit Terraform-managed)

- [x] LXC object modules do NOT declare `initialization_contract` (implicit terraform-managed per D2)
- [x] Implicit terraform-managed pattern documented in ADR 0083 and GAP-ANALYSIS.md

### Initialization Manifest

- [x] `bootstrap_projections.py` plugin handles contract-aware bootstrap projection routing
- [x] Bundle manifest infers mechanism for root-level bootstrap artifacts
- [x] Manifest schema documented in ADR 0083 and bundle schema
- [x] Compute/router nodes appear in manifest when contract declared
- [x] Runtime state schema documented (`INITIALIZATION-STATE.yaml`) in `state.py`

### Orchestration

- [x] `scripts/orchestration/deploy/init_node.py` implemented (30,946 bytes)
- [x] `BootstrapAdapter` ABC in `adapters/base.py` (D19): `PreflightCheck`, `BootstrapResult`, `HandoverCheckResult`, `AdapterContext` dataclasses
- [x] All 4 adapters inherit from `BootstrapAdapter` and implement required abstract methods (preflight/handover baseline)
- [x] Adapter factory `get_adapter()` resolves mechanism → adapter class (`adapters/__init__.py`)
- [ ] Netinstall adapter works with MikroTik (execute() returns placeholder - hardware test pending)
- [x] Orchestrator owns state file; adapters return results only (D19 boundary enforced)
- [x] Orchestrator writes runtime state only to `.work/deploy-state/<project>/nodes/INITIALIZATION-STATE.yaml`
- [x] Orchestrator does not modify `generated/**`
- [x] State machine transitions enforced (`state.py`: LEGAL_TRANSITIONS, can_transition, assert_transition)
- [x] Atomic state updates with history tracking in `transition_node_state()`
- [x] Handover verification baseline implemented (adapter handover() methods with retry structure in schema)
  - [ ] `api_reachable` with retry/backoff (schema defined, adapter execute pending)
  - [ ] `ssh_reachable` with retry/backoff (schema defined, adapter execute pending)
  - [ ] Other check types defined in schema: `ansible_ping`, `http_status`, `tcp_port_open`
- [x] Structured logging (D20): console output + `.work/deploy-state/<project>/logs/init-node-audit.jsonl`
- [x] Audit trail events with mandatory fields: `timestamp`, `level`, `node`, `event`, `project_id`, `mechanism`, `status`, `message`, `error_code`, `details`
- [x] CLI interface documented and implemented (`--node`, `--all-pending`, `--verify-only`, `--force`, `--status`, `--plan`, `--bundle`, `--reset`, `--confirm-reset`)
- [x] Taskfile targets documented (deploy.yaml integration path)

### Assemble Stage (ADR 0085 bundle contract)

- [x] `bundle.py` implements bundle assembly with secret injection option (`--inject-secrets`)
- [x] Bundle assembly produces immutable bundles at `.work/deploy/bundles/<bundle_id>/`
- [x] Secret-bearing artifacts written only to bundle directory (not in `generated/`)
- [x] Bundle checksums verify integrity before staging
- [x] SOPS+age decryption path integrated in bundle assembly (ADR 0072)
- [x] `.work/` covered by .gitignore

---

## Cutover Execution

### Step 1: Freeze Legacy Scripts

- [ ] Announce deprecation of legacy initialization scripts
- [ ] Add deprecation notice to archive files

### Step 2: Enable New Workflow

- [x] Core implementation PRs merged (runner + profile + bundle + init-node scaffold)
- [x] v5 pipeline validation passes (82 tests)
- [x] Bundle manifest generated with mechanism inference
- [x] State file created in correct location on orchestration actions

### Step 3: Validate on Real Hardware

- [ ] MikroTik: Execute full netinstall + handover verification
- [ ] Proxmox: Validate answer.toml with fresh install (if possible)
- [ ] Orange Pi: Boot with generated cloud-init (manual)

### Step 4: Update Documentation

- [x] `docs/guides/DEPLOY-BUNDLE-WORKFLOW.md` published (ADR 0085)
- [ ] `docs/guides/NODE-INITIALIZATION.md` to be published (ADR 0083 hardware phase)
- [x] CLAUDE.md mentions deploy bundle workflow
- [x] Taskfile deploy wrappers documented

### Step 5: Archive Legacy

- [ ] Move legacy scripts to `archive/migrated-and-archived/`
- [ ] Add `MIGRATION-NOTES.md` explaining what was moved

---

## Post-Cutover Verification

### Functional Checks

- [x] `python scripts/orchestration/lane.py validate-v5` passes
- [x] `python topology-tools/compile-topology.py` produces bootstrap artifacts
- [ ] `task deploy:init:verify NODE=rtr-mikrotik-chateau` passes (hardware test pending)
- [x] `init-node.py --status` displays nodes with contracts
- [x] Runtime state updates are visible in `.work/deploy-state/<project>/nodes/INITIALIZATION-STATE.yaml`
- [x] No secrets present in `generated/` directory (bundle-only injection)

### Regression Checks

- [x] No v5 pipeline errors
- [x] All existing tests pass (82/83, 1 WSL skip expected)
- [x] No files under `generated/` are modified by deploy-time orchestration
- [ ] MikroTik Terraform plan succeeds (hardware test pending)
- [ ] Proxmox Terraform plan succeeds (hardware test pending)

### Documentation Checks

- [ ] All device types documented in NODE-INITIALIZATION.md (pending hardware validation)
- [ ] ADR 0083 status updated to Accepted (pending hardware validation)
- [x] REGISTER.md reflects current ADR statuses

---

## Rollback Plan

If cutover fails:

1. Revert merge commits
2. Restore legacy scripts from archive
3. Document failure in ADR 0083 analysis directory
4. Plan remediation before retry

---

## Sign-off

| Role | Name | Date | Signature |
|------|------|------|-----------|
| Author | | | |
| Reviewer | | | |
| Hardware Tester | | | |
