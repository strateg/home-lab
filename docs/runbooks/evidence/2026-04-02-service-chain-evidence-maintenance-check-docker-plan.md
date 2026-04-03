# 2026-04-02 Docker Plan Evidence

## Intent
Capture the maintenance-check execution plan with explicit runner consideration for reproducibility.

## Runner Decision
- Selected for actual device operations: `wsl:Ubuntu` (validated access to local LAN and SOPS secrets).
- Docker path retained as optional tooling plan only; not used for live MikroTik bootstrap in this run.

## Planned Commands
1. `task deploy:service-chain-evidence-check-bundle BUNDLE=<bundle_id> DEPLOY_RUNNER=docker`
2. `task deploy:init-node-plan BUNDLE=<bundle_id> NODE=rtr-mikrotik-chateau DEPLOY_RUNNER=docker PHASE=bootstrap`

## Status
- Planning reference stored.
- Live execution used WSL runner to match network reachability constraints.
