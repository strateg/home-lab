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

Plan all pending:

```powershell
task framework:deploy-init-all-pending-plan -- BUNDLE=<bundle_id>
```

---

## 3. Notes

- `init-node` currently emits execution plan JSON and initializes state baseline.
- Use immutable deploy bundles from ADR 0085 (`task framework:deploy-bundle-create`).
- This is safe to run in current state because no destructive adapter execution is active yet.
