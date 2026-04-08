# Development Plane Operator Manual

**Version:** 1.0
**ADR Reference:** 0062, 0063, 0074, 0080, 0092, 0093, 0094
**Last Updated:** 2026-04-08

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Pipeline Stages](#pipeline-stages)
4. [Phases Within Stages](#phases-within-stages)
5. [Topology Authoring](#topology-authoring)
6. [Plugin Development](#plugin-development)
7. [Build Workflow](#build-workflow)
8. [Validation](#validation)
9. [Testing](#testing)
10. [Diagnostics](#diagnostics)
11. [Framework Management](#framework-management)

---

## Overview

Development Plane is the build-time layer for Infrastructure-as-Data topology compilation and artifact generation. It provides:

- **Plugin-based microkernel** - Extensible compiler with discover → compile → validate → generate → assemble → build pipeline (ADR 0063, 0080)
- **Class-Object-Instance model** - Three-level topology hierarchy (ADR 0062)
- **Generator architecture** - Terraform, Ansible, Bootstrap artifact generation (ADR 0074)
- **Smart artifact generation contracts** - projection → plan → report lifecycle (ADR 0092, ADR 0093)
- **Framework/Project separation** - Reusable framework with project-specific instances (ADR 0075)

### Key Principles

1. **Topology is source of truth** - Edit YAML, compile, generate, apply
2. **Plugin-first execution** - All transformations via plugin microkernel
3. **Layered boundaries** - Global → Class → Object → Instance
4. **Deterministic outputs** - Same inputs always produce same artifacts

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Source of Truth                               │
│  ┌─────────────┐   ┌─────────────┐   ┌─────────────┐               │
│  │   Class     │   │   Object    │   │  Instance   │               │
│  │  Modules    │   │  Modules    │   │  Bindings   │               │
│  │ topology/   │   │ topology/   │   │ projects/   │               │
│  │ class-      │   │ object-     │   │ <project>/  │               │
│  │ modules/    │   │ modules/    │   │ topology/   │               │
│  └─────────────┘   └─────────────┘   └─────────────┘               │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    Plugin Microkernel (ADR 0063)                     │
│  ┌────────┐  ┌────────┐  ┌────────┐  ┌────────┐  ┌────────┐       │
│  │discover│→ │compile │→ │validate│→ │generate│→ │assemble│→ build │
│  └────────┘  └────────┘  └────────┘  └────────┘  └────────┘       │
│                                                                      │
│  Each stage has phases: init → pre → run → post → verify → finalize │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      Generated Artifacts                             │
│  generated/<project>/                                                │
│  ├── terraform/proxmox/     # Proxmox IaC                           │
│  ├── terraform/mikrotik/    # MikroTik IaC                          │
│  ├── ansible/               # Ansible inventory & playbooks         │
│  ├── bootstrap/             # Node bootstrap packages               │
│  └── docs/                  # Generated documentation               │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Pipeline Stages

### Stage Order (ADR 0080)

```
discover → compile → validate → generate → assemble → build
```

| Stage | Purpose | Plugin Kind | Order Range |
|-------|---------|-------------|-------------|
| `discover` | Find and register plugin manifests | `discoverer` | 10–89 |
| `compile` | Transform raw YAML into compiled model | `compiler` | 30–89 |
| `validate` | Check model correctness | `validator_yaml`, `validator_json` | 90–189 |
| `generate` | Emit artifacts (Terraform, Ansible, docs) | `generator` | 190–399 |
| `assemble` | Build execution-root workspaces | `assembler` | 400–499 |
| `build` | Package, sign, verify release bundles | `builder` | 500–599 |

### Stage Selection

```bash
# Run all stages (default)
python topology-tools/compile-topology.py

# Run specific stages
python topology-tools/compile-topology.py --stages discover,compile,validate

# Skip generation (validation only)
python topology-tools/compile-topology.py --stages discover,compile,validate
```

### Stage Dependencies

```
discover ← compile ← validate ← generate ← assemble ← build
```

- `validate` requires `compile`
- `generate` requires `validate`
- `assemble` requires `generate`
- `build` requires `assemble`

---

## Phases Within Stages

### Phase Order

```
init → pre → run → post → verify → finalize
```

| Phase | Semantic | Typical Use |
|-------|----------|-------------|
| `init` | Load/prepare inputs | Module loaders, config resolvers |
| `pre` | Pre-conditions, governance checks | Schema guards, policy checks |
| `run` | Main business logic | Compilation, validation, generation |
| `post` | Post-processing, cross-cutting | Docs, diagrams, secondary outputs |
| `verify` | Quality gates | Integrity checks, contract validation |
| `finalize` | Summary and cleanup | Manifests, checksums, cleanup |

### Execution Order Within Phase

1. `depends_on` DAG (topological order)
2. `order` field (numeric tie-breaker)
3. Plugin `id` (lexical tie-breaker)

### Finalize Guarantee

`finalize` **always runs** for any started stage, even if earlier phase fails.

---

## Topology Authoring

### Directory Structure

```
topology/
├── topology.yaml              # Main entry point
├── framework.yaml             # Framework manifest
├── module-index.yaml          # Module discovery index
├── class-modules/             # Class definitions
│   ├── compute/
│   │   ├── cls.compute.lxc_container.yaml
│   │   └── cls.compute.proxmox_vm.yaml
│   ├── network/
│   │   ├── cls.network.vlan.yaml
│   │   └── cls.network.bridge.yaml
│   └── device/
│       └── cls.device.mikrotik_router.yaml
└── object-modules/            # Object definitions
    ├── proxmox/
    │   ├── obj.proxmox.gamayun.yaml
    │   └── plugins.yaml
    └── mikrotik/
        ├── obj.mikrotik.chateau_lte7_ax.yaml
        └── plugins.yaml

projects/home-lab/
├── project.yaml               # Project manifest
├── framework.lock.yaml        # Framework version lock
├── topology/instances/        # Instance bindings
│   ├── L1-foundation/
│   ├── L2-network/
│   ├── L3-transport/
│   ├── L4-platform/
│   ├── L5-application/
│   ├── L6-observability/
│   └── L7-operations/
├── secrets/                   # SOPS-encrypted secrets
└── deploy/                    # Deploy profile
```

### Class Definition Example

```yaml
# topology/class-modules/compute/cls.compute.lxc_container.yaml
class_id: cls.compute.lxc_container
version: "1.0.0"
description: "LXC container on Proxmox"

schema:
  type: object
  required: [vmid, hostname, cores, memory_mb]
  properties:
    vmid:
      type: integer
      minimum: 100
    hostname:
      type: string
      pattern: "^[a-z][a-z0-9-]*$"
    cores:
      type: integer
      minimum: 1
    memory_mb:
      type: integer
      minimum: 256
    disk_gb:
      type: integer
      default: 8

capabilities:
  - cap.compute
  - cap.container
```

### Object Definition Example

```yaml
# topology/object-modules/proxmox/obj.proxmox.gamayun.yaml
object_id: obj.proxmox.gamayun
class_ref: cls.device.proxmox_host
version: "1.0.0"
description: "Proxmox hypervisor on Dell XPS"

properties:
  management_ip: 10.0.99.1
  api_port: 8006
  storage_pools:
    - local-lvm
    - local

initialization_contract:
  version: "1.0.0"
  mechanism: unattended_install
  bootstrap:
    template: bootstrap/answer.toml.j2
```

### Instance Binding Example

```yaml
# projects/home-lab/topology/instances/L4-platform/compute/lxc-adguard.yaml
instance_id: lxc-adguard
object_ref: obj.proxmox.gamayun
class_ref: cls.compute.lxc_container

binding:
  vmid: 101
  hostname: adguard
  cores: 1
  memory_mb: 512
  disk_gb: 4

capabilities:
  - cap.dns
  - cap.adblock
```

### Topology Manifest (Entry Point)

```yaml
# topology/topology.yaml
schema_version: "1.0"

framework:
  class_modules_root: topology/class-modules
  object_modules_root: topology/object-modules
  model_lock: topology/model.lock.yaml
  layer_contract: topology/layer-contract.yaml
  capability_catalog: topology/capability-catalog.yaml
  capability_packs: topology/capability-packs.yaml

project:
  active: home-lab
  projects_root: projects
```

---

## Plugin Development

### Plugin Types

| Kind | Stage | Purpose |
|------|-------|---------|
| `discoverer` | discover | Find plugin manifests |
| `compiler` | compile | Transform YAML to compiled model |
| `validator_yaml` | validate | Validate raw YAML |
| `validator_json` | validate | Validate compiled JSON |
| `generator` | generate | Emit artifacts |
| `assembler` | assemble | Build workspaces |
| `builder` | build | Package releases |

### Quick Start

1. **Create plugin file:**

```python
# topology/object-modules/mikrotik/plugins/validators/bridge_check.py
from kernel.plugin_base import ValidatorJsonPlugin, PluginContext, PluginResult, Stage

class BridgeValidator(ValidatorJsonPlugin):
    def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        diagnostics = []
        for bridge in ctx.compiled_json.get("bridges", []):
            if len(bridge.get("name", "")) > 15:
                diagnostics.append(self.emit_diagnostic(
                    code="E5401", severity="error", stage=stage,
                    message=f"Bridge name too long: {bridge['name']}",
                    path=f"bridges.{bridge['name']}"
                ))
        return self.make_result(diagnostics)
```

2. **Register in manifest:**

```yaml
# topology/object-modules/mikrotik/plugins.yaml
schema_version: 1
plugins:
  - id: obj.mikrotik.validator.json.bridges
    kind: validator_json
    entry: plugins/validators/bridge_check.py:BridgeValidator
    api_version: "1.x"
    stages: [validate]
    phase: run
    order: 120
```

3. **Run:**

```bash
python topology-tools/compile-topology.py --profile production
```

### Data Exchange (Publish/Subscribe)

```python
# Publishing
ctx.publish("my_result_key", result_data)

# Subscribing
data = ctx.subscribe("upstream.plugin.id", "key_name")
```

Declare in manifest:
```yaml
produces:
  - key: my_result_key
    scope: pipeline_shared
consumes:
  - from_plugin: upstream.plugin.id
    key: key_name
    required: true
depends_on:
  - upstream.plugin.id
```

### Plugin Context Fields

| Field | Description |
|-------|-------------|
| `ctx.topology_path` | Path to topology.yaml |
| `ctx.profile` | Runtime profile |
| `ctx.compiled_json` | Compiled model |
| `ctx.output_dir` | Generator output root |
| `ctx.config` | Plugin configuration |
| `ctx.classes` | Class module metadata |
| `ctx.objects` | Object module metadata |

---

## Build Workflow

### Complete Build

```bash
# Clean and build all artifacts
task build:default
```

### Step-by-Step Build

```bash
# 1. Clean generated artifacts
task build:clean-generated

# 2. Run full pipeline
python topology-tools/compile-topology.py \
  --topology topology/topology.yaml \
  --strict-model-lock \
  --secrets-mode passthrough \
  --artifacts-root generated
```

### Build Variants

```bash
# Build with docs and diagrams
task build:docs

# Build with Mermaid icon-nodes
task build:docs-icons

# Build with Mermaid compat mode
task build:docs-compat

# Build and validate Mermaid rendering
task build:docs-validate
```

### Generated Artifact Structure

```
generated/home-lab/
├── terraform/
│   ├── proxmox/
│   │   ├── provider.tf
│   │   ├── variables.tf
│   │   ├── lxc_containers.tf
│   │   └── vm_instances.tf
│   └── mikrotik/
│       ├── provider.tf
│       ├── vlans.tf
│       ├── bridges.tf
│       └── firewall.tf
├── ansible/
│   ├── inventory.yaml
│   ├── group_vars/
│   └── playbooks/
├── bootstrap/
│   ├── rtr-mikrotik-chateau/
│   │   ├── init-terraform.rsc
│   │   └── backup-restore-overrides.rsc
│   ├── pve-gamayun/
│   │   ├── answer.toml
│   │   └── post-install-minimal.sh
│   └── sbc-orangepi5/
│       └── cloud-init/
└── docs/
    ├── topology-overview.md
    ├── diagrams/
    └── api-reference.md
```

---

## Validation

### Validate Topology

```bash
# Full validation with passthrough secrets
task validate:passthrough

# Default validation (uses V5_SECRETS_MODE env)
task validate:default

# Layer contract validation only
task validate:layers
```

### Validate Plugin Manifests

```bash
task validate:plugin-manifests
```

### Module Index Governance (ADR0082)

```bash
# Bidirectional consistency: module-index <-> filesystem manifests
task validate:module-index

# Non-blocking growth snapshot (writes build/diagnostics/module-growth.json)
task validate:module-growth

# Blocking gate: fail when active module manifests exceed threshold (>15)
task validate:module-growth-gate
```

### Observability Trigger Monitoring (ADR0047)

```bash
# Non-blocking trigger snapshot (alerts/services)
task validate:adr0047-trigger

# Blocking gate mode for governance pipelines
task validate:adr0047-trigger-gate
```

### ADR Governance Consistency

```bash
# Validate adr/REGISTER.md against ADR file metadata and links
task validate:adr-consistency

# ADR0083 reactivation readiness snapshot/gate (non-hardware checks)
task validate:adr0083-reactivation
task validate:adr0083-reactivation-gate
task validate:adr0083-reactivation-evidence
```

### Quality Gates

```bash
# Lint (black + isort)
task validate:lint

# Type check (mypy)
task validate:typecheck

# Full quality gate
task validate:quality
```

### Workspace Layout Validation

```bash
task validate:workspace-layout
```

---

## Testing

### Run All Tests

```bash
task test
# or
task test:all
```

### Test Categories

```bash
# Plugin API unit tests
task test:plugin-api

# Plugin contract tests
task test:plugin-contract

# Plugin integration tests
task test:plugin-integration

# Plugin regression tests
task test:plugin-regression

# V4/current parity tests
task test:parity-v4-current
```

### CI and Acceptance Lanes

```bash
# CI composed lanes
task ci:local
task ci:lane
task ci:topology-mainline
task ci:topology-parity-v4-current

# Acceptance scenarios
task acceptance:list
task acceptance:tests-all
task acceptance:quality-all
```

### Direct pytest

```bash
# Run specific test file
.venv/bin/python -m pytest tests/plugin_integration/test_bootstrap_generators.py -v

# Run with coverage
.venv/bin/python -m pytest tests -v --cov=topology-tools --cov-report=html

# Run specific test
.venv/bin/python -m pytest tests/plugin_api/test_plugin_context.py::test_publish_subscribe -v
```

### Test Directory Structure

```
tests/
├── plugin_api/           # Plugin API unit tests
├── plugin_contract/      # Plugin contract tests
├── plugin_integration/   # End-to-end integration
├── plugin_regression/    # Regression tests
├── orchestration/        # Deploy orchestration tests
├── fixtures/             # Test fixtures
│   ├── topology/
│   ├── projections/
│   └── golden/
└── conftest.py           # Shared fixtures
```

### Writing Tests

```python
# tests/plugin_integration/test_my_plugin.py
import pytest
from kernel.plugin_base import PluginContext, Stage

@pytest.fixture
def make_ctx():
    def _make(compiled_json, config=None):
        return PluginContext(
            topology_path="test",
            profile="production",
            compiled_json=compiled_json,
            config=config or {},
        )
    return _make

def test_valid_input(make_ctx):
    ctx = make_ctx({"bridges": [{"name": "br-lan"}]})
    plugin = MyPlugin("test.plugin")
    result = plugin.execute(ctx, Stage.VALIDATE)
    assert result.status.value == "SUCCESS"
```

---

## Diagnostics

### Diagnostic Output

```bash
# Diagnostics written to:
build/diagnostics/report.json    # Machine-readable
build/diagnostics/report.txt     # Human-readable
```

### Enable Execution Trace

```bash
python topology-tools/compile-topology.py --trace-execution
# Creates: build/diagnostics/plugin-execution-trace.json
```

### Diagnostic Severity Levels

| Severity | Exit Code | Meaning |
|----------|-----------|---------|
| `error` | 1 | Compilation failed |
| `warning` | 0 (or 2 with --fail-on-warning) | Issue but can proceed |
| `info` | 0 | Informational message |

### Error Code Ranges

| Range | Domain |
|-------|--------|
| `E000x–E199x` | Data format/structure |
| `E200x–E299x` | Reference/relationship |
| `E300x–E399x` | Configuration/contract |
| `E400x–E499x` | Kernel/runtime |
| `E500x–E799x` | Domain-specific validation |
| `E800x` | Discover stage |
| `E810x` | Assemble stage |
| `E820x` | Build stage |

### View Diagnostics

```bash
# Human-readable summary
cat build/diagnostics/report.txt

# Parse with jq
cat build/diagnostics/report.json | jq '.diagnostics[] | select(.severity == "error")'
```

---

## Framework Management

### Framework Lock

```bash
# Refresh framework lock
task framework:lock-refresh

# Verify framework lock
task framework:verify-lock

# Verify with package trust
task framework:verify-lock-package-trust
```

### Framework Compilation

```bash
# Compile with strict model lock
task framework:compile
```

### Framework Release

```bash
# Run release preflight
task framework:release-preflight

# Build framework distribution
task framework:release-build FRAMEWORK_VERSION=1.0.8

# Full release candidate
task framework:release-candidate FRAMEWORK_VERSION=1.0.8
```

### Cutover Readiness

```bash
# Quick readiness check
task framework:cutover-readiness-quick

# Full readiness report
task framework:cutover-readiness
```

---

## Compiler CLI Reference

### Basic Usage

```bash
python topology-tools/compile-topology.py [OPTIONS]
```

### Key Options

| Option | Default | Description |
|--------|---------|-------------|
| `--topology` | `topology/topology.yaml` | Entry point |
| `--output-json` | `build/effective-topology.json` | Compiled output |
| `--artifacts-root` | `generated` | Generator output root |
| `--profile` | `production` | Runtime profile |
| `--secrets-mode` | `passthrough` | Secrets handling |
| `--strict-model-lock` | off | Treat unpinned refs as errors |
| `--fail-on-warning` | off | Exit non-zero on warnings |
| `--stages` | all | Comma-separated stage list |
| `--parallel-plugins` | on | Parallel plugin execution |
| `--trace-execution` | off | Write execution trace |

### Examples

```bash
# Validation only
python topology-tools/compile-topology.py \
  --stages discover,compile,validate \
  --strict-model-lock

# Full build with trace
python topology-tools/compile-topology.py \
  --trace-execution \
  --strict-model-lock \
  --secrets-mode passthrough

# Sequential execution (debugging)
python topology-tools/compile-topology.py \
  --no-parallel-plugins
```

---

## Quick Reference

### Daily Development Workflow

```bash
# 1. Edit topology files
vim topology/object-modules/mikrotik/obj.mikrotik.chateau_lte7_ax.yaml

# 2. Validate changes
task validate:passthrough

# 3. Build artifacts
task build:default

# 4. Run tests
task test

# 5. Check diagnostics
cat build/diagnostics/report.txt
```

### Plugin Development Workflow

```bash
# 1. Create plugin
vim topology/object-modules/mikrotik/plugins/validators/my_check.py

# 2. Register in manifest
vim topology/object-modules/mikrotik/plugins.yaml

# 3. Validate manifest
task validate:plugin-manifests

# 4. Write tests
vim tests/plugin_integration/test_my_check.py

# 5. Run tests
task test:plugin-integration

# 6. Run full pipeline
task build:default
```

---

## See Also

- [DEV-COMMAND-REFERENCE.md](DEV-COMMAND-REFERENCE.md) - Quick command reference
- [DEV-TESTING-GUIDE.md](DEV-TESTING-GUIDE.md) - Testing patterns
- [DEV-TOPOLOGY-GUIDE.md](DEV-TOPOLOGY-GUIDE.md) - Topology authoring
- [PLUGIN_AUTHORING_GUIDE.md](../../docs/PLUGIN_AUTHORING_GUIDE.md) - Full plugin guide
- [ADR 0062](../adr/0062-class-object-instance-hierarchy.md) - Topology model
- [ADR 0063](../adr/0063-plugin-microkernel.md) - Plugin architecture
- [ADR 0074](../adr/0074-generator-architecture.md) - Generator architecture
- [ADR 0080](../adr/0080-stage-phase-lifecycle.md) - Stage/phase lifecycle
