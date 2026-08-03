# ADR 0114: TAIGA Architecture Harmonization across Toolchain, Library, Extension, and Project Planes

- Status: Proposed
- Date: 2026-07-30
- Depends on: ADR 0062, ADR 0063, ADR 0076, ADR 0080, ADR 0081, ADR 0106
- Consolidates: Plugin system, framework/project separation, capability-driven discovery

---

## Context

### Current State

The Taiga topology system has evolved through multiple ADRs into a sophisticated infrastructure-as-data platform. Key architectural decisions established:

| ADR | Decision | Role |
|-----|----------|------|
| 0062 | Class → Object → Instance model | Data hierarchy |
| 0063 | Plugin microkernel | Extension mechanism |
| 0076 | Framework distribution | Versioned artifact consumption |
| 0080 | 6-stage pipeline | Execution lifecycle |
| 0081 | 1:N project model | Multi-project scaling |
| 0106 | Capability-driven plugins | Declarative plugin discovery |

These decisions are implemented but scattered across ADRs without a unified architectural vision document.

### Framework Identity

The framework is named **TAIGA** — *Topology Artifacts for Infrastructure Governance and Automation*.

| Attribute | Value |
|-----------|-------|
| Framework ID | `taiga` |
| Repository | `strateg/taiga` |
| Project mount point | `framework/` |

### Terminology

This ADR uses precise terminology to avoid ambiguity:

| Term | Scope | Definition |
|------|-------|------------|
| **Layer** | Architecture | One of four artifact ownership levels (Foundation, Class, Object, Project) |
| **Stratum** (pl. Strata) | Topology Model | Logical model layers L0–L7 in `layer-contract.yaml` |
| **Plane** | Historical | Original term for "Layer" in early drafts; retained for traceability |

**Note on Strata:** The L0–L7 stratum model is a logical organization convention, not a rigid contract. Projects MAY use fewer or more strata depending on their complexity. The canonical strata are:

- L0: Meta (organization, contacts)
- L1: Foundation (physical devices)
- L2: Network (VLANs, bridges, zones)
- L3: Data (storage)
- L4: Platform (VMs, containers)
- L5: Application (services)
- L6: Observability (monitoring)
- L7: Operations (backup, maintenance)

### Problem Statement

Developers and AI agents need a single coherent mental model that answers:

1. **What is executable?** — Where are the compilers, validators, generators, assemblers, builders?
2. **What is data?** — Where are classes, objects, instances, capabilities?
3. **What is extensible?** — How does a project extend framework libraries?
4. **How do plugins compose?** — How are plugins discovered, ordered, executed?

### Architectural Principle

The system follows a **programming language** metaphor:

| Concept | Programming Language | Taiga Topology |
|---------|---------------------|----------------|
| Standard library | `stdlib` | Framework class/object modules |
| Runtime | Python interpreter | Plugin microkernel + 6-stage pipeline |
| User code | Application files | Project instances + project plugins |
| Build system | `pip`, `setuptools` | Assemblers + builders |
| Package manager | `pip install` | Framework artifact consumption |

---

## Decision

Adopt **Executable Framework Architecture** with four distinct artifact layers and capability-driven plugin composition.

### 1. Four Artifact Layers (Normative)

The system is organized into four distinct layers with strict ownership boundaries:

```
┌─────────────────────────────────────────────────────────────────┐
│  Layer 4: PROJECT INSTANCES                                    │
│  ─────────────────────────────────────────────────────────────  │
│  Owner: Project repository                                      │
│  Content: topology/instances/, secrets/, project plugins        │
│  Purpose: Concrete infrastructure declarations                  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ extends
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  Layer 3: TOPOLOGY LIBRARIES (Object Modules)                  │
│  ─────────────────────────────────────────────────────────────  │
│  Owner: Framework                                               │
│  Content: topology/object-modules/                              │
│  Purpose: Reusable templates with placeholders, object plugins  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ inherits
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  Layer 2: TOPOLOGY LIBRARIES (Class Modules)                   │
│  ─────────────────────────────────────────────────────────────  │
│  Owner: Framework                                               │
│  Content: topology/class-modules/, capability-catalog.yaml      │
│  Purpose: Abstract type definitions, class plugins              │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ powered by
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  Layer 1: EXECUTABLE FOUNDATION                                 │
│  ─────────────────────────────────────────────────────────────  │
│  Owner: Framework (topology-tools/)                             │
│  Content: kernel/, plugins/, schemas/, templates/               │
│  Purpose: Runtime engine, base plugins, compilation pipeline    │
└─────────────────────────────────────────────────────────────────┘
```

#### 1.1 Layer 1: Executable Foundation

The executable foundation provides the runtime engine for topology compilation.

**Components:**

| Component | Location | Purpose |
|-----------|----------|---------|
| Kernel | `topology-tools/kernel/` | Plugin registry, scheduler, context |
| Base plugins | `topology-tools/plugins/` | Framework-level compilers, validators, generators |
| Schemas | `topology-tools/schemas/` | JSON Schema definitions |
| Templates | `topology-tools/templates/` | Jinja2 generation templates |
| Entrypoints | `topology-tools/compile-topology.py` | Pipeline execution |

**Plugin Families (6 total):**

| Family | Stage | Purpose |
|--------|-------|---------|
| `discoverers` | discover | Manifest loading, capability detection |
| `compilers` | compile | Model transformation, resolution |
| `validators` | validate | Contract enforcement, structural checks |
| `generators` | generate | Artifact emission (Terraform, Ansible, docs) |
| `assemblers` | assemble | Execution view construction |
| `builders` | build | Packaging, trust verification, release |

**Execution Contract:**

```
discover → compile → validate → generate → assemble → build
```

Each stage follows universal phase model:

```
init → pre → run → post → verify → finalize
```

#### 1.2 Layer 2: Class Modules (Topology Library - Abstract)

Class modules define abstract infrastructure types.

**Structure:**

```
topology/class-modules/
├── capability-catalog.yaml          # Capability ontology (200+ capabilities)
├── compute/
│   ├── class.yaml                   # class.compute.hypervisor, class.compute.vm
│   └── plugins/                     # Class-level plugins
├── network/
│   ├── class.yaml                   # class.network.router, class.network.switch
│   └── plugins/
├── storage/
│   ├── class.yaml                   # class.storage.nas, class.storage.array
│   └── plugins/
└── [9 total domains]
```

**Class Plugin Boundary Rules:**

1. Class-level plugins MUST NOT hardcode object identifiers (`obj.*`)
2. Class-level plugins MUST NOT hardcode instance identifiers (`inst.*`)
3. Class-level plugins provide domain-wide validation and generation logic

**Project Extension:**

Projects MAY NOT define new classes (framework owns class namespace).

#### 1.3 Layer 3: Object Modules (Topology Library - Concrete)

Object modules provide vendor-specific templates.

**Structure:**

```
topology/object-modules/
├── mikrotik/
│   ├── chateau-lte12/
│   │   ├── object.yaml              # obj.mikrotik.chateau-lte12 template
│   │   ├── plugins/                 # Object-level plugins
│   │   └── templates/               # Object-specific Jinja2
│   └── hap-ax3/
│       ├── object.yaml
│       └── plugins/
├── proxmox/
│   └── ve/
│       ├── object.yaml              # obj.proxmox.ve template
│       └── plugins/
└── [vendor modules]
```

**Object Plugin Boundary Rules:**

1. Object-level plugins MUST NOT hardcode instance identifiers (`inst.*`)
2. Object-level plugins provide object-family-wide behavior
3. Object templates use `@placeholder` syntax for instance-resolved values

**Project Extension:**

Projects MAY define new object modules in `<project>/topology/object-modules/` for project-specific device families. Project objects:

1. MUST reference existing framework classes
2. MUST follow the same structural contract as framework objects
3. ARE discovered after framework objects (additive merge)
4. MUST have globally unique object_ref (no override of framework objects)

#### 1.4 Layer 4: Project Instances

Project instances are concrete infrastructure declarations.

**Structure:**

```
<project>/
├── topology/
│   └── instances/
│       ├── L0-meta/                 # Organization, contacts
│       ├── L1-foundation/           # Physical devices, racks
│       ├── L2-network/              # VLANs, bridges, zones
│       ├── L3-data/                 # Storage mounts, volumes
│       ├── L4-platform/             # VMs, containers, hosts
│       ├── L5-application/          # Services, applications
│       ├── L6-observability/        # Monitoring, logging
│       └── L7-operations/           # Backup, maintenance
├── plugins/                         # Project-specific plugins
│   ├── discoverers/
│   ├── compilers/
│   ├── validators/
│   ├── generators/
│   ├── assemblers/
│   └── builders/
├── secrets/                         # SOPS-encrypted secrets
├── framework.lock.yaml              # Pinned framework version
├── project.model.lock.yaml          # Project-defined module versions (if any)
└── project.yaml                     # Project manifest
```

**Instance Resolution:**

Instances resolve `@placeholder` values from object templates:

```yaml
# Object template (framework)
object:
  object_ref: obj.mikrotik.chateau-lte12
  defaults:
    hostname: "@placeholder"
    management_ip: "@on:host.management_ip"

# Instance (project)
instance:
  instance_ref: inst.rtr-main
  object_ref: obj.mikrotik.chateau-lte12
  hostname: rtr-main.example.com
```

### 2. Plugin Discovery and Composition (Normative)

Plugins are discovered and merged in deterministic order:

```
Kernel (built-in)
    ↓
Framework Base (topology-tools/plugins/plugins.yaml)
    ↓
Class Modules (topology/class-modules/**/plugins.yaml)
    ↓
Object Modules (topology/object-modules/**/plugins.yaml)
    ↓
Project (project/plugins/plugins.yaml)
```

#### 2.1 Discovery Rules

1. **Deterministic merge**: Within each level, manifests sorted lexicographically by path
2. **Additive only**: Later levels add plugins, cannot override earlier levels
3. **Unique IDs required**: Duplicate plugin IDs across any level = hard error
4. **Capability gates**: Plugins may declare `requires_capabilities` for conditional activation

#### 2.2 Capability-Driven Plugin Activation

Plugins declare capability requirements in manifest:

```yaml
plugins:
  - id: obj.mikrotik.generator.routeros
    kind: generator
    stages: [generate]
    requires_capabilities:
      - cap.os.routeros
    produces:
      - key: routeros_scripts
        scope: pipeline_shared
```

Runtime activates plugin only when:

1. Plugin is discovered in merge chain
2. All `requires_capabilities` are present in compiled model
3. `when` predicates evaluate to true

#### 2.3 Plugin Isolation Model

Each plugin family maintains strict stage affinity:

| Plugin Kind | Allowed Stage | Violation = |
|-------------|---------------|-------------|
| `discoverer` | discover | E8001 |
| `compiler` | compile | E4001 |
| `validator_yaml` | validate | E4002 |
| `validator_json` | validate | E4003 |
| `generator` | generate | E4004 |
| `assembler` | assemble | E8101 |
| `builder` | build | E8201 |

### 3. Framework-Project Composition Model (Normative)

#### 3.1 Composition Principle

Project extends Framework through **layered composition**, not inheritance:

```
┌────────────────────────────────────────────────────┐
│              COMPILED MODEL                        │
│  ┌──────────────────────────────────────────────┐  │
│  │ Framework Classes + Objects                   │  │
│  │   + Project Instances                         │  │
│  │     + Project Objects (if any)                │  │
│  │       + Project Plugins                       │  │
│  └──────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────┘
```

#### 3.2 Consumption Modes

| Mode | Use Case | Lock Source | Trust Level |
|------|----------|-------------|-------------|
| Package artifact | Production | `framework.source: package` | Full (signature + provenance + SBOM) |
| Git submodule | Development | `framework.source: git` | Integrity (SHA + hash) |
| Local path | Framework dev | N/A | None (forbidden for release) |

#### 3.3 Project Extension Capabilities

| Extension Type | Allowed? | Location | Discovery Order |
|----------------|----------|----------|-----------------|
| New instances | Yes | `topology/instances/` | After framework compile |
| New object modules | Yes | `topology/object-modules/` | After framework objects |
| New class modules | No | — | Framework owns classes |
| New plugins | Yes | `plugins/<family>/` | After framework plugins |
| Override framework plugins | No | — | Unique IDs required |
| Project-defined classes | Yes (namespaced) | `topology/class-modules/` | MUST use `class.<project>.*` namespace |

**Namespace Rule:** If a project defines custom classes, they MUST use the `class.<project>.*` namespace to avoid collision with framework classes. Framework identifiers MUST NOT be shadowed.

### 4. Artifact Packaging Model (Normative)

#### 4.1 Framework Artifact

Framework ships as versioned artifact containing:

```
framework-<version>.zip
├── framework.yaml                   # Manifest + version
├── topology/
│   ├── class-modules/               # All classes
│   ├── object-modules/              # All objects
│   ├── capability-catalog.yaml
│   ├── layer-contract.yaml
│   └── model.lock.yaml
└── topology-tools/
    ├── kernel/                      # Runtime engine
    ├── plugins/                     # Base plugins
    ├── schemas/                     # Validation schemas
    ├── templates/                   # Generation templates
    └── compile-topology.py          # Entrypoint
```

**Exclusions** (development-only):

- Tests, ADRs, docs, AI agent configs, IDE files
- Project data, generated outputs, Python bytecode

**Versioning Semantics:**

| Component | Version Source | Integrity Mechanism |
|-----------|---------------|---------------------|
| Toolchain (kernel, pipeline) | `framework_api_version` in `framework.yaml` | API compatibility check |
| Library (classes, objects) | `model.lock.yaml` content hash | SHA256 integrity |
| Plugin packs | Individual pack `version` | Pack manifest + hash |
| Project modules | `project.model.lock.yaml` | Project-side integrity |

The `framework.lock.yaml` becomes a true lockfile over three artifact families (toolchain, library, packs), each with its own version and integrity entry.

#### 4.2 Plugin Artifact (Future)

Individual plugins or plugin packs may be distributed as artifacts:

```
plugin-pack-<name>-<version>.zip
├── manifest.yaml                    # Plugin manifest
├── plugins/
│   ├── discoverers/
│   ├── compilers/
│   ├── validators/
│   ├── generators/
│   ├── assemblers/
│   └── builders/
├── templates/                       # Plugin-specific templates
└── schemas/                         # Plugin-specific schemas
```

Plugin artifacts:

1. MUST declare `requires_framework_version` for compatibility
2. MUST declare unique plugin IDs
3. MAY declare `requires_capabilities` for conditional activation
4. ARE discovered at project level in merge chain

### 5. AI Agent and Developer Tooling Contract (Normative)

#### 5.1 Executable Tools for AI Agents

AI agents have access to the complete executable foundation:

| Tool | Purpose | Usage |
|------|---------|-------|
| `compile-topology.py` | Run full pipeline | Always available |
| `verify-framework-lock.py` | Verify dependencies | Before changes |
| `generate-framework-lock.py` | Update lock | After framework update |

#### 5.2 Declarative Data for AI Agents

AI agents work with declarative topology data:

| Data Type | Location | Editable? |
|-----------|----------|-----------|
| Class definitions | `topology/class-modules/` | Framework development only |
| Object templates | `topology/object-modules/` | Framework development only |
| Instance declarations | `projects/<id>/topology/instances/` | Always |
| Capability catalog | `topology/class-modules/capability-catalog.yaml` | Framework development |
| Secrets | `projects/<id>/secrets/` | With SOPS encryption |

#### 5.3 Plugin Development Pattern

AI agents creating plugins follow this pattern:

```yaml
# 1. Define plugin in manifest
plugins:
  - id: project.validator.naming_convention
    kind: validator_json
    stages: [validate]
    phase: run
    order: 150
    entry: plugins/validators/naming_convention.py:NamingValidator
    api_version: "1.x"
    requires_capabilities: []
    produces: []
    consumes:
      - from_plugin: base.compiler.instance_rows
        key: normalized_rows
        required: true
```

```python
# 2. Implement plugin class
class NamingValidator(PluginBase):
    def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        rows = ctx.subscribe("base.compiler.instance_rows", "normalized_rows")
        diagnostics = []
        for row in rows:
            if not self._check_naming(row["instance_ref"]):
                diagnostics.append(PluginDiagnostic(
                    code="E9001",
                    message=f"Invalid naming: {row['instance_ref']}",
                    severity=Severity.ERROR,
                    location=row.get("source_location")
                ))
        return PluginResult(
            plugin_id=self.plugin_id,
            status=PluginStatus.SUCCESS if not diagnostics else PluginStatus.PARTIAL,
            diagnostics=diagnostics
        )
```

### 6. Validation and Verification Gates (Normative)

#### 6.1 Compile-Time Verification

| Check | Error Code | Stage |
|-------|------------|-------|
| Plugin ID uniqueness | E4001 | discover |
| Stage affinity violation | E4002 | discover |
| Missing dependency | E4003 | discover |
| Capability mismatch | E8020 | compile |
| Instance resolution failure | E6001 | compile |
| Reference validation | E5001 | validate |
| Topology requires capability no plugin provides | E4013 | validate |

**E4013 Note:** This diagnostic ensures that if topology declares functionality via capabilities, at least one installed plugin can serve that capability. This prevents silent omission when configuration expects a feature that no plugin implements.

#### 6.2 Lock Verification

| Check | Error Code | Description |
|-------|------------|-------------|
| Lock missing | E7822 | No framework.lock.yaml |
| Revision mismatch | E7823 | Framework changed |
| Integrity mismatch | E7824 | Content hash differs |
| Version incompatible | E7811 | Version below minimum |

---

## Consequences

### Positive

1. **Unified mental model**: One document explains entire architecture
2. **Clear ownership boundaries**: Framework vs project vs plugin responsibilities defined
3. **Composable extensions**: Projects extend framework without modification
4. **AI-agent friendly**: Executable tools + declarative data = predictable behavior
5. **Language-like semantics**: Developers understand "standard library" metaphor

### Trade-offs

1. **Learning curve**: Four-layer model requires initial understanding
2. **Strict boundaries**: Cannot override framework behavior (by design)
3. **Plugin discipline**: Stage affinity and capability requirements add complexity

### Migration Impact

This ADR consolidates existing decisions — no migration required. It serves as the canonical reference for understanding how ADRs 0062, 0063, 0076, 0080, 0081, 0106 work together.

---

## Recorded Debt

The following technical debt items are acknowledged but not resolved by this ADR:

### D1. Residual Project Coupling in Framework Assets

Framework assets contain hardcoded project references that should be parameterized:

| Location | Issue |
|----------|-------|
| `plugins/manifests/compilers.yaml` (5 occurrences) | `secrets_root: projects/home-lab/secrets` defaults |
| `plugins/compilers/instance_rows_compiler.py:765` | Same fallback path |
| `templates/ansible/playbooks/vpn-gateway.yml.j2:19` | Path `../../../../projects/home-lab/secrets` |
| `templates/ansible/host_vars/wireguard_gateway.yml.j2:25,30` | Comments reference home-lab |

**Resolution:** These paths must be parameterized before framework extraction to separate repository.

### D2. Integration Test Fixture Dependency

ADR 0081:57 designates `projects/home-lab` as a required integration fixture of the framework repository. When the project moves to its own repository:

- `projects/test-lab` must be promoted to integration fixture role
- `projects/test-lab` currently lacks complete `topology.yaml` and instances
- `tests/plugin_integration/test_tuc*.py` reference home-lab data

**Resolution:** Prepare `projects/test-lab` as framework-internal fixture before repository split.

---

## References

- ADR 0062: `adr/0062-modular-topology-architecture-consolidation.md` — Class-Object-Instance model
- ADR 0063: `adr/0063-plugin-microkernel-for-compiler-validators-generators.md` — Plugin architecture
- ADR 0076: `adr/0076-framework-distribution-and-multi-repository-extraction.md` — Framework distribution
- ADR 0080: `adr/0080-unified-build-pipeline-stage-phase-and-plugin-data-bus.md` — 6-stage pipeline
- ADR 0081: `adr/0081-framework-runtime-artifact-and-1-n-project-repository-model.md` — 1:N model
- ADR 0106: `adr/0106-capability-driven-plugin-architecture.md` — Capability-driven plugins
- AGENT-RULEBOOK: `docs/ai/AGENT-RULEBOOK.md` — AI agent rules
- Plugin contract: `topology-tools/schemas/plugin-manifest.schema.json`
- Capability catalog: `topology/class-modules/capability-catalog.yaml`
