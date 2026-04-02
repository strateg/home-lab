# Node Initialization (Scaffold)

**Status:** Experimental scaffold
**Updated:** 2026-04-02
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

Partially implemented:
- `netinstall` adapter execute path is phase-aware:
  - `bootstrap` (default phase): bootstrap script is uploaded/imported via `scp + ssh` contract:
    - `INIT_NODE_NETINSTALL_SSH_HOST`
    - `INIT_NODE_NETINSTALL_SSH_USER`
  - `recover` phase: reserved recovery path allows netinstall/custom contracts:
    - custom command via `INIT_NODE_NETINSTALL_COMMAND`
    - native `netinstall-cli` env contract (`MIKROTIK_BOOTSTRAP_MAC`, `MIKROTIK_NETINSTALL_INTERFACE`, `MIKROTIK_NETINSTALL_CLIENT_IP`, `MIKROTIK_ROUTEROS_PACKAGE`)

Not implemented yet:
- full native netinstall-cli orchestration (without external command contract)
- full retry/backoff policy orchestration

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

Execute one node (bootstrap via SCP+SSH import):

```powershell
$env:INIT_NODE_NETINSTALL_SSH_HOST='192.168.88.1'
$env:INIT_NODE_NETINSTALL_SSH_USER='admin'
task framework:deploy-init-node-run -- BUNDLE=<bundle_id> NODE=<node_id> DEPLOY_RUNNER=docker PHASE=bootstrap
```

Execute one node (recovery mode; netinstall contract kept for future recover phase):

```powershell
$env:MIKROTIK_BOOTSTRAP_MAC='00:11:22:33:44:55'
$env:MIKROTIK_NETINSTALL_INTERFACE='eth0'
$env:MIKROTIK_NETINSTALL_CLIENT_IP='192.168.88.3'
$env:MIKROTIK_ROUTEROS_PACKAGE='/path/to/routeros-arm64.npk'
task framework:deploy-init-node-run -- BUNDLE=<bundle_id> NODE=<node_id> PHASE=recover
```

Verify one initialized node (handover checks):

```powershell
task framework:deploy-init-node-run -- BUNDLE=<bundle_id> NODE=<node_id> VERIFY_ONLY=1
```

---

## 3. Notes

- `init-node` currently emits execution plan JSON and initializes state baseline.
- non-`--plan-only` execution runs adapter preflight + adapter execute flow and updates state.
- `--verify-only` now runs adapter handover checks and can transition `initialized -> verified`.
- `netinstall` handover can include TCP checks for SSH/REST when `INIT_NODE_NETINSTALL_HANDOVER_HOST` is set.
- `bootstrap` phase defaults to `scp + ssh /import`; no netinstall reinstall should run in bootstrap mode.
- Explicit phase override is available via `--phase bootstrap|recover` (Task passthrough var: `PHASE`).
- non-plan execute/verify flows now stage bundle in selected runner workspace and call runner cleanup after execution.
- Use immutable deploy bundles from ADR 0085 (`task framework:deploy-bundle-create`).
- This is still safe in current state because destructive adapter execution is not implemented.
- Environment precheck runs by default for non-`--status` commands; use `SKIP_ENVIRONMENT_CHECK=1` only for isolated tests.
- Environment setup reference: `docs/guides/OPERATOR-ENVIRONMENT-SETUP.md`.
- Unknown `--node` now fails fast with `status=node-not-found` and available manifest node list.
