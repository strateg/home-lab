# Node Initialization (Scaffold)

**Status:** Experimental scaffold
**Updated:** 2026-03-31
**Scope:** ADR 0083 Phase 5 scaffold (`init-node` CLI/state/status/verify baseline)

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
- mechanism-specific adapter baselines:
  - `scripts/orchestration/deploy/adapters/netinstall.py`
  - `scripts/orchestration/deploy/adapters/unattended.py`
  - `scripts/orchestration/deploy/adapters/cloud_init.py`
  - `scripts/orchestration/deploy/adapters/ansible_bootstrap.py`
- `--verify-only` handover baseline (`initialized -> verified`)
- structured JSONL audit logging:
  - `.work/deploy-state/<project>/logs/init-node-audit.jsonl`
- deploy environment precheck (`check_deploy_environment()`), with optional `--skip-environment-check` for isolated test runs

Not implemented yet:
- destructive adapter execution paths (bootstrapping actions remain not-implemented)
- full retry/backoff and external handover probes

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

Execute one node (scaffold execute path):

```powershell
task framework:deploy-init-node-run -- BUNDLE=<bundle_id> NODE=<node_id>
```

Verify one initialized node (handover checks):

```powershell
task framework:deploy-init-node-run -- BUNDLE=<bundle_id> NODE=<node_id> VERIFY_ONLY=1
```

---

## 3. Notes

- `init-node` currently emits execution plan JSON and initializes state baseline.
- non-`--plan-only` execution runs adapter preflight + placeholder execute flow and updates state.
- `--verify-only` now runs adapter handover checks and can transition `initialized -> verified`.
- Use immutable deploy bundles from ADR 0085 (`task framework:deploy-bundle-create`).
- This is still safe in current state because destructive adapter execution is not implemented.
- Environment precheck runs by default for non-`--status` commands; use `SKIP_ENVIRONMENT_CHECK=1` only for isolated tests.
- Environment setup reference: `docs/guides/OPERATOR-ENVIRONMENT-SETUP.md`.
- Unknown `--node` now fails fast with `status=node-not-found` and available manifest node list.
