# AI Rule Pack: Deploy Domain

Load when changing:

- `scripts/orchestration/deploy/**`
- `taskfiles/deploy.yml`
- `taskfiles/product.yml`
- deploy schemas
- node initialization or deploy runner behavior

## Rules

1. Deploy bundle is the immutable execution input.
2. Deploy operations must execute through workspace-aware `DeployRunner` backends.
3. Active execution flows should use explicit `--bundle <bundle_id>` inputs.
4. Mutable deploy state belongs under `.work/deploy-state/<project>/`.
5. Bundle artifacts belong under `.work/deploy/bundles/<bundle_id>/`.
6. Keep dev plane cross-platform and deploy plane Linux-backed.
7. ADR0083 initialization remains hardware-sensitive; do not overstate hardware readiness without E2E evidence.

## Validation

- runner/bundle targeted tests
- `task workflow:bundle`
- `task deploy:init-status` for initialization state work
- deploy smoke tasks when changing backend behavior

## ADR Sources

- ADR0051 (Ansible runtime and secrets)
- ADR0052 (Build pipeline after Ansible)
- ADR0056 (Native execution workspace)
- ADR0057 (MikroTik bootstrap)
- ADR0083 (Unified node initialization)
- ADR0084 (Cross-platform dev plane)
- ADR0085 (Deploy bundle and runner)
- ADR0090 (SOHO operator lifecycle)
- ADR0091 (SOHO readiness evidence)
