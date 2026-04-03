# ADR 0083 Reactivation Pack (Paused -> Active)

**Date:** 2026-04-03
**Status:** Preparation-only (no implementation start)
**Purpose:** Provide a repeatable go/no-go package to re-activate ADR 0083 work when hardware window is available.

---

## 1. Scope

This pack covers:

1. Preconditions to unpause ADR 0083.
2. Hardware-readiness checklist by mechanism.
3. Non-destructive smoke-run commands.
4. Go/No-Go decision criteria.

This pack does **not** start new implementation.

---

## 2. Preconditions (Must Be True)

1. ADR governance baseline is aligned:
   - `ADR 0085` accepted/implemented.
   - `ADR 0084` accepted/implemented.
   - `ADR 0083` remains `Proposed (scaffold complete, hardware pending)`.
2. Dev/deploy strict lanes are green:
   - `task ci:python-checks-core`
3. ADR governance checks are green:
   - `task validate:adr-consistency`
4. ADR0047 trigger remains below thresholds (or accepted as separate work):
   - `task validate:adr0047-trigger-gate`
5. Deploy bundle flow works:
   - `task bundle:create INJECT_SECRETS=true`
6. Runner/toolchain is ready for selected environment:
   - WSL/Linux path: use `DEPLOY_RUNNER=native`.
   - If password-based SSH bootstrap is used, `paramiko` must be installed in `.venv`.

---

## 3. Hardware Readiness Checklist

### 3.1 MikroTik (`netinstall`)

- [ ] Netinstall network segment reachable from deploy runner.
- [ ] Device can be reset to bootloader/netinstall mode.
- [ ] RouterOS bundle/version selected and available.
- [ ] Bootstrap SSH/API credentials prepared in project secrets.
- [ ] Rollback path prepared (manual recovery instructions + backup state).

### 3.2 Proxmox (`unattended_install`)

- [ ] Target node can boot install media.
- [ ] Unattended `answer.toml` validated against intended disk/network layout.
- [ ] Post-install minimal bootstrap path available.
- [ ] Out-of-band access available for recovery.

### 3.3 Orange Pi (`cloud_init`)

- [ ] Tested base image selected.
- [ ] `user-data` and `meta-data` media preparation path available.
- [ ] Serial/console access available for first boot diagnostics.

---

## 4. Smoke-Run Command Pack (Non-Destructive First)

Use this order:

```bash
# 1) Baseline checks
task ci:python-checks-core
task validate:adr-consistency
task validate:adr0083-reactivation

# 2) Prepare bundle
task bundle:create INJECT_SECRETS=true
task bundle:list

# 3) Check init state
task deploy:init-status

# 4) Run bundled non-destructive smoke pack (status + all-pending plan + node plan)
task deploy:init-reactivation-smoke BUNDLE=<bundle_id> NODE=rtr-mikrotik-chateau PHASE=bootstrap
```

Optional environment guard for WSL/Linux:

```bash
task deploy:init-all-pending-plan BUNDLE=<bundle_id> DEPLOY_RUNNER=native
```

For workstation-side dry verification when runner/toolchain checks are handled separately:

```bash
task deploy:init-reactivation-smoke BUNDLE=<bundle_id> SKIP_ENVIRONMENT_CHECK=true
```

If a full execution rehearsal is approved, start with one node only:

```bash
task deploy:init-node-run BUNDLE=<bundle_id> NODE=rtr-mikrotik-chateau DEPLOY_RUNNER=native
```

---

## 5. Go / No-Go Criteria

### Go

All conditions:

1. Preconditions in section 2 are green.
2. Plan-only commands complete without environment/contract errors.
3. Hardware checklist for chosen mechanism is complete.
4. Responsible operator confirms rollback path.

### No-Go

Any of:

1. `environment-error` in init-node planning.
2. Missing secrets/toolchain for selected mechanism.
3. Hardware access window not guaranteed.
4. Recovery path cannot be executed same day.

---

## 6. Reactivation Outputs (When Unpaused)

On formal reactivation, create:

1. `adr/0083-analysis/HARDWARE-EVIDENCE-YYYY-MM-DD.md` with executed commands and outcomes.
2. Updates in `adr/0083-analysis/CUTOVER-CHECKLIST.md` for hardware-validated items.
3. ADR status proposal update (`Proposed` -> `Accepted`) only after hardware gate completion.
