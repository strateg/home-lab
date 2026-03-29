# ADR 0081: Framework Runtime Artifact and 1:N Project Repository Model

- Status: Accepted
- Date: 2026-03-29
- Revised: 2026-03-29
- Depends on: ADR 0063, ADR 0065, ADR 0069, ADR 0071, ADR 0074, ADR 0075, ADR 0076, ADR 0078, ADR 0080
- Related plans: `adr/plan/0081-framework-artifact-first-execution-plan.md`

---

## Context

ADR 0075 established framework/project boundary inside one repository.
ADR 0076 introduced distribution + lock contracts and completed Stage 2 in submodule-first mode.
ADR 0080 finalized six-stage lifecycle and six plugin families.

The current repository (`home-lab`) serves a dual role:

1. **Framework development source** — AI-assisted development of the topology framework, including tests, ADRs, architecture documentation, experiments, and CI tooling.
2. **Home-lab project host** — the `home-lab` project data is co-located for development convenience.

The target architecture is 1:N: one framework is consumed as a versioned artifact by N independent project repositories. Each project repository, combined with a framework artifact, MUST be self-sufficient for deterministic generation of deployment artifacts (Terraform, Ansible, bootstrap, docs).

### Architecture Principles

1. **Framework is runtime-only in artifact form.** The framework artifact contains only what a project CI needs to run the `discover → compile → validate → generate → assemble → build` pipeline. No tests, no ADRs, no development documentation.
2. **Projects are independently deployable.** A project repository + framework dependency = all inputs needed for artifact generation.
3. **Framework development stays in this repository.** Tests, ADR history, architecture experiments, AI-agent instructions remain here and are never shipped in the artifact.
4. **Plugin layering is strict.** Framework provides base plugins. Class/object modules may provide plugins. Projects may provide plugins. Discovery order is deterministic: kernel → framework → class → object → project.

### Current State

- Framework/project separation is implemented (ADR 0075).
- Submodule-first consumption is operational (ADR 0076 Stage 2).
- Artifact-first consumption is defined but not yet canonical.
- Project-level plugin families are defined in contract but not yet enforced in runtime.

---

## Decision

Adopt **artifact-first framework consumption** as canonical 1:N architecture.

### 1. Repository Roles (Normative)

#### 1.1 Framework Source Repository (this repo: `home-lab`)

This repository is the single source of truth for framework development.

The repository also contains a **co-located test project** (`projects/home-lab/`) so that framework and project development happen in one place. The co-located project uses the same compilation scripts and produces the same artifacts as a standalone project repository would. This enables:

1. **End-to-end validation** — framework changes are immediately tested against real project data.
2. **Single development context** — AI-assisted development has full visibility into framework + project interaction.
3. **Reference implementation** — the co-located project serves as the canonical example of how a project consumes the framework.

The co-located project is built with the same `compile-topology.py` and the same plugin pipeline. The only difference from a standalone project is path resolution: in monorepo mode, `topology.yaml` points to framework paths without a mount prefix (`topology/class-modules`), while in standalone mode it points through the framework mount (`framework/topology/class-modules`).
`projects/home-lab/` remains a required integration fixture for validating that framework changes do not break standalone-project execution semantics.

Contents exclusive to this repository (NEVER included in framework artifact):

| Asset | Purpose |
|-------|---------|
| `adr/` | Architecture Decision Records |
| `tests/` | Framework test suites and fixtures |
| `acceptance-testing/` | TUC acceptance tests |
| `docs/` | Framework development documentation |
| `archive/` | Historical codebase archive |
| `scripts/` | Development orchestration scripts |
| `.claude/`, `.codex/`, `AGENTS.md`, `CLAUDE.md` | AI-agent instructions |
| `Taskfile.yml`, `taskfiles/` | Development task runner |
| `pyproject.toml`, `requirements-dev.txt` | Development dependencies |
| `projects/` | Co-located project data (for development convenience) |
| `configs/` | Device configurations |
| `Заметки/` | Working notes |

#### 1.2 Project Repositories (independent, one per deployment)

Each project repository is an independent Git repository that consumes the framework as a versioned dependency.

### 2. Framework Runtime Artifact Contract (Normative)

Framework release artifact MUST contain **only** runtime functionality needed by consuming projects.

#### 2.1 Required Artifact Contents

```
<framework-artifact>/
├── framework.yaml                      # Framework manifest + distribution spec
├── topology/
│   ├── class-modules/                  # All class definitions
│   │   ├── compute/
│   │   ├── network/
│   │   ├── observability/
│   │   ├── operations/
│   │   ├── power/
│   │   ├── router/
│   │   ├── service/
│   │   ├── software/
│   │   └── storage/
│   ├── object-modules/                 # All object templates
│   │   ├── _shared/
│   │   ├── cloud/
│   │   ├── glinet/
│   │   ├── mikrotik/
│   │   ├── network/
│   │   ├── observability/
│   │   ├── operations/
│   │   ├── orangepi/
│   │   ├── power/
│   │   ├── proxmox/
│   │   ├── service/
│   │   ├── software/
│   │   └── storage/
│   ├── layer-contract.yaml             # 8-layer OSI-like model
│   ├── model.lock.yaml                 # Class/object version lock
│   └── profile-map.yaml                # Runtime profiles
└── topology-tools/                     # Complete runtime toolchain
    ├── kernel/                         # Plugin microkernel
    ├── plugins/                        # Framework-level plugins + manifest
    │   ├── plugins.yaml                # Base plugin registry
    │   ├── compilers/
    │   ├── discoverers/
    │   ├── validators/
    │   └── generators/
    ├── schemas/                        # JSON Schema definitions
    ├── templates/                      # Jinja2 generation templates
    ├── data/                           # Error catalogs, static data
    ├── compile-topology.py             # Main compiler entrypoint
    ├── generate-framework-lock.py      # Lock generation
    ├── verify-framework-lock.py        # Lock verification
    ├── build-framework-distribution.py # Self-build capability
    ├── compiler_runtime.py             # Runtime orchestration
    ├── compiler_contract.py            # Manifest/model validation
    ├── compiler_reporting.py           # Diagnostics output
    ├── framework_lock.py               # Lock module
    ├── plugin_manifest_discovery.py    # Plugin discovery chain
    └── [other runtime entrypoints]     # assemble, bootstrap, etc.
```

#### 2.2 Artifact Exclusions (Normative)

The framework artifact MUST NOT include:

1. Framework tests (`tests/`, `acceptance-testing/`)
2. ADRs and architecture documentation (`adr/`)
3. Development documentation (`docs/` — except operator runtime references if explicitly packaged)
4. Project data (`projects/`)
5. Archived code (`archive/`)
6. Development tooling (`Taskfile.yml`, `taskfiles/`, `scripts/`, `pyproject.toml`, `requirements-dev.txt`)
7. AI-agent configuration (`.claude/`, `.codex/`, `AGENTS.md`, `CLAUDE.md`)
8. IDE and CI configuration (`.github/`, `.idea/`, `.pre-commit-config.yaml`)
9. Generated outputs (`generated/`, `build/`, `dist/`)
10. Python bytecode (`__pycache__/`, `*.pyc`, `*.pyo`)

This exclusion list is enforced by `topology/framework.yaml` distribution spec and verified by artifact content contract tests.

### 3. Project Repository Contract (Normative)

#### 3.1 Project Layout

```
<project-repo>/
├── topology.yaml                       # Root manifest (points to framework)
├── project.yaml                        # Project manifest + compatibility
├── framework.lock.yaml                 # Pinned framework version + integrity
├── framework/                          # Framework artifact (submodule or extracted)
│   └── ...                             # Contents per §2.1
├── topology/
│   └── instances/                      # Project-specific instance data
│       ├── L0-meta/
│       ├── L1-foundation/
│       ├── L2-network/
│       ├── L3-data/
│       ├── L4-platform/
│       ├── L5-application/
│       ├── L6-observability/
│       └── L7-operations/
├── plugins/                            # Project-specific plugins
│   ├── discoverers/
│   ├── compilers/
│   ├── validators/
│   ├── generators/
│   ├── assemblers/
│   └── builders/
├── secrets/                            # SOPS-encrypted secrets
├── overrides/                          # Optional runtime overrides
├── generated/                          # Generated output artifacts
│   ├── terraform/
│   ├── ansible/
│   ├── bootstrap/
│   └── docs/
└── Taskfile.yml                        # Project-level task runner (optional)
```

#### 3.2 Self-Sufficiency Principle

A project repository combined with its framework dependency MUST be sufficient to execute the complete pipeline:

```
discover → compile → validate → generate → assemble → build
```

No external knowledge, no framework source repo access, no AI-agent context required for artifact generation.

#### 3.3 Project Plugin Root (Normative)

Projects MAY define plugins in `<project-root>/plugins/<family>/`. Project plugins extend (but do not override) framework plugins.

Six plugin families with strict stage affinity:

| Stage | Plugin Family | Project Use Case |
|-------|---------------|------------------|
| `discover` | `discoverers` | Project-specific hardware discovery, inventory enrichment |
| `compile` | `compilers` | Custom compilation transforms for project entities |
| `validate` | `validators` | Project-specific validation rules (naming, policy) |
| `generate` | `generators` | Custom output formats, project-specific Terraform modules |
| `assemble` | `assemblers` | Project-specific assembly (runtime inventory, secrets injection) |
| `build` | `builders` | Project-specific packaging (deployment bundles) |

#### 3.4 Plugin Discovery Order (Normative)

Plugin discovery follows a strict deterministic merge chain:

1. **Kernel** — built-in plugin base contracts
2. **Framework base** — `topology-tools/plugins/plugins.yaml`
3. **Class modules** — `topology/class-modules/<class>/plugins.yaml` (if present)
4. **Object modules** — `topology/object-modules/<object>/plugins.yaml` (if present)
5. **Project** — `<project-root>/plugins/plugins.yaml` (if present)

Later levels extend earlier levels through additive registration only. To keep determinism and avoid hidden behavior changes, plugin IDs MUST be globally unique across all loaded manifests. Duplicate IDs at any level are hard errors.

### 3.5 Practical Integration: How Framework Connects to Project (Informative)

The key architectural question is: **project does NOT flatten classes/objects/instances into one root.** Classes and objects belong to the framework; instances belong to the project. They are connected via `topology.yaml` path declarations.

#### Layout Comparison

**Monorepo mode** (this repository — framework development):

```
home-lab/                               # repo_root
├── topology/                           # Framework contracts (NO prefix needed)
│   ├── class-modules/                  # ← framework.class_modules_root
│   ├── object-modules/                 # ← framework.object_modules_root
│   ├── topology.yaml                   # Root manifest
│   └── ...
├── topology-tools/                     # Compiler toolchain
│   └── compile-topology.py             # Entrypoint
├── projects/home-lab/                  # ← project_root
│   ├── project.yaml
│   ├── topology/instances/             # ← project.instances_root (relative to project_root)
│   ├── secrets/                        # ← project.secrets_root
│   └── framework.lock.yaml
└── generated/home-lab/                 # Output artifacts
```

```yaml
# topology/topology.yaml (monorepo)
framework:
  class_modules_root: topology/class-modules       # relative to repo_root
  object_modules_root: topology/object-modules     # relative to repo_root
project:
  active: home-lab
  projects_root: projects                          # project_root = repo_root/projects/home-lab
```

**Standalone project mode** (project repo with framework dependency):

```
my-infra/                               # repo_root = project_root
├── framework/                          # Framework artifact (submodule or extracted zip)
│   ├── topology/
│   │   ├── class-modules/              # ← framework.class_modules_root
│   │   ├── object-modules/             # ← framework.object_modules_root
│   │   └── ...
│   └── topology-tools/                 # Compiler toolchain
│       └── compile-topology.py         # Same entrypoint
├── topology.yaml                       # Root manifest (at project root)
├── project.yaml
├── framework.lock.yaml
├── topology/
│   └── instances/                      # ← project.instances_root
│       ├── L0-meta/
│       ├── L1-foundation/
│       └── ...
├── plugins/                            # Project-specific plugins
├── secrets/
└── generated/                          # Output artifacts
```

```yaml
# topology.yaml (standalone project)
framework:
  class_modules_root: framework/topology/class-modules   # through framework/ mount
  object_modules_root: framework/topology/object-modules  # through framework/ mount
project:
  active: my-infra
  projects_root: .                                        # project IS the repo root
```

#### Path Resolution Mechanics

The compiler resolves paths through two separate mechanisms:

1. **Framework paths** (classes, objects, capabilities, layer contract) — resolved relative to `repo_root` via `topology.yaml:framework.*` declarations.
2. **Project paths** (instances, secrets) — resolved relative to `project_root` via `project.yaml:instances_root` and `secrets_root`.

This dual-root resolution enables the same `compile-topology.py` to work in both modes without code changes:

```bash
# Monorepo mode (framework development)
python topology-tools/compile-topology.py \
  --repo-root . \
  --topology topology/topology.yaml

# Standalone project mode (same script, different topology.yaml)
python framework/topology-tools/compile-topology.py \
  --repo-root . \
  --topology ./topology.yaml
```

The compiler has built-in layout detection:
- `resolve_topology_path()` falls back from `topology/topology.yaml` (monorepo) to `topology.yaml` (standalone) automatically.
- `default_framework_manifest_path()` detects both `topology/framework.yaml` (monorepo) and `framework.yaml` (extracted artifact).

### 3.6 Topology Execution Environment Compatibility (Normative)

The topology execution environment for standalone projects MUST preserve the same operational script contract as monorepo development.

Required compatibility rules:

1. The same runtime entrypoints are used in both modes (`compile-topology.py`, `generate-framework-lock.py`, `verify-framework-lock.py`).
2. In standalone repositories, scripts are executed from framework mount (`framework/topology-tools/...`) with project-local manifests.
3. Project bootstrap tooling (`bootstrap-project-repo.py` / `init-project-repo.py`) MUST generate runnable command templates (Taskfile/workflow notes) that reference mounted framework scripts.
4. CI validation in project repositories MUST call mounted framework scripts directly, not scripts from framework source repository.

Practical command mapping:

| Function | Monorepo (`home-lab`) | Standalone project (`my-infra`) |
|----------|------------------------|----------------------------------|
| Compile | `python topology-tools/compile-topology.py --repo-root . --topology topology/topology.yaml` | `python framework/topology-tools/compile-topology.py --repo-root . --topology ./topology.yaml` |
| Generate lock | `python topology-tools/generate-framework-lock.py --topology topology/topology.yaml --force` | `python framework/topology-tools/generate-framework-lock.py --repo-root . --project-root . --project-manifest ./project.yaml --framework-root ./framework --framework-manifest ./framework/framework.yaml --lock-file ./framework.lock.yaml --force` |
| Verify lock | `python topology-tools/verify-framework-lock.py --strict` | `python framework/topology-tools/verify-framework-lock.py --repo-root . --project-root . --project-manifest ./project.yaml --framework-root ./framework --framework-manifest ./framework/framework.yaml --lock-file ./framework.lock.yaml --strict` |

#### What Belongs Where

| Asset | Owner | Location in Monorepo | Location in Standalone Project |
|-------|-------|---------------------|-------------------------------|
| Class definitions | Framework | `topology/class-modules/` | `framework/topology/class-modules/` |
| Object templates | Framework | `topology/object-modules/` | `framework/topology/object-modules/` |
| Layer contract | Framework | `topology/layer-contract.yaml` | `framework/topology/layer-contract.yaml` |
| Model lock | Framework | `topology/model.lock.yaml` | `framework/topology/model.lock.yaml` |
| Base plugins | Framework | `topology-tools/plugins/` | `framework/topology-tools/plugins/` |
| Compiler toolchain | Framework | `topology-tools/` | `framework/topology-tools/` |
| Instance data | Project | `projects/<id>/topology/instances/` | `topology/instances/` |
| Secrets | Project | `projects/<id>/secrets/` | `secrets/` |
| Project plugins | Project | `projects/<id>/plugins/` | `plugins/` |
| Framework lock | Project | `projects/<id>/framework.lock.yaml` | `framework.lock.yaml` |
| Generated artifacts | Project | `generated/<id>/` | `generated/` |

### 4. Dependency and Trust Contract (Normative)

#### 4.1 Lock Contract

Each project MUST maintain `framework.lock.yaml` containing:

| Field | Description |
|-------|-------------|
| `framework.version` | SemVer version of pinned framework |
| `framework.source` | `git` or `package` |
| `framework.revision` | Immutable git commit SHA or artifact digest |
| `framework.integrity` | SHA-256 hash of framework content |
| `locked_at` | ISO 8601 timestamp of lock generation |

#### 4.2 Verification Gates

Compiler MUST verify lock consistency before compile in strict mode.

| Check | Error Code | Description |
|-------|------------|-------------|
| Lock file missing | `E7822` | `framework.lock.yaml` absent in strict mode |
| Revision mismatch | `E7823` | Actual framework content differs from locked revision |
| Integrity mismatch | `E7824` | SHA-256 hash does not match |
| Version compatibility | `E7811` | Framework version below `project_min_framework_version` |
| Schema compatibility | `E7812` | Project schema outside `supported_project_schema_range` |

#### 4.3 Trust Verification (Package Mode)

For package-mode consumption (production release promotion), additional checks apply:

| Check | Error Code | Description |
|-------|------------|-------------|
| Signature invalid | `E7825` | Cryptographic signature verification failed |
| No provenance | `E7826` | Provenance attestation missing |
| SBOM missing | `E7828` | Software Bill of Materials not present |

Trust verification is phased: integrity checks (§4.2) are mandatory now; cryptographic trust (§4.3) is required for production release promotion and enforced incrementally.

### 5. Consumption Modes (Normative)

| Mode | Context | Lock Source | Trust Level |
|------|---------|-------------|-------------|
| **Package artifact** (primary) | Production CI, release builds | `package` | Full (integrity + signature + provenance) |
| **Git submodule** (secondary) | Development, rehearsal | `git` | Integrity (commit SHA + content hash) |
| **Local path** (dev-only) | Framework development | N/A | None (forbidden for release promotion) |

### 5.1 Cognitive Load Policy for Dependency Integration (Normative)

To minimize developer cognitive load, the dependency model is standardized to one primary path.

1. Canonical developer and CI path is **artifact-first** (`project:init-from-dist` style bootstrap).
2. Submodule flow is retained only as **temporary legacy/rollback compatibility** during Phase 13 stabilization.
3. Submodule flow MUST NOT be the default path in documentation, templates, or onboarding.
4. After Phase 13 stabilization window, submodule flow is deprecated and removed from primary project workflows.
5. Upgrade UX target is one deterministic flow:
   - update framework artifact in `./framework`,
   - regenerate `framework.lock.yaml`,
   - run strict verify + compile,
   - commit dependency + lock + approved generated diffs.

### 6. Development Workflow (Informative)

#### 6.1 Framework Development (this repository)

```
1. Edit framework code (classes, objects, plugins, toolchain)
2. Run framework tests (pytest, acceptance tests)
3. Validate with co-located home-lab project (local-path mode)
4. Commit, push, CI validates
5. Tag release → build framework artifact → publish
```

AI-assisted development tooling (`.claude/`, `.codex/`, `AGENTS.md`) guides framework evolution. These assets never leave this repository.

#### 6.2 Project Development (project repository)

```
1. Pin framework version (framework.lock.yaml)
2. Define instances (topology/instances/L0-L7)
3. Add project plugins if needed (plugins/<family>/)
4. Run pipeline: discover → compile → validate → generate → assemble → build
5. Apply generated artifacts (terraform apply, ansible-playbook)
```

#### 6.3 Framework Upgrade in Project

```
1. Update framework dependency:
   - package mode: fetch/install new framework artifact version into `./framework`
   - submodule mode: move submodule pointer to required tag/commit
2. Regenerate lock with mounted framework:
   - `python framework/topology-tools/generate-framework-lock.py --repo-root . --project-root . --project-manifest ./project.yaml --framework-root ./framework --framework-manifest ./framework/framework.yaml --lock-file ./framework.lock.yaml --force`
3. Run strict verification and compile:
   - `python framework/topology-tools/verify-framework-lock.py --repo-root . --project-root . --project-manifest ./project.yaml --framework-root ./framework --framework-manifest ./framework/framework.yaml --lock-file ./framework.lock.yaml --strict`
   - `python framework/topology-tools/compile-topology.py --repo-root . --topology ./topology.yaml --strict-model-lock --secrets-mode passthrough`
4. Re-run project CI gates (validate/generate/assemble/build).
5. Commit dependency update + `framework.lock.yaml` + approved generated diffs in one changeset.
```

Version update policy:

1. No implicit framework updates in project CI.
2. Framework version bump is explicit, locked, and reviewable.
3. Rollback is performed by restoring previous framework dependency revision and corresponding `framework.lock.yaml`.

#### 6.4 Framework Upgrade Checklist (Operational)

Use this checklist in project repositories:

1. Update dependency in `./framework` (artifact refresh or submodule pointer).
2. Regenerate lock:
   - `python framework/topology-tools/generate-framework-lock.py --repo-root . --project-root . --project-manifest ./project.yaml --framework-root ./framework --framework-manifest ./framework/framework.yaml --lock-file ./framework.lock.yaml --force`
3. Verify lock (strict):
   - `python framework/topology-tools/verify-framework-lock.py --repo-root . --project-root . --project-manifest ./project.yaml --framework-root ./framework --framework-manifest ./framework/framework.yaml --lock-file ./framework.lock.yaml --strict`
4. Compile (strict model lock):
   - `python framework/topology-tools/compile-topology.py --repo-root . --topology ./topology.yaml --strict-model-lock --secrets-mode passthrough`
5. Run project CI gates and review generated diffs.
6. Commit in one change:
   - framework dependency update,
   - `framework.lock.yaml`,
   - approved generated artifacts.
7. Rollback procedure:
   - restore previous framework dependency revision,
   - restore matching `framework.lock.yaml`,
   - re-run steps 3-4.

---

## Consequences

Positive:

1. Clean 1:N scaling: one framework release, N independent project repositories.
2. Minimal runtime dependency: project CI only needs framework artifact + project data.
3. Clear lifecycle boundary: framework engineering (with AI, tests, ADRs) is decoupled from project operation.
4. Framework artifact is self-contained and has no historical dependencies.

Trade-offs:

1. Framework release discipline required (versioning, artifact build, trust metadata).
2. Project plugin root and discovery chain need runtime implementation to match this contract.
3. Stricter contracts reduce tolerance for ad-hoc local workflows.

---

## Relationship to ADR 0075 and ADR 0076

| ADR | Scope | Status |
|-----|-------|--------|
| **0075** | Monorepo framework/project boundary | Completed — established `topology/` vs `projects/<id>/` separation |
| **0076** | Distribution contracts + extraction tooling | Completed (submodule-first) — lock/verify/extract tools operational |
| **0081** (this) | 1:N architecture, artifact-first as canonical, runtime boundary | Accepted — extends 0075+0076 with explicit runtime artifact contract |

ADR 0075 answers "where is the boundary?" — ADR 0076 answers "how to distribute?" — ADR 0081 answers "what exactly ships and how do projects consume it?"

---

---

## References

1. `adr/0075-framework-project-separation.md` — monorepo boundary contract
2. `adr/0076-framework-distribution-and-multi-repository-extraction.md` — distribution and extraction
3. `adr/0080-unified-build-pipeline-stage-phase-and-plugin-data-bus.md` — six-stage lifecycle
4. `adr/plan/0081-framework-artifact-first-execution-plan.md` — execution plan
5. `topology/framework.yaml` — framework distribution spec (source of truth for artifact contents)
6. `topology-tools/build-framework-distribution.py` — artifact build tool
7. `topology-tools/generate-framework-lock.py` — lock generation
8. `topology-tools/verify-framework-lock.py` — lock verification
9. `topology-tools/bootstrap-project-repo.py` — project repository scaffolding
10. `topology-tools/extract-framework-history.py` — history-preserving extraction
