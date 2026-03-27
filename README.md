# home-lab

Root-layout repository for topology framework + project runtime.

## Runtime Policy

- `v5` lane is the default production lane.
- `v4` is maintenance-only and stored under `archive/v4` for parity/rollback reference.
- New development is performed only on root layout (`topology/`, `topology-tools/`, `projects/`, `tests/`).

## Repository Layout

- Active runtime/model: `topology/`, `topology-tools/`, `projects/`, `scripts/`, `tests/`, `taskfiles/`
- Generated artifacts: `generated/`, `build/`, `dist/`
- Legacy baseline for parity only: `archive/v4/`

Root `v4/` and root `v5/` directories are intentionally forbidden.

## Core Paths

- Project instances: `projects/<project>/instances/`
- Project secrets: `projects/<project>/secrets/`
- Project ansible overrides: `projects/<project>/ansible/inventory-overrides/`
- Generated outputs:
  - `generated/<project>/terraform/...`
  - `generated/<project>/ansible/...`
  - `generated/<project>/bootstrap/...`

## Quick Commands

```powershell
task validate:quality
task validate:v5
task validate:v5-layers
task validate:workspace-layout
task test
task test:parity-v4-v5
task build
task build:v5-docs
task ci:local
task ci:local-with-legacy
task framework:strict
task framework:cutover-readiness-quick
task framework:cutover-readiness
task acceptance:tests-all
task ansible:install-collections
task ansible:runtime
task ansible:syntax
task ansible:check-site
```

## V5 Deploy Workflow

1. Run strict and validation gates:
   ```powershell
   task framework:strict
   task validate:v5
   task framework:release-tests
   ```
2. Compile and generate artifacts:
   ```powershell
   python topology-tools/compile-topology.py --topology topology/topology.yaml --strict-model-lock --secrets-mode passthrough --artifacts-root generated
   ```
3. Validate infrastructure plans:
   ```powershell
   terraform -chdir=generated/home-lab/terraform/proxmox validate
   terraform -chdir=generated/home-lab/terraform/proxmox plan -refresh=false
   terraform -chdir=generated/home-lab/terraform/mikrotik validate
   terraform -chdir=generated/home-lab/terraform/mikrotik plan -refresh=false
   ```
4. Build and verify Ansible runtime inventory:
   ```powershell
   task ansible:runtime
   ansible-inventory -i generated/home-lab/ansible/runtime/production/hosts.yml --list
   task ansible:syntax
   task ansible:check-site
   ```
5. Final cutover gates:
   ```powershell
   task acceptance:tests-all
   task framework:cutover-readiness
   ```

Full operational procedures:

- `docs/runbooks/README.md`
- `docs/runbooks/DEPLOYMENT-PROCEDURES.md`
- `docs/runbooks/V5-E2E-DRY-RUN.md`
- `projects/home-lab/ansible/README.md`

## Project Bootstrap

- Submodule mode:
  - `task project:init -- PROJECT_ROOT=D:/work/new-project PROJECT_ID=home-lab FRAMEWORK_SUBMODULE_URL=https://github.com/<org>/infra-topology-framework.git`
- Distribution zip mode:
  - `task project:init-from-dist -- PROJECT_ROOT=D:/work/new-project PROJECT_ID=home-lab FRAMEWORK_DIST_ZIP=D:/artifacts/infra-topology-framework-1.0.8.zip FRAMEWORK_DIST_VERSION=1.0.8`

## Main Docs

- `adr/0080-unified-build-pipeline-stage-phase-and-plugin-data-bus.md`
- `adr/0080-analysis/IMPLEMENTATION-PLAN.md`
- `adr/plan/0078-cutover-checklist.md`
- `docs/framework/FRAMEWORK-V5.md`
- `docs/framework/OPERATOR-WORKFLOWS.md`
- `docs/framework/FRAMEWORK-RELEASE-GUIDE.md`
- `docs/runbooks/README.md`
- `docs/runbooks/V5-E2E-DRY-RUN.md`
- `README-РУССКИЙ.md`
- `topology-tools/docs/ENVIRONMENT-SETUP.md`
- `topology-tools/docs/MANUAL-ARTIFACT-BUILD.md`
