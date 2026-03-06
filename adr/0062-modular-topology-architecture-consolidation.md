# ADR 0062: Topology v5 — Modular Class-Object-Instance Architecture

**Date:** 2026-03-06
**Status:** Proposed
**Supersedes:** ADR 0058, ADR 0059, ADR 0060, ADR 0061
**Evolves:** ADR 0048 (Topology v4 Architecture Consolidation)

---

## Context

### Evolution from Topology v4 to v5

| Version | Focus | Key Features |
|---------|-------|--------------|
| v4.0 (ADR 0048) | Layer consolidation | 8-layer OSI model, L0 abstract policies, tool versioning |
| **v5.0 (this ADR)** | Modular architecture | Class→Object→Instance, self-contained modules, YAML→JSON compilation |

Topology v4 established the layer structure (L0-L7) and governance rules. Topology v5 builds on this foundation by introducing **modular separation of concerns**:
- **Classes** define abstract semantics (router, hypervisor, container)
- **Objects** implement classes for specific vendors/products (MikroTik, Proxmox, LXC)
- **Instances** deploy objects in concrete environments (home-lab, office-lab)

### Topology Version History

| Version | ADR | Date | Key Changes |
|---------|-----|------|-------------|
| v1.0 | — | 2025 | Initial flat YAML structure |
| v2.0 | — | 2025 | Layer separation (L0-L7 draft) |
| v3.0 | 0027-0029 | 2026-02 | Consolidated layers, storage taxonomy |
| v4.0 | 0048 | 2026-02-28 | OSI-like 8-layer model, L0 policies, tool versioning |
| **v5.0** | **0062** | **2026-03-06** | **Class→Object→Instance, modular architecture, YAML→JSON compiler** |

### v4 → v5 Compatibility Matrix

| Feature | v4 Syntax | v5 Syntax | Compatibility |
|---------|-----------|-----------|---------------|
| Device type | `type: router` | `class_ref: router` | Both supported during migration |
| Implementation | `implementation: mikrotik` | `object_ref: mikrotik_chateau_lte7` | Both supported during migration |
| Layer files | `topology/L*.yaml` | `topology/home-lab/L*.yaml` | Symlinks during migration |
| Validation | `validate-topology.py` | `topology-core validate` | Both work, new wraps old |
| Generation | `regenerate-all.py` | `topology-core build` | Both work during migration |
| Output format | YAML consumed by generators | JSON consumed by generators | v5 compiles YAML→JSON |

### Problem Statement

ADRs 0058-0061 introduced the architectural direction for modular topology management but suffered from:

1. **Fragmentation** — Four interconnected ADRs with overlapping concepts and terminology
2. **Premature repository split** — Proposed two-repository model without external consumers
3. **Over-engineered capabilities** — Four-layer capability model for ~10 actual capabilities
4. **Unclear module boundaries** — Code and schema extensions spread across directories

### Core Requirements (Consolidated)

1. **Separation of concerns**: Base layer (classes) vs implementation layer (objects) vs deployment layer (instances)
2. **Self-contained modules**: Each module contains schema extensions, validators, generators, and templates
3. **YAML → JSON compilation**: Human-readable source, machine-readable canonical artifact
4. **Two-stage validation**: Validate YAML source, then validate compiled JSON
5. **Single repository**: Directory-based separation, no premature repo split
6. **AI-friendly diagnostics**: Structured error output for automated repair loops

### Class → Object → Instance Model

The core abstraction applies universally across all infrastructure entities:

| Layer | Description | Examples |
|-------|-------------|----------|
| **Class** | Abstract semantics and capabilities | `router`, `hypervisor`, `sbc`, `host_os`, `container` |
| **Object** | Concrete implementation/product | `mikrotik_chateau`, `proxmox_ve_9`, `debian_12`, `lxc_proxmox` |
| **Instance** | Deployed node with environment bindings | `rtr-home-main`, `hv-gamayun`, `lxc-nginx-prod` |

Resolution chain:
```
Instance.object_ref → Object.class_ref → Class
```

Merge precedence:
```
Class.defaults → Object.defaults → Instance.overrides
```

---

## Decision

### 1. Adopt Three-Layer Directory Structure

All code remains in single repository with explicit directory boundaries:

```
home-lab/
├── topology-core/           # CLASS layer: engine + class modules
├── topology-modules/        # OBJECT layer: object modules
└── topology/                # INSTANCE layer: project topologies
    └── {project-name}/
```

No repository split until criteria met:
- 3+ external projects depend on topology-core
- Different release cadence required

### 2. Define Module Architecture

#### 2.1 Module = Self-Contained Package

Every module (class or object) is a self-contained directory:

```
{module}/
├── manifest.yaml           # Module metadata and dependencies
├── schema/                 # Schema extensions (YAML schemas)
├── validators/
│   ├── yaml/               # Source YAML validators
│   └── json/               # Compiled JSON validators
├── generators/             # Artifact generators (if applicable)
│   └── {type}/
│       ├── generator.py
│       └── templates/
└── tests/
```

#### 2.2 Class Module Structure

```
topology-core/classes/{class}/
├── manifest.yaml
│   # id, version, description
│   # capabilities (required/optional)
│   # schema files
│   # validators
│
├── capabilities.yaml       # Capability definitions for this class
├── schema/
│   └── {class}.schema.yaml # Class-level schema extensions
└── validators/
    ├── yaml/
    │   └── {class}_validator.py
    └── json/
        └── {class}_contract.py
```

#### 2.3 Object Module Structure

```
topology-modules/{object}/
├── manifest.yaml
│   # id, version, description
│   # implements: [class_ids]
│   # schema files
│   # validators
│   # generators
│
├── objects.yaml            # Object catalog (models/variants)
├── schema/
│   ├── device.schema.yaml  # Object-specific device fields
│   └── *.schema.yaml       # Other schema extensions
├── validators/
│   ├── yaml/
│   └── json/
├── generators/
│   ├── terraform/
│   │   ├── generator.py
│   │   └── templates/
│   ├── bootstrap/
│   │   ├── generator.py
│   │   └── templates/
│   └── ansible/            # Optional
└── tests/
```

### 3. Define Compilation Engine

Location: `topology-core/engine/`

```
topology-core/engine/
├── __init__.py
├── loader.py               # YAML + !include resolution
├── registry.py             # Module discovery and loading
├── merger.py               # Schema merging (class + object + base)
├── compiler.py             # YAML → JSON transformation
├── validator.py            # Validation orchestration
├── generator.py            # Generation orchestration
└── diagnostics.py          # Structured error formatting
```

### 4. Define Compilation Pipeline

```
┌────────────────────────────────────────────────────────────────┐
│                    COMPILATION PIPELINE                         │
├────────────────────────────────────────────────────────────────┤
│                                                                 │
│  INPUT: topology/{project}/L*.yaml                              │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ 1. LOAD                                                  │   │
│  │    - Parse YAML files                                    │   │
│  │    - Resolve !include directives                         │   │
│  │    - Merge L0-L7 layers                                  │   │
│  └─────────────────────────────────────────────────────────┘   │
│                              ↓                                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ 2. DISCOVER                                              │   │
│  │    - Extract class_ref/object_ref from topology          │   │
│  │    - Load required class modules                         │   │
│  │    - Load required object modules                        │   │
│  │    - Verify module dependencies                          │   │
│  └─────────────────────────────────────────────────────────┘   │
│                              ↓                                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ 3. MERGE SCHEMA                                          │   │
│  │    - Combine: base schema + class schemas + object schemas│   │
│  │    - Build unified validation schema                     │   │
│  └─────────────────────────────────────────────────────────┘   │
│                              ↓                                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ 4. VALIDATE YAML (source validation)                     │   │
│  │    - JSON Schema validation against merged schema        │   │
│  │    - Class YAML validators                               │   │
│  │    - Object YAML validators                              │   │
│  │    - Output: diagnostics[]                               │   │
│  └─────────────────────────────────────────────────────────┘   │
│                              ↓ (if no errors)                   │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ 5. COMPILE                                               │   │
│  │    - Resolve all ID references                           │   │
│  │    - Apply profile overlay (if specified)                │   │
│  │    - Merge: class defaults → object defaults → instance  │   │
│  │    - Compute effective values                            │   │
│  │    - Transform to canonical JSON structure               │   │
│  └─────────────────────────────────────────────────────────┘   │
│                              ↓                                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ 6. VALIDATE JSON (compiled validation)                   │   │
│  │    - Class JSON validators (contract checks)             │   │
│  │    - Object JSON validators (implementation checks)      │   │
│  │    - Cross-reference integrity                           │   │
│  │    - Output: diagnostics[]                               │   │
│  └─────────────────────────────────────────────────────────┘   │
│                              ↓ (if no errors)                   │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ 7. EMIT                                                  │   │
│  │    - Write effective-topology.json                       │   │
│  │    - Write diagnostics.json                              │   │
│  │    - Write diagnostics.txt (human-readable)              │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  OUTPUT: generated/{project}/compiled/                          │
│                                                                 │
├────────────────────────────────────────────────────────────────┤
│                    GENERATION PIPELINE                          │
├────────────────────────────────────────────────────────────────┤
│                                                                 │
│  INPUT: generated/{project}/compiled/effective-topology.json    │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ 8. GENERATE                                              │   │
│  │    - Dispatch to object module generators                │   │
│  │    - Each generator produces its artifact type           │   │
│  │    - terraform/, bootstrap/, ansible/, docs/             │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  OUTPUT: generated/{project}/{terraform,bootstrap,ansible,...}  │
│                                                                 │
└────────────────────────────────────────────────────────────────┘
```

### 5. Define Manifest Contracts

#### 5.1 Class Manifest

```yaml
# topology-core/classes/{class}/manifest.yaml
id: router                          # Unique class identifier
version: "1.0.0"
type: class

description: "Layer 3 packet forwarding device"

# Capabilities this class defines
capabilities:
  required:
    - routing                       # Must be supported by any implementing object
  optional:
    - firewall
    - nat
    - dhcp_server
    - vpn_endpoint
    - container_hosting

# Schema extensions
schema:
  files:
    - schema/router.schema.yaml

# Validators
validators:
  yaml:
    - validators/yaml/router_validator.py:RouterYamlValidator
  json:
    - validators/json/router_contract.py:RouterContractValidator

# Dependencies on other classes (if any)
depends_on: []
```

#### 5.2 Object Manifest

```yaml
# topology-modules/{object}/manifest.yaml
id: mikrotik
version: "1.0.0"
type: object

description: "MikroTik RouterOS devices"

# Which classes this module implements
implements:
  - router
  - switch

# Object catalog
objects:
  $include: objects.yaml

# Schema extensions
schema:
  files:
    - schema/device.schema.yaml
    - schema/network.schema.yaml

# Validators
validators:
  yaml:
    - validators/yaml/mikrotik_validator.py:MikrotikYamlValidator
  json:
    - validators/json/mikrotik_contract.py:MikrotikContractValidator

# Generators
generators:
  terraform:
    entry: generators/terraform/generator.py:MikrotikTerraformGenerator
    outputs:
      - terraform/mikrotik/
  bootstrap:
    entry: generators/bootstrap/generator.py:MikrotikBootstrapGenerator
    outputs:
      - bootstrap/{instance_id}/

# Dependencies
depends_on:
  classes:
    - router
    - switch
  objects: []
```

#### 5.3 Object Catalog

```yaml
# topology-modules/{object}/objects.yaml
objects:
  mikrotik_chateau_lte7:
    model: "Chateau LTE7 ax"
    class: router
    virtual: false
    capabilities:
      - routing
      - firewall
      - nat
      - dhcp_server
      - vpn_endpoint
      - container_hosting
    specs:
      cpu_cores: 2
      ram_mb: 1024
      ports: { wan: 1, lan: 4 }
      wireless: true
      lte: true

  mikrotik_chr:
    model: "Cloud Hosted Router"
    class: router
    virtual: true
    capabilities:
      - routing
      - firewall
      - nat
      - dhcp_server
      - vpn_endpoint
    substitutes_for:              # Can replace these in virtual profile
      - mikrotik_chateau_lte7
```

#### 5.4 Project Manifest

```yaml
# topology/{project}/project.yaml
id: home-lab
version: "1.0.0"

# Required modules
requires:
  classes:
    - router
    - hypervisor
    - sbc
    - host_os
    - container
    - network
  objects:
    - mikrotik
    - proxmox
    - orangepi5
    - debian
    - lxc

# Profile overlays
profiles:
  default: null                   # No overlay
  virtual: profiles/virtual.yaml  # Virtual substitutions

# Module configuration overrides
module_config:
  mikrotik:
    terraform_provider_version: ">=1.30.0"
  proxmox:
    api_version: "v2"
```

### 6. Define Topology Instance Syntax

```yaml
# topology/{project}/L1-foundation.yaml
devices:
  - id: rtr-home-main
    class_ref: router                    # → topology-core/classes/router/
    object_ref: mikrotik_chateau_lte7    # → topology-modules/mikrotik/

    # Class-level fields (defined in router.schema.yaml)
    wan_interface: ether1
    routing_protocol: static
    firewall_enabled: true

    # Object-level fields (defined in mikrotik/schema/device.schema.yaml)
    routeros_version: "7.15"
    ros_packages: [container, iot]

    # Instance-level fields
    management_ip: 192.168.88.1
    interfaces:
      - id: ether1
        type: ethernet
        role: wan

  - id: hv-gamayun
    class_ref: hypervisor
    object_ref: proxmox_ve_9

    # Class-level
    vm_hosting: true
    container_hosting: true

    # Object-level
    pve_version: "9.0"
    cluster_enabled: false

    # Instance-level
    management_ip: 10.0.99.1
```

### 7. Define Structured Diagnostics

#### 7.1 Diagnostic Record

```yaml
# Schema for diagnostic records
type: object
required: [code, severity, message, path]
properties:
  code:
    type: string
    pattern: "^[EWI][0-9]{4}$"
  severity:
    enum: [error, warning, info]
  stage:
    enum: [load, discover, merge, validate_yaml, compile, validate_json, emit, generate]
  message:
    type: string
  path:
    type: string
    description: "JSONPath to error location"
  source:
    type: object
    properties:
      file: { type: string }
      line: { type: integer }
      column: { type: integer }
  hint:
    type: string
  autofix:
    type: object
    properties:
      action: { enum: [replace, insert, delete] }
      value: {}
```

#### 7.2 Error Code Taxonomy

| Range | Stage | Description |
|-------|-------|-------------|
| E1xxx | load | YAML parse errors, !include failures |
| E2xxx | discover/merge | Unknown module, missing dependency, schema conflict |
| E3xxx | validate_yaml | Source validation errors |
| E4xxx | compile | Reference resolution, profile application errors |
| E5xxx | validate_json | Compiled model contract violations |
| E6xxx | emit/generate | Output generation errors |
| W3xxx | validate_yaml | Source validation warnings |
| W5xxx | validate_json | Compiled model warnings |
| I9xxx | any | Informational messages |

#### 7.3 Diagnostics Output

```json
{
  "version": "1.0",
  "project": "home-lab",
  "profile": null,
  "timestamp": "2026-03-06T12:00:00Z",
  "status": "error",
  "summary": {
    "errors": 2,
    "warnings": 1,
    "info": 0
  },
  "diagnostics": [
    {
      "code": "E2001",
      "severity": "error",
      "stage": "discover",
      "message": "Unknown object_ref 'mikrotik_rb750' - module not found",
      "path": "$.devices[1].object_ref",
      "source": {
        "file": "topology/home-lab/L1-foundation.yaml",
        "line": 42,
        "column": 16
      },
      "hint": "Available mikrotik objects: mikrotik_chateau_lte7, mikrotik_chr"
    },
    {
      "code": "E5001",
      "severity": "error",
      "stage": "validate_json",
      "message": "Object 'mikrotik_chr' missing required capability 'container_hosting' for instance role",
      "path": "$.devices[0]",
      "hint": "Instance requests container_hosting but mikrotik_chr does not support it"
    }
  ]
}
```

### 8. Define Profile Overlay Mechanism

```yaml
# topology/{project}/profiles/virtual.yaml
description: "Virtual environment for testing"

# Object substitutions
replacements:
  rtr-home-main:
    object_ref: mikrotik_chr           # Replace hardware with CHR
  hv-gamayun:
    object_ref: proxmox_nested         # Nested virtualization

# Additional overrides
overrides:
  rtr-home-main:
    routeros_license: "free"
    lte_config: null                   # Remove LTE (not available in CHR)

# Instances to exclude from this profile
exclude:
  - sbc-orangepi5                      # No virtual equivalent
```

Compatibility rule: Replacement object must implement same class and satisfy instance capability requirements.

### 9. Define CLI Interface

```bash
# Compile topology (YAML → JSON)
topology-core compile \
    --project topology/home-lab \
    --output generated/home-lab/compiled \
    [--profile virtual]

# Validate only (no emit)
topology-core validate \
    --project topology/home-lab \
    [--profile virtual]

# Generate artifacts from compiled JSON
topology-core generate \
    --input generated/home-lab/compiled/effective-topology.json \
    --output generated/home-lab \
    [--generators terraform,bootstrap,ansible]

# All-in-one
topology-core build \
    --project topology/home-lab \
    --output generated/home-lab \
    [--profile virtual]
```

### 10. Define Full Directory Structure

```
home-lab/
│
├── topology-core/                          # CLASS LAYER
│   │
│   ├── engine/                             # Compilation engine
│   │   ├── __init__.py
│   │   ├── loader.py
│   │   ├── registry.py
│   │   ├── merger.py
│   │   ├── compiler.py
│   │   ├── validator.py
│   │   ├── generator.py
│   │   └── diagnostics.py
│   │
│   ├── schemas/                            # Base schemas
│   │   ├── topology.schema.yaml
│   │   ├── layer.schema.yaml
│   │   ├── manifest.schema.yaml
│   │   └── diagnostics.schema.yaml
│   │
│   ├── classes/                            # Class modules
│   │   ├── router/
│   │   │   ├── manifest.yaml
│   │   │   ├── capabilities.yaml
│   │   │   ├── schema/
│   │   │   │   └── router.schema.yaml
│   │   │   └── validators/
│   │   │       ├── yaml/
│   │   │       └── json/
│   │   │
│   │   ├── hypervisor/
│   │   │   ├── manifest.yaml
│   │   │   ├── capabilities.yaml
│   │   │   ├── schema/
│   │   │   └── validators/
│   │   │
│   │   ├── sbc/
│   │   ├── host_os/
│   │   ├── container/
│   │   └── network/
│   │
│   ├── cli/                                # CLI entry points
│   │   ├── __init__.py
│   │   ├── compile.py
│   │   ├── validate.py
│   │   ├── generate.py
│   │   └── build.py
│   │
│   ├── data/
│   │   └── error-catalog.yaml              # Error code definitions
│   │
│   └── tests/
│
├── topology-modules/                        # OBJECT LAYER
│   │
│   ├── mikrotik/
│   │   ├── manifest.yaml
│   │   ├── objects.yaml
│   │   ├── schema/
│   │   │   ├── device.schema.yaml
│   │   │   └── network.schema.yaml
│   │   ├── validators/
│   │   │   ├── yaml/
│   │   │   │   └── mikrotik_validator.py
│   │   │   └── json/
│   │   │       └── mikrotik_contract.py
│   │   ├── generators/
│   │   │   ├── terraform/
│   │   │   │   ├── generator.py
│   │   │   │   └── templates/
│   │   │   └── bootstrap/
│   │   │       ├── generator.py
│   │   │       └── templates/
│   │   └── tests/
│   │
│   ├── proxmox/
│   │   ├── manifest.yaml
│   │   ├── objects.yaml
│   │   ├── schema/
│   │   │   ├── device.schema.yaml
│   │   │   ├── storage.schema.yaml
│   │   │   └── workload.schema.yaml
│   │   ├── validators/
│   │   ├── generators/
│   │   │   ├── terraform/
│   │   │   ├── bootstrap/
│   │   │   └── ansible/
│   │   └── tests/
│   │
│   ├── orangepi5/
│   │   ├── manifest.yaml
│   │   ├── objects.yaml
│   │   ├── schema/
│   │   ├── validators/
│   │   ├── generators/
│   │   │   └── bootstrap/
│   │   └── tests/
│   │
│   ├── debian/
│   │   ├── manifest.yaml
│   │   ├── objects.yaml
│   │   ├── schema/
│   │   ├── validators/
│   │   └── generators/
│   │       └── cloud-init/
│   │
│   └── lxc/
│       ├── manifest.yaml
│       ├── objects.yaml
│       ├── schema/
│       └── validators/
│
├── topology/                                # INSTANCE LAYER
│   │
│   └── home-lab/
│       ├── project.yaml                     # Project manifest
│       ├── topology.yaml                    # Entry point
│       ├── L0-meta.yaml
│       ├── L1-foundation.yaml
│       ├── L2-network.yaml
│       ├── L3-data.yaml
│       ├── L4-platform.yaml
│       ├── L5-application.yaml
│       ├── L6-observability.yaml
│       ├── L7-operations.yaml
│       └── profiles/
│           └── virtual.yaml
│
├── generated/                               # COMPILED OUTPUT
│   └── home-lab/
│       ├── compiled/
│       │   ├── effective-topology.json
│       │   ├── diagnostics.json
│       │   └── diagnostics.txt
│       ├── terraform/
│       │   ├── mikrotik/
│       │   └── proxmox/
│       ├── bootstrap/
│       │   ├── rtr-home-main/
│       │   ├── hv-gamayun/
│       │   └── sbc-orangepi5/
│       ├── ansible/
│       │   └── inventory/
│       └── docs/
│
├── topology-tools/                          # LEGACY (migrate to topology-core)
│   └── ...
│
└── adr/
```

---

## Migration Plan: Topology v4 → v5

### Version Compatibility

| Artifact | v4 (current) | v5 (target) | Migration Path |
|----------|--------------|-------------|----------------|
| Topology YAML | `topology/L*.yaml` | `topology/home-lab/L*.yaml` | Move + add class_ref/object_ref |
| Validators | `topology-tools/scripts/validators/` | `topology-core/` + `topology-modules/` | Split by class/object |
| Generators | `topology-tools/scripts/generators/` | `topology-modules/{object}/generators/` | Move to modules |
| Schemas | `topology-tools/schemas/` | `topology-core/schemas/` + modules | Split by class/object |
| Templates | `topology-tools/templates/` | `topology-modules/{object}/generators/{type}/templates/` | Move to modules |

### Phase 0: Preparation (Current State Analysis)

**Objective:** Document current codebase for migration mapping.

**Tasks:**
- [ ] Inventory all validators in `topology-tools/scripts/validators/`
- [ ] Inventory all generators in `topology-tools/scripts/generators/`
- [ ] Map current schemas in `topology-tools/schemas/`
- [ ] Identify class-level vs object-level code in each file
- [ ] Create migration tracking document

**Current Code Mapping:**

```
topology-tools/scripts/validators/
├── checks/
│   ├── foundation.py      → class:router, class:hypervisor, class:sbc
│   ├── network.py         → class:network
│   ├── platform.py        → class:container, class:host_os
│   ├── references.py      → topology-core/engine/ (generic)
│   └── governance.py      → topology-core/engine/ (generic)
├── base.py                → topology-core/engine/validator.py
└── runner.py              → topology-core/engine/validator.py

topology-tools/scripts/generators/
├── terraform/
│   ├── mikrotik/          → topology-modules/mikrotik/generators/terraform/
│   └── proxmox/           → topology-modules/proxmox/generators/terraform/
├── bootstrap/
│   ├── mikrotik/          → topology-modules/mikrotik/generators/bootstrap/
│   ├── proxmox/           → topology-modules/proxmox/generators/bootstrap/
│   └── orangepi5/         → topology-modules/orangepi5/generators/bootstrap/
├── ansible/               → topology-modules/proxmox/generators/ansible/
├── docs/                  → topology-core/generators/docs/
└── common/
    ├── base.py            → topology-core/engine/generator.py
    └── ip_resolver_v2.py  → topology-core/engine/resolver.py

topology-tools/templates/
├── terraform/mikrotik/    → topology-modules/mikrotik/generators/terraform/templates/
├── terraform/proxmox/     → topology-modules/proxmox/generators/terraform/templates/
├── bootstrap/mikrotik/    → topology-modules/mikrotik/generators/bootstrap/templates/
├── bootstrap/proxmox/     → topology-modules/proxmox/generators/bootstrap/templates/
└── bootstrap/orangepi5/   → topology-modules/orangepi5/generators/bootstrap/templates/
```

**Deliverables:**
- `docs/migration/v5-inventory.md` — Current code inventory
- `docs/migration/v5-mapping.md` — Source → target mapping
- `docs/migration/v5-tracking.md` — Phase progress tracking

---

### Phase 1: Directory Scaffolding

**Objective:** Create new directory structure without moving code.

**Commands:**
```bash
# Create topology-core structure
mkdir -p topology-core/{engine,schemas,classes,cli,data,tests}
mkdir -p topology-core/classes/{router,hypervisor,sbc,host_os,container,network}
for class in router hypervisor sbc host_os container network; do
  mkdir -p topology-core/classes/$class/{schema,validators/{yaml,json}}
done

# Create topology-modules structure
mkdir -p topology-modules/{mikrotik,proxmox,orangepi5,debian,lxc}
for mod in mikrotik proxmox orangepi5 debian lxc; do
  mkdir -p topology-modules/$mod/{schema,validators/{yaml,json},generators,tests}
done
mkdir -p topology-modules/mikrotik/generators/{terraform,bootstrap}/templates
mkdir -p topology-modules/proxmox/generators/{terraform,bootstrap,ansible}/templates
mkdir -p topology-modules/orangepi5/generators/bootstrap/templates

# Create project topology structure
mkdir -p topology/home-lab/profiles
```

**Tasks:**
- [ ] Create `topology-core/` directory structure
- [ ] Create `topology-modules/` directory structure
- [ ] Create `topology/home-lab/` directory
- [ ] Add placeholder `manifest.yaml` in each class module
- [ ] Add placeholder `manifest.yaml` in each object module
- [ ] Add placeholder `objects.yaml` in each object module
- [ ] Add `project.yaml` in `topology/home-lab/`
- [ ] Add `__init__.py` files for Python packages

**Placeholder Files:**

```yaml
# topology-core/classes/router/manifest.yaml
id: router
version: "0.1.0"
type: class
status: placeholder
description: "Router class - to be implemented"
```

```yaml
# topology-modules/mikrotik/manifest.yaml
id: mikrotik
version: "0.1.0"
type: object
status: placeholder
implements: [router, switch]
description: "MikroTik module - to be implemented"
```

```yaml
# topology/home-lab/project.yaml
id: home-lab
version: "5.0.0"
topology_version: "5.0"
status: migration
previous_version: "4.0"
```

**Deliverables:**
- Empty directory structure with manifests
- No functional changes to existing code
- Both v4 and v5 structures coexist

**Verification:**
```bash
# Structure check
find topology-core -name "manifest.yaml" | wc -l  # Should be 6
find topology-modules -name "manifest.yaml" | wc -l  # Should be 5
test -f topology/home-lab/project.yaml && echo "OK"
```

---

### Phase 2: Engine Bootstrap

**Objective:** Implement minimal compilation engine that wraps existing validators.

**Tasks:**
- [ ] Extract loader from `topology_loader.py` → `topology-core/engine/loader.py`
- [ ] Implement `topology-core/engine/registry.py` (module discovery)
- [ ] Implement `topology-core/engine/diagnostics.py` (structured errors)
- [ ] Implement `topology-core/engine/validator.py` (orchestration)
- [ ] Implement `topology-core/cli/validate.py` (CLI wrapper)
- [ ] Add base schemas to `topology-core/schemas/`
- [ ] Create `topology-core/data/error-catalog.yaml`

**Key Files:**

```python
# topology-core/engine/loader.py
"""
Extract from topology-tools/topology_loader.py:
- load_topology()
- resolve_includes()
- merge_layers()
"""

# topology-core/engine/diagnostics.py
"""
New implementation:
- Diagnostic dataclass
- DiagnosticsReport class
- JSON/text formatters
"""

# topology-core/engine/registry.py
"""
New implementation:
- discover_class_modules()
- discover_object_modules()
- load_module_manifest()
- ModuleRegistry singleton
"""
```

**CLI Interface:**
```bash
# New v5 CLI (wraps existing validators initially)
python -m topology_core.cli.validate --project topology/home-lab

# Output: generated/home-lab/compiled/diagnostics.json
```

**Deliverables:**
- Working `topology-core validate` command
- Structured diagnostics output (JSON + text)
- Backward compatible with existing topology

**Verification:**
```bash
# Run new validator, compare with existing
python -m topology_core.cli.validate --project topology/home-lab > /tmp/v5-diag.json
python topology-tools/validate-topology.py > /tmp/v4-diag.txt
# Manual comparison of detected issues
```

---

### Phase 3: First Class Module (router)

**Objective:** Extract router class from existing validation code.

**Source Analysis:**
```
topology-tools/scripts/validators/checks/foundation.py
  └── FoundationDevicesCheck
      └── validate_device_type() — contains router logic

topology-tools/schemas/
  └── topology.schema.json — device schema with type: router
```

**Tasks:**
- [ ] Create `topology-core/classes/router/manifest.yaml`
- [ ] Create `topology-core/classes/router/capabilities.yaml`
- [ ] Create `topology-core/classes/router/schema/router.schema.yaml`
- [ ] Extract router validation → `classes/router/validators/yaml/router_validator.py`
- [ ] Extract router contract checks → `classes/router/validators/json/router_contract.py`
- [ ] Update `topology/home-lab/L1-foundation.yaml` to use `class_ref: router`
- [ ] Update engine registry to load router class
- [ ] Verify backward compatibility (both old and new fields work)

**Topology Update:**
```yaml
# topology/home-lab/L1-foundation.yaml
devices:
  - id: rtr-mikrotik-chateau
    type: router                    # v4 field (keep for compatibility)
    class_ref: router               # v5 field (add)
    implementation: mikrotik        # v4 field (keep for compatibility)
    # ... rest unchanged
```

**Deliverables:**
- Working router class module
- Updated topology with class_ref
- Both v4 and v5 fields supported

**Verification:**
```bash
# Validate with new class
python -m topology_core.cli.validate --project topology/home-lab
# Check router class loaded
grep "router" generated/home-lab/compiled/diagnostics.json
```

---

### Phase 4: First Object Module (mikrotik)

**Objective:** Extract MikroTik-specific code into self-contained module.

**Source Analysis:**
```
topology-tools/scripts/generators/terraform/mikrotik/
├── generator.py                    → generators/terraform/generator.py
├── resolvers.py                    → generators/terraform/resolvers.py (internal)
└── (uses templates/)

topology-tools/scripts/generators/bootstrap/mikrotik/
├── generator.py                    → generators/bootstrap/generator.py
└── (uses templates/)

topology-tools/templates/terraform/mikrotik/
└── *.tf.j2                         → generators/terraform/templates/

topology-tools/templates/bootstrap/mikrotik/
└── *.j2, *.rsc.j2                  → generators/bootstrap/templates/
```

**Tasks:**
- [ ] Create `topology-modules/mikrotik/manifest.yaml` (full)
- [ ] Create `topology-modules/mikrotik/objects.yaml` (chateau, chr, etc.)
- [ ] Create `topology-modules/mikrotik/schema/device.schema.yaml`
- [ ] Create `topology-modules/mikrotik/schema/network.schema.yaml`
- [ ] Move validators → `mikrotik/validators/`
- [ ] Move terraform generator → `mikrotik/generators/terraform/`
- [ ] Move terraform templates → `mikrotik/generators/terraform/templates/`
- [ ] Move bootstrap generator → `mikrotik/generators/bootstrap/`
- [ ] Move bootstrap templates → `mikrotik/generators/bootstrap/templates/`
- [ ] Update imports in moved files
- [ ] Update topology: `object_ref: mikrotik_chateau_lte7`
- [ ] Register module in engine registry
- [ ] Verify generated output parity with v4

**Topology Update:**
```yaml
# topology/home-lab/L1-foundation.yaml
devices:
  - id: rtr-mikrotik-chateau
    type: router
    class_ref: router
    implementation: mikrotik        # v4 field
    object_ref: mikrotik_chateau_lte7  # v5 field (add)
    # ... rest unchanged
```

**Deliverables:**
- Self-contained mikrotik module
- Terraform generation working from module
- Bootstrap generation working from module
- Generated output identical to v4

**Verification:**
```bash
# Generate with new module
python -m topology_core.cli.generate --project topology/home-lab --generators terraform

# Compare outputs
diff -r generated/home-lab/terraform/mikrotik/ /tmp/v4-terraform-mikrotik/
```

---

### Phase 5: Remaining Class Modules

**Objective:** Extract all class modules following router pattern.

**Class → Source Mapping:**

| Class | Source Validators | Source Schema |
|-------|-------------------|---------------|
| hypervisor | `checks/foundation.py` | `topology.schema.json` |
| sbc | `checks/foundation.py` | `topology.schema.json` |
| host_os | `checks/platform.py` | `topology.schema.json` |
| container | `checks/platform.py` | `topology.schema.json` |
| network | `checks/network.py` | `topology.schema.json` |

**Tasks:**
- [ ] Create `hypervisor` class module
  - [ ] manifest.yaml, capabilities.yaml
  - [ ] schema/hypervisor.schema.yaml
  - [ ] validators/yaml/, validators/json/
- [ ] Create `sbc` class module
- [ ] Create `host_os` class module
- [ ] Create `container` class module
- [ ] Create `network` class module
- [ ] Update all topology files with class_ref
- [ ] Update engine to load all classes
- [ ] Verify all class validations work

**Deliverables:**
- All 6 class modules operational
- All topology entities have class_ref

---

### Phase 6: Remaining Object Modules

**Objective:** Extract all object modules following mikrotik pattern.

**Object → Source Mapping:**

| Object | Generators | Templates |
|--------|------------|-----------|
| proxmox | terraform/, bootstrap/, ansible/ | terraform/proxmox/, bootstrap/proxmox/ |
| orangepi5 | bootstrap/ | bootstrap/orangepi5/ |
| debian | (cloud-init in proxmox) | — |
| lxc | (in proxmox generator) | — |

**Tasks:**
- [ ] Create `proxmox` object module
  - [ ] manifest.yaml, objects.yaml (proxmox_ve_8, proxmox_ve_9)
  - [ ] schema/device.schema.yaml, storage.schema.yaml, workload.schema.yaml
  - [ ] validators/
  - [ ] generators/terraform/, bootstrap/, ansible/
- [ ] Create `orangepi5` object module
  - [ ] manifest.yaml, objects.yaml
  - [ ] generators/bootstrap/
- [ ] Create `debian` object module
  - [ ] manifest.yaml, objects.yaml (debian_11, debian_12)
  - [ ] generators/cloud-init/ (extract from proxmox)
- [ ] Create `lxc` object module
  - [ ] manifest.yaml, objects.yaml (lxc_proxmox, lxc_incus)
  - [ ] Extract LXC-specific logic from proxmox
- [ ] Update all topology files with object_ref
- [ ] Verify all generators produce same output

**Deliverables:**
- All 5 object modules operational
- Full generation parity with v4

---

### Phase 7: Compiler Implementation

**Objective:** Implement full YAML → JSON compilation pipeline.

**Components:**
```
topology-core/engine/
├── merger.py      # Schema merging (base + class + object)
├── compiler.py    # YAML → JSON transformation
└── resolver.py    # Reference resolution (extract from ip_resolver_v2.py)
```

**Tasks:**
- [ ] Implement `merger.py` — combine schemas from loaded modules
- [ ] Implement `resolver.py` — resolve all ID references
- [ ] Implement `compiler.py` — full transformation pipeline
- [ ] Implement `topology-core/cli/compile.py`
- [ ] Generate `effective-topology.json`
- [ ] Update all generators to consume JSON instead of YAML
- [ ] Add JSON validators to all modules

**Pipeline:**
```
Input:  topology/home-lab/L*.yaml
        ↓
Load:   Merge YAML layers
        ↓
Schema: Merge base + class + object schemas
        ↓
Validate YAML: Run all YAML validators
        ↓
Compile: Resolve refs, apply defaults, transform
        ↓
Validate JSON: Run all JSON validators
        ↓
Output: generated/home-lab/compiled/effective-topology.json
        generated/home-lab/compiled/diagnostics.json
```

**Deliverables:**
- Working compilation pipeline
- `effective-topology.json` as canonical artifact
- All generators consume JSON

---

### Phase 8: Profile System

**Objective:** Implement profile overlays for environment variants.

**Tasks:**
- [ ] Implement profile loading in compiler
- [ ] Implement object substitution logic
- [ ] Implement override merging
- [ ] Add `--profile` flag to compile CLI
- [ ] Create `topology/home-lab/profiles/virtual.yaml`
- [ ] Add profile validation (class compatibility)
- [ ] Verify virtual profile produces valid output

**Profile Example:**
```yaml
# topology/home-lab/profiles/virtual.yaml
description: "Virtual environment for testing"

replacements:
  rtr-mikrotik-chateau:
    object_ref: mikrotik_chr

overrides:
  rtr-mikrotik-chateau:
    routeros_license: "free"

exclude:
  - sbc-orangepi5
```

**Deliverables:**
- Working profile system
- Virtual profile for testing
- Profile validation integrated

---

### Phase 9: Legacy Cleanup

**Objective:** Remove legacy code and finalize migration.

**Tasks:**
- [ ] Remove `topology-tools/scripts/generators/` (migrated)
- [ ] Remove `topology-tools/scripts/validators/checks/` (migrated)
- [ ] Remove `topology-tools/templates/` (migrated)
- [ ] Keep `topology-tools/` as thin wrapper calling `topology-core`
- [ ] Update `regenerate-all.py`:
  ```python
  # Old
  from scripts.generators.terraform.mikrotik import generator
  # New
  from topology_core.cli import build
  build.main(["--project", "topology/home-lab"])
  ```
- [ ] Update `deploy/Makefile`
- [ ] Move `topology/L*.yaml` → `topology/home-lab/L*.yaml`
- [ ] Update symlinks and paths
- [ ] Update CLAUDE.md with v5 structure
- [ ] Update all documentation

**Deliverables:**
- Clean codebase with no duplication
- Updated documentation
- CLAUDE.md reflects v5

---

### Phase 10: Stabilization

**Objective:** Ensure production readiness.

**Tasks:**
- [ ] Add unit tests for `topology-core/engine/`
- [ ] Add unit tests for each class module
- [ ] Add unit tests for each object module
- [ ] Add integration tests (full pipeline)
- [ ] Add output parity tests (v4 vs v5 generation)
- [ ] CI integration for validation
- [ ] Performance benchmarking
- [ ] Documentation review
- [ ] Create v5 migration guide

**Test Coverage Targets:**
| Component | Target |
|-----------|--------|
| topology-core/engine/ | 90% |
| topology-core/classes/ | 80% |
| topology-modules/ | 80% |

**Deliverables:**
- Test coverage > 80%
- CI pipeline updated
- Production-ready v5 system
- Migration guide published

---

### Migration Timeline

```
Phase 0-1:  Foundation          ████░░░░░░░░░░░░░░░░  10%
Phase 2:    Engine Bootstrap    ████████░░░░░░░░░░░░  20%
Phase 3-4:  First Modules       ████████████░░░░░░░░  40%
Phase 5-6:  All Modules         ████████████████░░░░  60%
Phase 7:    Compiler            ████████████████████  80%
Phase 8-10: Polish & Cleanup    ████████████████████  100%
```

### Version Update (End of Migration)

After Phase 9 completion, update topology version:

```yaml
# topology/home-lab/L0-meta.yaml
version: 5.0.0  # Updated from 4.0.0
metadata:
  # ...
  changelog:
    - version: 5.0.0
      date: 'YYYY-MM-DD'
      changes: |
        Topology v5 — Modular Class-Object-Instance Architecture:
        - Introduced Class→Object→Instance model
        - Separated topology-core (classes) and topology-modules (objects)
        - YAML→JSON compilation pipeline
        - Structured diagnostics for AI tooling
        - Project-based topology structure (topology/home-lab/)
        - Profile overlays for environment variants
```

---

### Rollback Strategy

At any phase, rollback is possible:
1. Legacy `topology-tools/` remains functional until Phase 9
2. Topology files support both v4 and v5 fields during migration
3. Generated outputs can be compared for parity verification

**Rollback command:**
```bash
# If v5 generation fails, use v4
python topology-tools/regenerate-all.py  # v4 (legacy)
# vs
python -m topology_core.cli.build --project topology/home-lab  # v5 (new)
```

---

## Consequences

### Positive

1. **Clear separation of concerns** — Class semantics, object implementations, and instance deployments are isolated
2. **Self-contained modules** — Each module owns its schema, validators, generators, and templates
3. **AI-friendly** — Structured JSON and diagnostics enable automated tooling
4. **Extensibility** — Adding new device types requires only new modules, no core changes
5. **Testability** — Modules can be tested in isolation
6. **Single repository** — No premature complexity of multi-repo management

### Negative

1. **Migration effort** — Significant refactoring of existing codebase
2. **Learning curve** — New concepts (class/object/instance, compilation pipeline)
3. **Temporary duplication** — Legacy and new code coexist during migration
4. **Schema complexity** — Merged schemas may be harder to debug

### Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| Migration breaks existing generation | Phase-by-phase migration with output parity tests |
| Schema merging conflicts | Clear precedence rules, validation of merged schema |
| Module discovery performance | Lazy loading, caching of module metadata |
| Over-abstraction | Start with minimal class/object split, add complexity when needed |

---

## Open Questions

1. **Schema format:** YAML schemas or JSON Schema? (Proposal: YAML for authoring, convert to JSON Schema for validation)
2. **Module versioning:** Semantic versioning for modules? (Proposal: Yes, but enforce only when multi-project)
3. **Generator plugin API:** How do generators declare their capabilities? (Proposal: via manifest.yaml)
4. **Capability inheritance:** Can objects add capabilities not in class? (Proposal: Yes, but warn)
5. **Cross-module references:** How to handle object depending on another object? (Proposal: explicit depends_on)

---

## References

### Superseded ADRs

- ADR 0058: Core Abstraction Layer and Device Module Architecture
- ADR 0059: Repository Split and Class-Object-Instance Module Contract
- ADR 0060: YAML-to-JSON Compiler and Diagnostics Contract
- ADR 0061: Base Repo with Versioned Class-Object-Instance and Test Profiles

### Related ADRs

- ADR 0025: Generator Protocol and CLI Base Class
- ADR 0028: Topology Tools Architecture Consolidation
- ADR 0046: Generators Architecture Refactoring

### External References

- [Terraform Provider Plugin Architecture](https://developer.hashicorp.com/terraform/plugin)
- [Ansible Collection Structure](https://docs.ansible.com/ansible/latest/dev_guide/developing_collections.html)
- [JSON Schema Specification](https://json-schema.org/specification.html)

---

## Appendix A: Validator Protocol

```python
# topology-core/engine/validator.py

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Literal, Optional, Any
from pathlib import Path

@dataclass
class SourceLocation:
    file: str
    line: int
    column: Optional[int] = None

@dataclass
class Autofix:
    action: Literal["replace", "insert", "delete"]
    value: Any

@dataclass
class Diagnostic:
    code: str
    severity: Literal["error", "warning", "info"]
    message: str
    path: str  # JSONPath
    stage: Optional[str] = None
    source: Optional[SourceLocation] = None
    hint: Optional[str] = None
    autofix: Optional[Autofix] = None

@dataclass
class ValidationContext:
    project_path: Path
    topology: dict
    merged_schema: dict
    loaded_modules: dict  # module_id -> module_manifest
    profile: Optional[str] = None

class YamlValidator(ABC):
    """Validates source YAML before compilation."""

    @abstractmethod
    def validate(self, yaml_data: dict, context: ValidationContext) -> List[Diagnostic]:
        """Run validation and return diagnostics."""
        pass

class JsonValidator(ABC):
    """Validates compiled JSON after compilation."""

    @abstractmethod
    def validate(self, json_data: dict, context: ValidationContext) -> List[Diagnostic]:
        """Run validation and return diagnostics."""
        pass
```

## Appendix B: Generator Protocol

```python
# topology-core/engine/generator.py

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import List

@dataclass
class GeneratorContext:
    topology: dict  # effective-topology.json content
    output_dir: Path
    module_path: Path
    templates_dir: Path
    project_config: dict

class ArtifactGenerator(ABC):
    """Base class for artifact generators."""

    @abstractmethod
    def get_type(self) -> str:
        """Return generator type: terraform, bootstrap, ansible, docs."""
        pass

    @abstractmethod
    def get_instances(self, topology: dict) -> List[str]:
        """Return instance IDs this generator handles."""
        pass

    @abstractmethod
    def generate(self, context: GeneratorContext) -> List[Path]:
        """Generate artifacts and return list of created files."""
        pass
```

## Appendix C: Example Module Implementation

```python
# topology-modules/mikrotik/generators/terraform/generator.py

from topology_core.engine.generator import ArtifactGenerator, GeneratorContext
from jinja2 import Environment, FileSystemLoader
from pathlib import Path
from typing import List

class MikrotikTerraformGenerator(ArtifactGenerator):

    def get_type(self) -> str:
        return "terraform"

    def get_instances(self, topology: dict) -> List[str]:
        return [
            d["id"] for d in topology.get("devices", [])
            if d.get("object_ref", "").startswith("mikrotik_")
        ]

    def generate(self, context: GeneratorContext) -> List[Path]:
        env = Environment(loader=FileSystemLoader(context.templates_dir))
        created = []

        data = self._extract_data(context.topology)
        output_path = context.output_dir / "terraform" / "mikrotik"
        output_path.mkdir(parents=True, exist_ok=True)

        for template_name in ["provider.tf.j2", "interfaces.tf.j2", "firewall.tf.j2"]:
            template = env.get_template(template_name)
            output_file = output_path / template_name.replace(".j2", "")
            output_file.write_text(template.render(**data))
            created.append(output_file)

        return created

    def _extract_data(self, topology: dict) -> dict:
        devices = [
            d for d in topology["devices"]
            if d.get("object_ref", "").startswith("mikrotik_")
        ]
        return {
            "devices": devices,
            "networks": topology.get("networks", []),
            "firewall_rules": self._extract_firewall(topology),
        }

    def _extract_firewall(self, topology: dict) -> list:
        # Extract firewall rules relevant to MikroTik
        ...
```
