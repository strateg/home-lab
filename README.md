# home-lab

Repository is split into two migration lanes:

- `v5/` - default lane (Class -> Object -> Instance architecture)
- `v4/` - legacy maintenance lane (critical fixes and regression checks only)

Generated artifacts are versioned by lane:

- `v4-generated/`, `v4-build/`, `v4-dist/`
- `v5-generated/`, `v5-build/`, `v5-dist/`

v5 generator outputs are project-qualified:

- `v5-generated/<project>/terraform/...`
- `v5-generated/<project>/ansible/...`
- `v5-generated/<project>/bootstrap/...`

Project runtime inputs are stored under:

- `v5/projects/<project>/instances/`
- `v5/projects/<project>/secrets/`
- `v5/projects/<project>/ansible/inventory-overrides/`

Main documents:

- `adr/0062-modular-topology-architecture-consolidation.md`
- `adr/PLUGIN-RUNTIME-ADR-MAP.md`
- `adr/0075-framework-project-separation.md`
- `adr/0074-v5-generator-architecture.md`
- `docs/release-notes/2026-03-20-v5-framework-project-cutover.md`
- `docs/framework/FRAMEWORK-V5.md`
- `docs/framework/SUBMODULE-ROLL-OUT.md`
- `docs/runbooks/V5-E2E-DRY-RUN.md`
- `v4/README.md`
- `v5/topology-tools/docs/ENVIRONMENT-SETUP.md`
- `v5/topology-tools/docs/MANUAL-ARTIFACT-BUILD.md`

Quick commands:

```powershell
make validate-v5
make validate-v5-layers
make build-v5
make phase1-gate
```

v4 maintenance commands:

```powershell
make validate-v4
make build-v4
make phase1-bootstrap
make phase1-reconcile
make phase1-backlog
make phase4-sync-lock
make phase4-export
```
