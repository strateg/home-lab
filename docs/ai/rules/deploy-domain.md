# AI Rule Pack: Deploy Domain

> **Version:** 1.0 | **Updated:** 2026-06-15 | **ADRs:** See `ADR-RULE-MAP.yaml` → `deploy-domain.source_adr`

## Quick Reference

| Rule | Key Point |
|------|-----------|
| Bundle | Immutable execution input at `.work/deploy/bundles/<id>/` |
| Runner | Workspace-aware backends (native/wsl/docker/remote) |
| State | Mutable state under `.work/deploy-state/<project>/` |
| Init | Hardware-sensitive; requires E2E evidence |
| Plane | Dev=cross-platform, Deploy=Linux-backed |

## Load When

- `scripts/orchestration/deploy/**`
- `taskfiles/deploy.yml`, `taskfiles/product.yml`
- Deploy schemas, node initialization, deploy runner behavior

## Architecture

| Component | Location | Purpose |
|-----------|----------|---------|
| Deploy bundles | `.work/deploy/bundles/<id>/` | Immutable artifacts |
| Deploy state | `.work/deploy-state/<project>/` | Mutable execution state |
| Runner backends | `scripts/orchestration/deploy/runner.py` | Workspace-aware execution |
| Init orchestrator | `scripts/orchestration/deploy/init_node.py` | Node bootstrap |

## Execution Flow

| Step | Command | Input |
|------|---------|-------|
| Create bundle | `task bundle:create` | Generated artifacts |
| Check evidence | `task deploy:service-chain-evidence-check-bundle` | `BUNDLE=<id>` |
| Apply | `task deploy:service-chain-evidence-apply-bundle` | `BUNDLE=<id> ALLOW_APPLY=YES` |
| Init status | `task deploy:init-status` | — |

## Anti-Patterns

| Pattern | Why Wrong | Fix |
|---------|-----------|-----|
| Direct `generated/` execution | Bypasses bundle contract | Use `--bundle <id>` |
| Overstate hardware readiness | Init is hardware-sensitive | Require E2E evidence |
| Mutable bundle artifacts | Breaks immutability | State goes to deploy-state/ |

## Validation

```bash
task workflow:bundle
task deploy:init-status
# Runner/bundle targeted tests
```
