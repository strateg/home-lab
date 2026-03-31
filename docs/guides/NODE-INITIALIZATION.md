# Node Initialization (Scaffold)

**Status:** Experimental scaffold
**Updated:** 2026-03-31
**Scope:** ADR 0083 Phase 5.3 baseline (`init-node` CLI/state/status)

---

## 1. Current Scope

Implemented now:
- bundle-first CLI contract (`--bundle`, `--node`, `--all-pending`, `--status`)
- guardrails (`--reset` requires `--confirm-reset`, `--verify-only` vs `--force` validation)
- state bootstrap file under:
  - `.work/deploy-state/<project>/nodes/INITIALIZATION-STATE.yaml`
- planning output (`--plan-only`)
- adapter/state scaffolding:
  - `scripts/orchestration/deploy/adapters/base.py`
  - `scripts/orchestration/deploy/adapters/__init__.py`
  - `scripts/orchestration/deploy/state.py`
- deploy environment precheck (`check_deploy_environment()`), with optional `--skip-environment-check` for isolated test runs

Not implemented yet:
- adapter execution (`netinstall`, `unattended`, `cloud-init`, `ansible_bootstrap`)
- full state-machine transitions and handover checks

---

## 2. Commands

State summary:

```powershell
task framework:deploy-init-status
```

Plan one node:

```powershell
task framework:deploy-init-node-plan -- BUNDLE=<bundle_id> NODE=<node_id>
```

Plan one node with explicit runner:

```powershell
task framework:deploy-init-node-plan -- BUNDLE=<bundle_id> NODE=<node_id> DEPLOY_RUNNER=wsl
```

Plan all pending:

```powershell
task framework:deploy-init-all-pending-plan -- BUNDLE=<bundle_id>
```

---

## 3. Notes

- `init-node` currently emits execution plan JSON and initializes state baseline.
- Use immutable deploy bundles from ADR 0085 (`task framework:deploy-bundle-create`).
- This is safe to run in current state because no destructive adapter execution is active yet.
- Environment precheck runs by default for non-`--status` commands; use `SKIP_ENVIRONMENT_CHECK=1` only for isolated tests.
- Environment setup reference: `docs/guides/OPERATOR-ENVIRONMENT-SETUP.md`.
