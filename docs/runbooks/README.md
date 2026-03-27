# Runbooks Index

**Status:** Active
**Updated:** 2026-03-28
**Scope:** V5 post-migration operational readiness (Wave D / Phase 12)

---

## Core Runbooks

- `docs/runbooks/V5-E2E-DRY-RUN.md` - compile/generate/validate dry-run without production apply.
- `docs/runbooks/DEPLOYMENT-PROCEDURES.md` - staged deployment flow for Proxmox, MikroTik, and service lane.
- `docs/runbooks/TROUBLESHOOTING-INFRA-COMPONENTS.md` - troubleshooting matrix per infrastructure component.
- `docs/runbooks/BACKUP-RESTORE-PROCEDURES.md` - backup and restore operating procedure.
- `docs/runbooks/DISASTER-RECOVERY-PLAYBOOK.md` - disaster recovery execution plan with RTO/RPO checkpoints.
- `docs/runbooks/MONITORING-ALERT-RUNBOOKS.md` - alert handling procedures by signal family.
- `docs/runbooks/SERVICE-DEPLOYMENT-CHAIN-VALIDATION.md` - evidence template for full service deployment chain validation.

---

## Required Gate Commands

```powershell
task acceptance:tests-all
task framework:cutover-readiness
```

For release-focused lanes, also run:

```powershell
task framework:release-tests
task validate:v5
task ansible:runtime
task ansible:syntax
```

---

## Evidence Policy

For each execution window, attach:

- command log (stdout/stderr) for each gate,
- diagnostics snapshot under `build/diagnostics/`,
- change record reference (PR/commit/tag),
- rollback decision (`go` or `no-go`) with reason.
