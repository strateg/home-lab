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
task validate:quality
task validate:v5
task validate:v5-layers
task build:v5
task validate:phase1-gate
task framework:strict
task ci:python-checks-core
task ci:local
```

v4 maintenance commands:

```powershell
task validate:v4
task build:v4
task build:phase1-bootstrap
task build:phase1-reconcile
task build:phase1-backlog
task build:phase4-sync-lock
task build:phase4-export
```

Project bootstrap (new repo + framework submodule):

```powershell
task project:init -- PROJECT_ROOT=D:/work/new-project PROJECT_ID=home-lab FRAMEWORK_SUBMODULE_URL=https://github.com/<org>/infra-topology-framework.git
```

`Makefile` is kept as a compatibility shim and delegates to `task` where possible.

Minimum supported `go-task` version: `3.45.4` (CI is pinned to the same version).

If `task` is not installed yet:

- Windows (`winget`): `winget install Task.Task`
- macOS (`brew`): `brew install go-task/tap/go-task`
- Linux (`snap`): `sudo snap install task --classic`
- Verify: `task --version`
