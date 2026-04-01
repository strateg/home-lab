# Development Plane Command Reference

Quick reference for all development plane commands.

---

## Validation Commands

### Full Validation

```bash
task validate:v5-passthrough       # Recommended: explicit passthrough mode
task validate:default              # Uses V5_SECRETS_MODE env var
task validate:v5                   # Alias for default
```

### Targeted Validation

```bash
task validate:v5-layers            # Layer contract only
task validate:plugin-manifests     # Plugin manifest schema
task validate:workspace-layout     # Root workspace structure
```

### Code Quality

```bash
task validate:lint                 # black + isort check
task validate:typecheck            # mypy static analysis
task validate:pylint               # pylint checks
task validate:quality              # Aggregate quality gate
```

---

## Build Commands

### Full Build

```bash
task build:default                 # Clean + build all artifacts
```

### Build Variants

```bash
task build:v5-docs                 # Docs + diagrams (plain)
task build:v5-docs-icons           # Docs + diagrams with icon-nodes
task build:v5-docs-compat          # Docs + diagrams in compat mode
task build:v5-docs-validate        # Build + Mermaid render validation
```

### Cleanup

```bash
task build:clean-generated         # Remove generated artifacts
task build:clean-generated-dry     # Preview cleanup
```

### Terraform Variables

```bash
task build:tfvars-mikrotik         # Generate MikroTik tfvars
task build:tfvars-proxmox          # Generate Proxmox tfvars
task build:tfvars-all              # Generate all tfvars
task build:tfvars-cleanup          # Remove generated tfvars
```

---

## Test Commands

### Run Tests

```bash
task test                          # All tests (822+ tests)
task test:all                      # Alias for test
```

### Test Categories

```bash
task test:plugin-api               # Plugin API unit tests
task test:plugin-contract          # Plugin contract tests
task test:plugin-integration       # Integration tests
task test:plugin-regression        # Regression tests
task test:parity-v4-v5             # V4/V5 parity tests
```

### CI Coverage

```bash
task test:ci-coverage              # Tests with coverage report
```

### Direct pytest

```bash
# Specific file
.venv/bin/python -m pytest tests/plugin_integration/test_bootstrap_generators.py -v

# Specific test
.venv/bin/python -m pytest tests/plugin_api/test_context.py::test_publish -v

# With coverage
.venv/bin/python -m pytest tests -v --cov=topology-tools --cov-report=html

# Verbose with durations
.venv/bin/python -m pytest tests -v --durations=10
```

---

## Framework Commands

### Lock Management

```bash
task framework:lock-refresh              # Regenerate framework.lock
task framework:verify-lock               # Verify lock integrity
task framework:verify-lock-package-trust # Verify with package trust
```

### Compilation

```bash
task framework:compile                   # Compile with strict lock
```

### Release

```bash
task framework:release-preflight         # Pre-release checks
task framework:release-build -- FRAMEWORK_VERSION=1.0.8
task framework:release-candidate -- FRAMEWORK_VERSION=1.0.8
```

### Strict Gates

```bash
task framework:strict                    # Run all strict gates
task framework:rollback-rehearsal        # Test rollback path
task framework:compatibility-matrix      # Validate compatibility
task framework:audit-entrypoints         # Audit runtime entrypoints
```

### Cutover

```bash
task framework:cutover-readiness-quick   # Quick readiness check
task framework:cutover-readiness         # Full readiness report
```

---

## Compiler CLI

### Basic Usage

```bash
python topology-tools/compile-topology.py [OPTIONS]
```

### Common Options

| Option | Description |
|--------|-------------|
| `--topology PATH` | Entry point YAML |
| `--output-json PATH` | Compiled JSON output |
| `--artifacts-root PATH` | Generator output root |
| `--profile NAME` | Runtime profile |
| `--secrets-mode MODE` | passthrough/inject/strict |
| `--stages LIST` | Comma-separated stages |
| `--strict-model-lock` | Treat unpinned refs as errors |
| `--fail-on-warning` | Exit non-zero on warnings |
| `--parallel-plugins` | Enable parallel execution (default) |
| `--no-parallel-plugins` | Sequential execution |
| `--trace-execution` | Write execution trace |

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

# Debug (sequential)
python topology-tools/compile-topology.py \
  --no-parallel-plugins \
  --trace-execution
```

---

## Lane Orchestrator

### Direct Lane Commands

```bash
# Validate lane
python scripts/orchestration/lane.py validate-v5
python scripts/orchestration/lane.py validate-v5-passthrough
python scripts/orchestration/lane.py validate-v5-layers

# Build lane
python scripts/orchestration/lane.py build-v5

# Phase gates
python scripts/orchestration/lane.py phase1-gate
```

---

## Project Commands

### Project Initialization

```bash
# From distribution archive
task project:init-from-dist -- \
  PROJECT_ROOT=/path/to/new-project \
  PROJECT_ID=my-lab \
  FRAMEWORK_DIST_ZIP=/path/to/framework.zip \
  FRAMEWORK_DIST_VERSION=1.0.8

# From git submodule
task project:init -- \
  PROJECT_ROOT=/path/to/new-project \
  PROJECT_ID=my-lab \
  FRAMEWORK_SUBMODULE_URL=https://github.com/org/infra-topology-framework.git
```

---

## CI Commands

```bash
task ci:validate                   # CI validation lane
task ci:test                       # CI test lane
task ci:build                      # CI build lane
```

---

## Ansible Commands

```bash
task ansible:ping                  # Ping all hosts
task ansible:facts                 # Gather facts
task ansible:lint                  # Lint playbooks
```

---

## Terraform Commands

```bash
task terraform:init                # Initialize providers
task terraform:plan                # Plan changes
task terraform:apply               # Apply changes
task terraform:destroy             # Destroy resources
```

---

## Environment Variables

| Variable | Description |
|----------|-------------|
| `V5_SECRETS_MODE` | Secrets mode (passthrough/inject/strict) |
| `V5_DIAGRAM_ICON_MODE` | Diagram icon mode (icon-nodes/compat) |
| `PROJECT_ID` | Active project ID |
| `FRAMEWORK_VERSION` | Framework version for release |

---

## File Paths

### Source Files

| Path | Purpose |
|------|---------|
| `topology/topology.yaml` | Main entry point |
| `topology/class-modules/` | Class definitions |
| `topology/object-modules/` | Object definitions |
| `projects/<project>/topology/instances/` | Instance bindings |
| `projects/<project>/secrets/` | SOPS secrets |

### Generated Files

| Path | Purpose |
|------|---------|
| `generated/<project>/terraform/` | Terraform configs |
| `generated/<project>/ansible/` | Ansible inventory |
| `generated/<project>/bootstrap/` | Bootstrap packages |
| `generated/<project>/docs/` | Generated docs |
| `build/effective-topology.json` | Compiled model |
| `build/diagnostics/` | Diagnostic reports |

### Plugin Files

| Path | Purpose |
|------|---------|
| `topology-tools/plugins/plugins.yaml` | Base manifest |
| `topology/class-modules/**/plugins.yaml` | Class plugins |
| `topology/object-modules/**/plugins.yaml` | Object plugins |
| `projects/<project>/plugins/` | Project plugins |

---

## Exit Codes

| Code | Meaning |
|------|---------|
| `0` | Success |
| `1` | Error (validation/compilation failed) |
| `2` | Warning (with --fail-on-warning) |

---

## Diagnostic Files

| File | Purpose |
|------|---------|
| `build/diagnostics/report.json` | Machine-readable |
| `build/diagnostics/report.txt` | Human-readable |
| `build/diagnostics/plugin-execution-trace.json` | Execution trace |
| `build/diagnostics/plugin-published-keys.json` | Published data keys |
