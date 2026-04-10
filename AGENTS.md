# AGENTS.md

## Home Lab AI Agent Guide

This document provides essential, actionable guidance for AI coding agents working in this repository. It summarizes the architecture, workflows, and conventions that are unique to this project. **Read this before making any code or topology changes.**

**Universal rulebook:** for compact, ADR-derived implementation rules shared by Claude Code, Codex, Copilot, and other AI agents, read `docs/ai/AGENT-RULEBOOK.md` first and use `docs/ai/ADR-RULE-MAP.yaml` to select scoped rule packs. `AGENTS.md` is an adapter/bootloader, not a separate architectural source of truth.

---

### 1. Big Picture Architecture
- **Infrastructure-as-Data**: The system models infrastructure using a strict `Class -> Object -> Instance` hierarchy (see `topology/topology.yaml`).
- **Plugin-based Compiler**: All code generation, validation, and transformation is handled by plugins, organized by stage: `discover`, `compile`, `validate`, `generate`, `assemble`, `build`.
- **Plugin Runtime Contract (ADR0086)**: Runtime safety is enforced by stage/phase + manifest contracts + discovery order tests, not by strict 4-level visibility ACL.
- **Source of Truth**: All infrastructure definitions live in `topology/topology.yaml`, `topology/class-modules/`, `topology/object-modules/`, and `projects/home-lab/topology/instances/`.
- **Generated Outputs**: All generated files (Terraform, Ansible, docs) are written to `generated/<project>/`. Never edit these directly.

---

### 2. Critical Developer Workflows
- **Validation & Compilation**: Use the lane orchestrator and compiler scripts:
  - `.venv/bin/python scripts/orchestration/lane.py validate-v5`
  - `.venv/bin/python topology-tools/compile-topology.py`
- **Build & Test**: Use `task` commands for all build/test flows (see `README.md`):
  - `task validate:default`, `task build`, `task test`, `task acceptance:tests-all`
  - For full deploy: see `docs/runbooks/V5-E2E-DRY-RUN.md`
- **Terraform/Ansible**: Validate and plan using generated outputs only. Example:
  - `terraform -chdir=generated/home-lab/terraform/proxmox validate`
  - `ansible-inventory -i generated/home-lab/ansible/runtime/production/hosts.yml --list`
- **Secrets**: Managed with SOPS/age in `projects/home-lab/secrets/`. Never commit unencrypted secrets.

---

### 3. Project-Specific Conventions
- **Do not edit generated files** in `generated/`—regenerate by editing topology and running the compiler.
- **Plugin contracts are mandatory**: obey stage affinity, dependency/consumption links, and framework->class->object->project discovery order.
- **All architectural decisions** must be documented in `adr/` (see ADR policy in `.github/copilot-instructions.md`).
- **Directory structure is enforced**: Do not create root `v4/` or `v5/` directories; legacy code is in `archive/v4/`.
- **Validation is required after any change**: Always run validation scripts after editing topology or code.

---

### 4. Integration Points & Patterns
- **Plugin Families**: All plugin code lives in `topology-tools/plugins/` under subfolders for each stage (e.g., `compilers/`, `generators/`).
- **Templates**: Jinja2 templates for code generation are in `topology-tools/templates/`.
- **Orchestration**: All workflow entrypoints are in `scripts/orchestration/`.
- **Tests**: All tests are in `tests/`. Use `pytest` for test execution.
- **ADR Analysis**: Deep implementation plans and gap analyses are in `adr/NNNN-analysis/`.

---

### 5. Examples
- **Add a new instance**: Edit `projects/home-lab/topology/instances/`, then run validation and compilation.
- **Add a plugin**: Place it in the correct stage family under `topology-tools/plugins/` and wire manifest contracts (`depends_on`, `consumes`, `produces`) explicitly.
- **Update a class/object**: Edit YAML in `topology/class-modules/` or `topology/object-modules/`, then recompile.

---

### 6. References
- `.github/copilot-instructions.md`, `CLAUDE.md` — AI agent rules and plugin contract
- `README.md`, `README-РУССКИЙ.md` — project overview and workflows
- `docs/framework/FRAMEWORK-V5.md` — framework/project separation
- `docs/runbooks/` — operational runbooks and deployment procedures
- `adr/` — architecture decisions and analysis

**When in doubt, check the runbooks and ADRs before proceeding.**
