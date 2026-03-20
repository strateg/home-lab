# ADR 0075: Framework and Project Separation in V5 Topology

**Date:** 2026-03-20
**Status:** Proposed
**Depends on:** ADR 0062, ADR 0064, ADR 0071, ADR 0074
**Affects:** `v5/topology/`, `v5/topology/instances/`, toolchain paths, repository structure

---

## Context

The v5 topology system implements a `Class -> Object -> Instance` model (ADR 0062) with:

- **Classes**: Universal definitions with properties and capability contracts
- **Objects**: Concrete profiles/variants implementing class contracts
- **Instances**: Deployed state referencing objects

Currently, all three tiers live under `v5/topology/`:

```
v5/topology/
├── class-modules/           # Universal definitions
├── object-modules/          # Reusable profiles (vendor-specific, service templates)
├── instances/               # Deployed state (home-lab specific)
│   └── <layer-bucket>/<group>/<instance>.yaml
├── layer-contract.yaml
├── model.lock.yaml
├── profile-map.yaml
└── topology.yaml
```

### Problem Statement

1. **Instances are project-specific**: The `instances/` directory contains deployment state for a single project (home-lab). The same class/object framework could describe different configurations.

2. **No multi-project support**: Cannot model alternative topologies (test-bench, minimal-router) without duplicating or mixing instance data.

3. **Framework reusability blocked**: Classes and objects are potentially reusable across projects, but there is no clear boundary marking what is framework vs what is project.

4. **Testing isolation**: Integration tests need isolated instance sets without polluting production data.

### Considered Variants

#### Variant A: Projects inside topology

```
v5/topology/
├── class-modules/
├── object-modules/
├── layer-contract.yaml
└── projects/
    ├── home-lab/
    │   ├── project.yaml
    │   └── instances/
    └── test-bench/
```

**Assessment**: Mixes framework with project data under single root. Semantic ambiguity remains.

#### Variant B: Framework + Projects at same level

```
v5/
├── topology/                # Framework
│   ├── class-modules/
│   ├── object-modules/
│   └── layer-contract.yaml
└── projects/
    ├── home-lab/
    │   ├── project.yaml
    │   ├── instances/
    │   └── overrides/
    └── test-bench/
```

**Assessment**: Clean conceptual separation. Migration required but paths mostly preserved.

#### Variant C: Inventory overlay (Ansible-style)

```
v5/topology/
├── class-modules/
├── object-modules/
├── instances/
│   ├── _shared/
│   └── _project/ -> symlink
└── inventories/
    ├── home-lab/
    └── test-bench/
```

**Assessment**: Symlinks violate determinism (ADR 0074 D2) and cross-platform compatibility. Rejected.

---

## Decision

Adopt **Variant B** with refinements to minimize migration disruption, designed for eventual extraction into separate repositories.

### End State Vision: Multi-Repository Architecture

The ultimate goal is complete separation where:

1. **Framework** lives in its own repository (e.g., `infra-topology-framework`)
2. **Each project** lives in its own repository (e.g., `home-lab-project`)
3. **Framework is a dependency** of each project, versioned and pinned

```
┌─────────────────────────────────────────────────────────────────┐
│                    infra-topology-framework                      │
│                    (separate repository)                         │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  class-modules/     # Universal class definitions       │    │
│  │  object-modules/    # Reusable object profiles          │    │
│  │  topology-tools/    # Compiler, validators, generators  │    │
│  │  layer-contract.yaml                                    │    │
│  │  framework.yaml     # Framework manifest + version      │    │
│  └─────────────────────────────────────────────────────────┘    │
│                              ▲                                   │
│                              │ dependency                        │
└──────────────────────────────┼──────────────────────────────────┘
                               │
        ┌──────────────────────┼──────────────────────┐
        │                      │                      │
        ▼                      ▼                      ▼
┌───────────────┐    ┌───────────────┐    ┌───────────────┐
│  home-lab     │    │  test-bench   │    │  client-xyz   │
│  (project)    │    │  (project)    │    │  (project)    │
│               │    │               │    │               │
│  project.yaml │    │  project.yaml │    │  project.yaml │
│  instances/   │    │  instances/   │    │  instances/   │
│  overrides/   │    │  overrides/   │    │  overrides/   │
│  generated/   │    │  generated/   │    │  generated/   │
└───────────────┘    └───────────────┘    └───────────────┘
```

### Framework Repository Structure

```
infra-topology-framework/
├── class-modules/
│   ├── compute/
│   ├── network/
│   ├── power/
│   ├── router/
│   ├── software/
│   └── storage/
├── object-modules/
│   ├── cloud/
│   ├── glinet/
│   ├── mikrotik/
│   ├── orangepi/
│   ├── proxmox/
│   └── software/
├── topology-tools/
│   ├── plugins/
│   │   ├── compilers/
│   │   ├── generators/
│   │   └── validators/
│   ├── compile.py
│   ├── topology_loader.py
│   └── plugins.yaml
├── schemas/
│   ├── class.schema.json
│   ├── object.schema.json
│   ├── instance.schema.json
│   └── project.schema.json
├── layer-contract.yaml
├── framework.yaml              # Framework manifest
├── pyproject.toml              # Python package definition
└── README.md
```

### Project Repository Structure

```
home-lab-project/
├── .framework/                 # Framework dependency (git submodule or vendored)
│   └── -> infra-topology-framework@v1.2.0
├── instances/
│   ├── L1-foundation/
│   │   ├── devices/
│   │   ├── firmware/
│   │   ├── physical-links/
│   │   └── power/
│   ├── L2-network/
│   │   ├── network/
│   │   └── data-channels/
│   └── ...
├── overrides/                  # Project-specific object overrides
│   └── obj.mikrotik.chateau_lte7_ax.yaml
├── generated/                  # Compiled output (gitignored or tracked)
│   ├── terraform/
│   ├── ansible/
│   └── bootstrap/
├── local/                      # Secrets, tfvars (gitignored)
├── project.yaml                # Project manifest
├── framework.lock.yaml         # Pinned framework version + integrity
└── README.md
```

### Dependency Management Options

#### Option 1: Git Submodule (Recommended for Phase 1)

```bash
# In project repository
git submodule add https://github.com/user/infra-topology-framework.git .framework
git submodule update --init
```

```yaml
# project.yaml
schema_version: 2
project: home-lab

framework:
  type: submodule
  path: .framework
  version: v1.2.0  # Tag/commit to pin
```

**Pros**: Simple, works offline, explicit version in git history
**Cons**: Submodule workflow complexity, manual updates

#### Option 2: Python Package (Recommended for Phase 2)

```bash
pip install infra-topology-framework==1.2.0
# or
pip install git+https://github.com/user/infra-topology-framework.git@v1.2.0
```

```yaml
# project.yaml
schema_version: 2
project: home-lab

framework:
  type: package
  name: infra-topology-framework
  version: ">=1.2.0,<2.0.0"
```

```toml
# pyproject.toml in project
[project]
dependencies = [
    "infra-topology-framework>=1.2.0,<2.0.0",
]
```

**Pros**: Standard Python tooling, semver support, transitive dependencies
**Cons**: Requires package publishing infrastructure

#### Option 3: HTTP/Archive Fetch

```yaml
# project.yaml
framework:
  type: archive
  url: https://releases.example.com/framework/v1.2.0.tar.gz
  sha256: abc123...
  extract_to: .framework
```

**Pros**: No git/pip required, fully hermetic
**Cons**: Manual integrity verification, no incremental updates

### Framework Lock File

Each project maintains `framework.lock.yaml` for reproducible builds:

```yaml
# framework.lock.yaml
schema_version: 1
locked_at: '2026-03-20T10:30:00Z'

framework:
  version: 1.2.0
  source: git+https://github.com/user/infra-topology-framework.git
  commit: a1b2c3d4e5f6...
  integrity:
    sha256: 7f83b1657ff1fc53b92dc18148a1d65dfc2d4b1fa3d677284addd200126d9069

resolved_paths:
  class_modules: .framework/class-modules
  object_modules: .framework/object-modules
  layer_contract: .framework/layer-contract.yaml
  topology_tools: .framework/topology-tools
```

### Project Manifest Schema (Updated)

```yaml
# project.yaml (full schema)
schema_version: 2
project: home-lab
description: Primary home lab infrastructure
status: production

# Framework dependency
framework:
  type: submodule          # submodule | package | archive | local
  path: .framework         # For submodule/archive/local
  # name: infra-topology-framework  # For package type
  version: "1.2.0"
  # url: https://...       # For archive type

# Instance organization
instances:
  root: instances
  layout: sharded          # ADR 0071

# Project-specific object overrides
overrides:
  root: overrides
  merge_strategy: deep     # deep | shallow | replace

# Generation configuration
generation:
  output_root: generated
  targets:
    terraform_proxmox: true
    terraform_mikrotik: true
    ansible_inventory: true
    bootstrap: true

# Project metadata
meta:
  created_at: '2026-03-20'
  maintainers:
    - user@example.com
```

### Compilation in Multi-Repo Mode

```bash
# From project repository root
cd home-lab-project

# Ensure framework is available
git submodule update --init
# or: pip install -e .

# Compile using framework tools
python -m topology_tools.compile --project-root .

# Or via wrapper script
./compile.sh
```

Compiler resolution order:
1. Read `project.yaml` to find framework location
2. Load framework from `.framework/` or installed package
3. Load project instances from `instances/`
4. Apply project overrides from `overrides/`
5. Run compilation pipeline
6. Output to `generated/`

### CLI Interface

```bash
# Initialize new project from framework
topology init home-lab --framework git+https://github.com/user/framework.git

# Update framework to latest compatible version
topology framework update

# Pin framework to specific version
topology framework pin v1.3.0

# Verify framework integrity
topology framework verify

# Compile project
topology compile

# Validate without generating
topology validate
```

### 1. Directory Structure

```
v5/
├── topology/                    # FRAMEWORK (universal definitions)
│   ├── class-modules/           # Class definitions (unchanged)
│   ├── object-modules/          # Object definitions (unchanged)
│   ├── layer-contract.yaml      # Layer rules (unchanged)
│   ├── model.lock.yaml          # Version pins (unchanged)
│   └── profile-map.yaml         # Profile definitions (unchanged)
│
├── projects/                    # PROJECT INVENTORIES (deployment state)
│   ├── home-lab/
│   │   ├── project.yaml         # Project manifest
│   │   ├── instances/           # Instance shards (ADR 0071 layout)
│   │   │   └── <layer-bucket>/<group>/<instance>.yaml
│   │   └── overrides/           # Project-specific object overrides (optional)
│   │       └── obj.<domain>.<name>.yaml
│   │
│   └── test-bench/              # Additional project example
│       ├── project.yaml
│       └── instances/
│
└── topology.yaml                # Root manifest (selects active project)
```

### 2. Manifest Contract

Root `v5/topology.yaml` is updated to reference framework and project separately:

```yaml
version: 5.1.0
model: class-object-instance

# Framework paths (universal)
framework:
  class_modules_root: v5/topology/class-modules
  object_modules_root: v5/topology/object-modules
  layer_contract: v5/topology/layer-contract.yaml
  model_lock: v5/topology/model.lock.yaml
  profile_map: v5/topology/profile-map.yaml
  capability_catalog: v5/topology/class-modules/router/capability-catalog.yaml
  capability_packs: v5/topology/class-modules/router/capability-packs.yaml

# Project paths (deployment-specific)
project:
  active: home-lab
  root: v5/projects
  # Resolved paths:
  # - v5/projects/home-lab/project.yaml
  # - v5/projects/home-lab/instances/
  # - v5/projects/home-lab/overrides/ (optional)

# Legacy compatibility (deprecated, remove in v5.2)
paths:
  class_modules_root: v5/topology/class-modules
  object_modules_root: v5/topology/object-modules
  instances_root: v5/projects/home-lab/instances
  # ... remaining legacy paths
```

### 3. Project Manifest Schema

Each project has `project.yaml`:

```yaml
schema_version: 1
project: home-lab
description: Primary home lab infrastructure
status: production

# Instance organization
instances_root: instances
instances_layout: sharded  # ADR 0071

# Optional: project-specific object overrides
overrides_root: overrides

# Optional: inherit from another project
# inherits_from: minimal-base

# Generation targets
targets:
  terraform_proxmox: true
  terraform_mikrotik: true
  ansible_inventory: true
  bootstrap_proxmox: true
  bootstrap_mikrotik: true
  bootstrap_orangepi: true

# Project metadata
meta:
  created_at: '2026-03-20'
  migrated_from: v5/topology/instances
```

### 4. Instance Shard Layout (Unchanged)

Instance shards follow ADR 0071 exactly, just relocated:

```
v5/projects/home-lab/instances/
├── L0-meta/meta/
├── L1-foundation/
│   ├── devices/
│   ├── firmware/
│   ├── software_os/
│   ├── physical-links/
│   └── power/
├── L2-network/
│   ├── network/
│   └── data-channels/
├── L3-data/storage/
├── L4-platform/
│   ├── lxc/
│   └── vms/
├── L5-application/services/
├── L6-observability/observability/
└── L7-operations/operations/
```

### 5. Project Overrides (Optional Feature)

Projects MAY override object properties without modifying framework objects:

```yaml
# v5/projects/home-lab/overrides/obj.mikrotik.chateau_lte7_ax.yaml
extends: obj.mikrotik.chateau_lte7_ax

# Project-specific capability tuning
enabled_capabilities:
  - cap.net.wifi.ax
  - cap.net.lte
  - cap.container.arm64
  # Disable unused capabilities for this project
  remove:
    - cap.net.sfp
```

Compiler merge order:
`Class.defaults -> Object.defaults -> ProjectOverride -> Instance.overrides`

### 6. Multi-Project Compilation

Compiler accepts project selection:

```bash
# Compile specific project
python3 v5/topology-tools/compile.py --project home-lab

# Compile all projects (for CI validation)
python3 v5/topology-tools/compile.py --all-projects

# Default: use active project from topology.yaml
python3 v5/topology-tools/compile.py
```

### 7. Generator Output Paths

Generators output to project-qualified paths:

```
v5-generated/
├── home-lab/                    # Project-qualified output
│   ├── terraform/
│   │   ├── proxmox/
│   │   └── mikrotik/
│   ├── ansible/inventory/
│   └── bootstrap/
│
└── test-bench/                  # Another project's output
    └── ...
```

Or via configuration, single-project mode (current behavior):

```
v5-generated/
├── terraform/proxmox/           # No project prefix (single project mode)
├── terraform/mikrotik/
├── ansible/inventory/
└── bootstrap/
```

### 10. Migration Path

Migration proceeds in two stages: **Monorepo Separation** (Phases 1-3) and **Multi-Repo Extraction** (Phases 4-6).

---

#### Stage 1: Monorepo Separation (v5.1.x)

##### Phase 1: Directory Creation (Non-Breaking)

```bash
# Create project structure within existing repo
mkdir -p v5/projects/home-lab
touch v5/projects/home-lab/project.yaml
```

1. Create `v5/projects/` directory
2. Create `v5/projects/home-lab/` directory
3. Create `v5/projects/home-lab/project.yaml` manifest
4. Update `v5/topology.yaml` with dual `framework:` and `paths:` sections

##### Phase 2: Instance Migration

```bash
# Move instances to project
mv v5/topology/instances/* v5/projects/home-lab/instances/
# Keep legacy mapping for reference
mv v5/topology/instances/_legacy-home-lab v5/projects/home-lab/_legacy/
```

1. Move `v5/topology/instances/` to `v5/projects/home-lab/instances/`
2. Update `paths.instances_root` to new location
3. Archive legacy mapping data

##### Phase 3: Tooling Updates

1. Update compiler to read `framework:` + `project:` sections
2. Add `--project` CLI flag
3. Update generator output path resolution
4. Update tests to use explicit project references
5. Add `framework.lock.yaml` generation

**Milestone**: Monorepo works with framework/project separation. All existing workflows continue.

---

#### Stage 2: Multi-Repo Extraction (v5.2.x / v6.0)

##### Phase 4: Framework Extraction Preparation

1. Create `infra-topology-framework` repository
2. Copy framework components:
   ```bash
   # To new framework repo
   cp -r v5/topology/class-modules framework-repo/
   cp -r v5/topology/object-modules framework-repo/
   cp -r v5/topology-tools framework-repo/
   cp v5/topology/layer-contract.yaml framework-repo/
   ```
3. Add `framework.yaml` manifest with version
4. Add `pyproject.toml` for package distribution
5. Set up CI/CD for framework releases
6. Tag initial release `v1.0.0`

##### Phase 5: Project Extraction

1. Create `home-lab-project` repository
2. Add framework as submodule:
   ```bash
   cd home-lab-project
   git submodule add https://github.com/user/infra-topology-framework.git .framework
   git submodule update --init --checkout v1.0.0
   ```
3. Copy project data:
   ```bash
   cp -r v5/projects/home-lab/instances home-lab-project/
   cp -r v5/projects/home-lab/overrides home-lab-project/
   cp v5/projects/home-lab/project.yaml home-lab-project/
   ```
4. Update `project.yaml` with framework reference
5. Generate `framework.lock.yaml`
6. Verify compilation works standalone

##### Phase 6: Original Repo Transition

1. Archive `v5/` in original repo or mark as deprecated
2. Update original repo README to point to new repos
3. Optional: Keep original repo as "umbrella" with submodules:
   ```
   home-lab/
   ├── framework/ -> infra-topology-framework (submodule)
   ├── projects/
   │   └── home-lab/ -> home-lab-project (submodule)
   └── README.md
   ```

**Milestone**: Framework and projects are independent repositories with proper dependency management.

### 11. Validation Rules

Compiler MUST enforce:

1. **Project isolation**: Instances in one project cannot reference instances in another project
2. **Framework immutability**: Project overrides cannot modify class contracts
3. **Override schema**: Project overrides must extend valid framework objects
4. **Path consistency**: Instance shard paths must resolve within project's `instances_root`
5. **Framework version compatibility**: Project must declare compatible framework version range
6. **Lock file integrity**: `framework.lock.yaml` must match actual framework state

Diagnostic codes:

| Code | Meaning |
|------|---------|
| `E7501` | Project manifest schema violation |
| `E7502` | Cross-project instance reference |
| `E7503` | Invalid project override (class contract violation) |
| `E7504` | Project override extends non-existent object |
| `E7505` | Active project not found in projects root |
| `E7506` | Framework not found at specified path |
| `E7507` | Framework version mismatch (lock vs actual) |
| `E7508` | Framework integrity check failed |
| `E7509` | Incompatible framework version for project schema |
| `W7510` | Deprecated `paths:` section used (migration warning) |
| `W7511` | Framework lock file missing (non-reproducible build) |
| `W7512` | Framework newer than lock file (run `topology framework lock`) |

---

## Consequences

### Positive

**Stage 1 (Monorepo Separation):**
1. **Clean semantic boundary**: Framework (universal) vs Project (deployment-specific) is explicit
2. **Multi-project support**: Test benches, alternative configs, and experiments are first-class
3. **Framework reusability**: Classes and objects can be shared without instance pollution
4. **Testing isolation**: Each project has isolated instance sets for integration testing
5. **Aligns with ADR 0062**: Strengthens Class->Object->Instance separation
6. **Aligns with ADR 0071**: Instance shards unchanged, just relocated

**Stage 2 (Multi-Repo Extraction):**
7. **Independent versioning**: Framework and projects evolve on separate release cycles
8. **Access control**: Different teams can own framework vs projects
9. **Selective sharing**: Framework can be open-sourced while projects remain private
10. **Dependency clarity**: Projects declare explicit framework version requirements
11. **Reproducible builds**: Lock files ensure consistent compilation across environments
12. **Community contributions**: Framework improvements benefit all projects
13. **Smaller repositories**: Each repo contains only relevant code, faster clones

### Trade-offs

**Stage 1:**
1. **Migration effort**: One-time move of instances directory and path updates
2. **Tooling updates**: Compiler, generators, and tests need path resolution updates
3. **Manifest complexity**: New `framework:` and `project:` sections (but more explicit)
4. **Conceptual overhead**: Operators must understand framework vs project distinction

**Stage 2:**
5. **Multi-repo complexity**: Managing multiple repositories, submodules, or packages
6. **Version coordination**: Breaking changes in framework require project updates
7. **CI/CD complexity**: Cross-repo testing and release coordination
8. **Onboarding overhead**: New contributors must understand the split
9. **Offline limitations**: Package-based distribution requires internet access

### Risk Controls

1. **Phased migration**: Non-breaking phases allow incremental rollout
2. **Backward compatibility**: Legacy `paths:` section supported during transition
3. **Validation gates**: Compiler enforces project isolation from day one
4. **Rollback procedure**: Moving directories back is trivial if needed
5. **Lock files**: Ensure reproducible builds regardless of framework updates
6. **Submodule fallback**: Git submodules work offline, no external registry needed
7. **Version constraints**: Semver compatibility prevents accidental breaking changes

---

## Implementation Checklist

### Stage 1: Monorepo Separation

#### Phase 1: Directory Creation
- [ ] Create `v5/projects/` directory
- [ ] Create `v5/projects/home-lab/` directory
- [ ] Create `v5/projects/home-lab/project.yaml` with initial schema
- [ ] Update `v5/topology.yaml` with `framework:` section (alongside `paths:`)
- [ ] Update ADR register

#### Phase 2: Instance Migration
- [ ] Move `v5/topology/instances/` contents to `v5/projects/home-lab/instances/`
- [ ] Remove empty `v5/topology/instances/` directory
- [ ] Move `_legacy-home-lab/` to `v5/projects/home-lab/_legacy/`
- [ ] Update `paths.instances_root` in topology.yaml
- [ ] Verify compiler still resolves all instances

#### Phase 3: Tooling Updates
- [ ] Update `topology_loader.py` to support `framework:` + `project:` sections
- [ ] Add `--project` CLI flag to `compile.py`
- [ ] Add `--project-root` flag for standalone project compilation
- [ ] Implement `framework.lock.yaml` generation
- [ ] Update generator path resolution for optional project prefix
- [ ] Update all v5 tests to use explicit project paths
- [ ] Update CLAUDE.md paths section
- [ ] Add W7510 warning for legacy `paths:` usage

**Milestone**: v5.1.0 release with monorepo separation complete

---

### Stage 2: Multi-Repo Extraction

#### Phase 4: Framework Repository Setup
- [ ] Create `infra-topology-framework` repository
- [ ] Extract `class-modules/` to framework repo
- [ ] Extract `object-modules/` to framework repo
- [ ] Extract `topology-tools/` to framework repo
- [ ] Extract `layer-contract.yaml` to framework repo
- [ ] Create `framework.yaml` manifest with version
- [ ] Create `pyproject.toml` for Python package
- [ ] Set up CI/CD pipeline for framework releases
- [ ] Write framework README and documentation
- [ ] Tag and release `v1.0.0`

#### Phase 5: Project Repository Setup
- [ ] Create `home-lab-project` repository
- [ ] Add framework as git submodule at `.framework/`
- [ ] Copy `instances/` from monorepo
- [ ] Copy `overrides/` from monorepo (if exists)
- [ ] Create standalone `project.yaml` with framework reference
- [ ] Generate initial `framework.lock.yaml`
- [ ] Set up CI/CD pipeline for project
- [ ] Verify standalone compilation works
- [ ] Write project README

#### Phase 6: CLI and Tooling
- [ ] Implement `topology init` command for new projects
- [ ] Implement `topology framework update` command
- [ ] Implement `topology framework pin` command
- [ ] Implement `topology framework verify` command
- [ ] Add E7506-E7509 diagnostic codes
- [ ] Add W7511-W7512 diagnostic codes
- [ ] Support package-based framework installation (pip)
- [ ] Document multi-repo workflow

#### Phase 7: Original Repo Transition
- [ ] Update original `home-lab` repo README
- [ ] Archive or deprecate `v5/` directory
- [ ] Optional: Convert to umbrella repo with submodules
- [ ] Update all external documentation and links

**Milestone**: v6.0.0 / independent repositories operational

---

## References

- ADR 0062: Modular Class-Object-Instance Architecture
- ADR 0064: Firmware and OS as Separate Entities
- ADR 0071: Sharded Instance Files and Flat `instances` Root
- ADR 0074: V5 Generator Architecture
- Current topology manifest: `v5/topology/topology.yaml`
- Current instance root: `v5/topology/instances/`

## Appendix: Example Workflow

### Creating a New Project from Framework

```bash
# Clone framework or install as package
git clone https://github.com/user/infra-topology-framework.git

# Initialize new project
mkdir my-network && cd my-network
topology init --framework ../infra-topology-framework

# Or with remote framework
topology init --framework git+https://github.com/user/infra-topology-framework.git@v1.2.0

# Result:
# my-network/
# ├── .framework/ -> submodule
# ├── instances/
# │   └── L1-foundation/
# │       └── devices/
# ├── project.yaml
# └── framework.lock.yaml
```

### Updating Framework in Existing Project

```bash
cd my-network

# Check for updates
topology framework status
# Output: Current: v1.2.0, Latest: v1.3.0

# Update to latest compatible
topology framework update
# Updates submodule and regenerates lock file

# Or pin to specific version
topology framework pin v1.3.0

# Verify integrity
topology framework verify
# Output: ✓ Framework integrity verified (sha256: abc123...)
```

### CI/CD Pipeline Example

```yaml
# .github/workflows/compile.yml
name: Compile Topology
on: [push, pull_request]

jobs:
  compile:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          submodules: recursive

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install framework
        run: pip install -e .framework/

      - name: Verify framework
        run: topology framework verify

      - name: Compile topology
        run: topology compile --validate

      - name: Upload artifacts
        uses: actions/upload-artifact@v4
        with:
          name: generated
          path: generated/
```
