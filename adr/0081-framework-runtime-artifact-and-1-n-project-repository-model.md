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

- v4 is archived in `archive/v4/`. v5 content is in the repository root (premature extraction from `v5/` prefix — development continues on this structure).
- v4 can still be built from `archive/v4/` for reference and parity checks.
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

Contents exclusive to this repository (NEVER included in framework artifact):

| Asset | Purpose |
|-------|---------|
| `adr/` | Architecture Decision Records |
| `tests/` | Framework test suites and fixtures |
| `acceptance-testing/` | TUC acceptance tests |
| `docs/` | Framework development documentation |
| `archive/` | v4 codebase for reference and parity |
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

Later levels extend earlier levels. ID conflicts within the same level are errors. Cross-level ID collisions are resolved by level precedence (project wins for project-scoped execution).

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
1. Update framework dependency (submodule update or new artifact)
2. Regenerate lock: generate-framework-lock.py
3. Run pipeline in strict mode — verify no regressions
4. Commit updated lock + regenerated artifacts
```

---

## Consequences

Positive:

1. Clean 1:N scaling: one framework release, N independent project repositories.
2. Minimal runtime dependency: project CI only needs framework artifact + project data.
3. Clear lifecycle boundary: framework engineering (with AI, tests, ADRs) is decoupled from project operation.
4. v4 remains accessible in `archive/v4/` for parity checks and reference.

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

## Structural Note

v4 is archived in `archive/v4/`. v5 content was moved from `v5/` prefix to repository root (premature extraction). Development continues on the current root-level structure. Parity checks against v4 can still be executed from `archive/v4/`. v4 build pipeline MUST remain operational for regression validation.

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
