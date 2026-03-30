# ADR 0083: Cutover Checklist

## Pre-Cutover Gates

### Schema and Validation

- [ ] `schemas/initialization-contract.schema.json` created and passes meta-validation
- [ ] Object module schema extended with `initialization_contract` field
- [ ] `base.validator.initialization_contract` plugin implemented
- [ ] Validator unit tests pass (100% branch coverage)

### MikroTik Reference Implementation

- [ ] `obj.mikrotik.chateau_lte7_ax.yaml` has valid `initialization_contract`
- [ ] Bootstrap generator reads contract from compiled topology
- [ ] Generated artifacts unchanged (regression test passes)
- [ ] ADR 0057 compliance verified

### Proxmox Bootstrap

- [ ] Proxmox object module created with `initialization_contract`
- [ ] `answer.toml.j2` generates valid Proxmox answer file
- [ ] `post-install-minimal.sh.j2` contains ONLY:
  - [ ] API access enablement
  - [ ] terraform user creation
  - [ ] API token generation
  - [ ] Basic firewall for management
- [ ] Day-1 config documented for Terraform migration
- [ ] Day-2 config documented for Ansible migration
- [ ] Original `proxmox-post-install.sh` archived with migration notes

### Orange Pi Bootstrap

- [ ] Orange Pi object module has valid `initialization_contract`
- [ ] `user-data.j2` includes:
  - [ ] SSH authorized keys from secrets
  - [ ] Network configuration from topology
  - [ ] Python installation for Ansible
  - [ ] Hostname setting
- [ ] `meta-data.j2` generates valid cloud-init metadata
- [ ] cloud-init files validate with `cloud-init schema --config-file`

### LXC/Cloud Patterns (Implicit Terraform-managed)

- [ ] LXC object modules do NOT declare `initialization_contract` (implicit terraform-managed per D2)
- [ ] Implicit terraform-managed pattern documented in object module comments and operator guide

### Initialization Manifest

- [ ] `base.generator.initialization_manifest` plugin implemented
- [ ] INITIALIZATION-MANIFEST.yaml generated during v5 pipeline as read-only source-derived output
- [ ] Manifest schema documented
- [ ] All compute/router nodes appear in manifest
- [ ] Runtime state schema documented (`INITIALIZATION-STATE.yaml`)

### Orchestration

- [ ] `scripts/orchestration/deploy/init-node.py` implemented
- [ ] Netinstall adapter works with MikroTik
- [ ] Orchestrator writes runtime state only to `.work/native/bootstrap/INITIALIZATION-STATE.yaml`
- [ ] Orchestrator does not modify `generated/**`
- [ ] State machine transitions enforced (pending/bootstrapping/initialized/verified/failed)
- [ ] File locking for concurrent access implemented
- [ ] Atomic writes for state file implemented
- [ ] Handover verification checks implemented:
  - [ ] `api_reachable` with retry/backoff
  - [ ] `ssh_reachable` with retry/backoff
  - [ ] `credential_valid` with retry/backoff
  - [ ] `python_installed` with retry/backoff
  - [ ] `terraform_plan_succeeds` with retry/backoff
- [ ] CLI interface documented (`--node`, `--all-pending`, `--verify-only`, `--force`, `--status`, `--interactive`, `--import`, `--reset`, `--confirm-reset`, `--acknowledge-drift`, `--cleanup`)
- [ ] Taskfile targets added (`taskfiles/deploy.yaml`)

### Assemble Stage (requires ADR 0080 Wave F)

- [ ] `base.assembler.bootstrap_secrets` plugin implemented
- [ ] Assembler consumes `initialization_manifest_data` from data bus
- [ ] Secret-bearing artifacts written only to `.work/native/bootstrap/`
- [ ] Secret-leak scanner in assemble.verify detects secrets in `generated/`
- [ ] SOPS+age decryption integrated (ADR 0072)
- [ ] `.work/native/bootstrap/` covered by .gitignore

---

## Cutover Execution

### Step 1: Freeze Legacy Scripts

- [ ] Announce deprecation of legacy initialization scripts
- [ ] Add deprecation notice to archive files

### Step 2: Enable New Workflow

- [ ] Merge all implementation PRs
- [ ] Run full v5 pipeline validation
- [ ] Verify INITIALIZATION-MANIFEST.yaml generated
- [ ] Verify INITIALIZATION-STATE.yaml is created only after deploy/orchestration actions

### Step 3: Validate on Real Hardware

- [ ] MikroTik: Execute full netinstall + handover verification
- [ ] Proxmox: Validate answer.toml with fresh install (if possible)
- [ ] Orange Pi: Boot with generated cloud-init (manual)

### Step 4: Update Documentation

- [ ] `docs/guides/NODE-INITIALIZATION.md` published
- [ ] CLAUDE.md updated with initialization workflow
- [ ] Taskfile help updated

### Step 5: Archive Legacy

- [ ] Move legacy scripts to `archive/migrated-and-archived/`
- [ ] Add `MIGRATION-NOTES.md` explaining what was moved

---

## Post-Cutover Verification

### Functional Checks

- [ ] `python scripts/orchestration/lane.py validate-v5` passes
- [ ] `python topology-tools/compile-topology.py` produces bootstrap artifacts
- [ ] `task deploy:init:verify NODE=rtr-mikrotik-chateau` passes (after device initialized)
- [ ] `task deploy:init:status` displays all nodes
- [ ] Runtime state updates are visible in `.work/native/bootstrap/INITIALIZATION-STATE.yaml`
- [ ] No secrets present in `generated/` directory (leak scan passes)

### Regression Checks

- [ ] No v5 pipeline errors
- [ ] All existing tests pass
- [ ] No files under `generated/` are modified by deploy-time orchestration
- [ ] MikroTik Terraform plan succeeds
- [ ] Proxmox Terraform plan succeeds (if applicable)

### Documentation Checks

- [ ] All device types documented in NODE-INITIALIZATION.md
- [ ] ADR 0083 status updated to Accepted
- [ ] REGISTER.md updated

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
