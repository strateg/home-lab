# Development Plane Command Reference

Quick reference for all development plane commands.

---

## Validation Commands

### Full Validation

```bash
task validate:passthrough       # Recommended: explicit passthrough mode
task validate:default              # Uses V5_SECRETS_MODE env var
task validate:topology                   # Alias for default
```

### Targeted Validation

```bash
task validate:layers            # Layer contract only
task validate:plugin-manifests     # Plugin manifest schema
task validate:module-index         # module-index <-> filesystem consistency
task validate:module-growth        # ADR0082 growth report (JSON in build/diagnostics)
task validate:module-growth-gate   # Fail when active module manifests > 15
task validate:adr0047-trigger      # ADR0047 alerts/services trigger report
task validate:adr0047-trigger-gate # Fail when alerts>50 or services>30
task validate:adr0083-reactivation # ADR0083 reactivation readiness snapshot
task validate:adr0083-reactivation-gate # Fail when ADR0083 non-hardware readiness is not met
task validate:adr0083-reactivation-evidence # Render ADR0083 readiness evidence markdown
task validate:adr-consistency      # ADR register/file consistency check
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

## Topology Inspection Commands

```bash
task inspect:default                                            # Summary (compact)
task inspect:summary-json                                       # Summary JSON (schema_versioned)
task inspect:classes                                            # Class hierarchy tree
task inspect:inheritance                                        # Inheritance summary
task inspect:inheritance CLASS='class.router'                   # Focused class lineage
task inspect:inheritance-json [CLASS='class.router']            # Inheritance JSON
task inspect:objects                                            # Objects grouped by class (compact)
task inspect:objects-detailed                                   # Objects grouped by class (detailed rows)
task inspect:instances                                          # Instances grouped by layer (compact)
task inspect:instances-detailed                                 # Instances grouped by layer (detailed rows)
task inspect:search QUERY='mikrotik'                            # Regex search across instance payloads
task inspect:deps INSTANCE='rtr-mikrotik-chateau'               # Direct/incoming/transitive dependency view
task inspect:deps-typed-shadow INSTANCE='rtr-mikrotik-chateau'  # deps + non-authoritative typed relation shadow
task inspect:deps-json INSTANCE='rtr-mikrotik-chateau'          # Dependency JSON
task inspect:deps-json-typed-shadow INSTANCE='rtr-mikrotik-chateau' # Dependency JSON + typed shadow block
task inspect:deps-dot                                           # Export DOT graph to build/diagnostics/
task inspect:capability-packs                                   # class -> packs -> objects inspection
task inspect:capabilities                                       # Unified class/object/pack capability summary
task inspect:capabilities CLASS='class.router'                  # Focused class capability view
task inspect:capabilities OBJECT='obj.mikrotik.chateau_lte7_ax' # Focused object capability view
task inspect:capabilities-json [CLASS|OBJECT]                   # Capability JSON
```

### Optional Filters (instance-scoped commands)

The following commands support `LAYER` and `GROUP` filters:
- `inspect:default`, `inspect:summary-json`
- `inspect:instances`, `inspect:instances-detailed`
- `inspect:search`
- `inspect:deps`, `inspect:deps-typed-shadow`, `inspect:deps-json`, `inspect:deps-json-typed-shadow`
- `inspect:deps-dot`

Examples:

```bash
task inspect:default LAYER='L5' GROUP='services'
task inspect:summary-json LAYER='L5' GROUP='services'
task inspect:search QUERY='mikrotik' LAYER='L3' GROUP='network'
task inspect:deps-dot LAYER='L5' GROUP='services' OUTPUT='build/diagnostics/topology-instance-deps-l5-services.dot'
```

---

## Build Commands

### Full Build

```bash
task build:default                 # Clean + build all artifacts
```

### Build Variants

```bash
task build:docs                 # Docs + diagrams (plain)
task build:docs-icons           # Docs + diagrams with icon-nodes
task build:docs-compat          # Docs + diagrams in compat mode
task build:docs-validate        # Build + Mermaid render validation
```

### Cleanup

```bash
task clean                         # Root alias to build:clean-generated
task build:clean-generated         # Remove generated artifacts
task build:clean-generated-dry     # Preview cleanup
```

`task clean` / `task build:clean-generated` remove and recreate build outputs used by the dev plane:
- `generated/` (recreated)
- `generated-artifacts/`
- `build/diagnostics/`
- `build/test-artifacts/`
- `build/effective-topology.json`
- `build/effective-topology.yaml`
- `build/plugin-execution-trace.json`

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
task test:parity-v4-current             # V4/current parity tests
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
task framework:release-build FRAMEWORK_VERSION=1.0.8
task framework:release-candidate FRAMEWORK_VERSION=1.0.8
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
.venv/bin/python topology-tools/compile-topology.py [OPTIONS]
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
.venv/bin/python topology-tools/compile-topology.py \
  --stages discover,compile,validate \
  --strict-model-lock

# Full build with trace
.venv/bin/python topology-tools/compile-topology.py \
  --trace-execution \
  --strict-model-lock \
  --secrets-mode passthrough

# Debug (sequential)
.venv/bin/python topology-tools/compile-topology.py \
  --no-parallel-plugins \
  --trace-execution
```

---

## Lane Orchestrator

### Direct Lane Commands

```bash
# Validate lane
.venv/bin/python scripts/orchestration/lane.py validate-v5
.venv/bin/python scripts/orchestration/lane.py validate-v5-passthrough
.venv/bin/python scripts/orchestration/lane.py validate-v5-layers

# Build lane
python scripts/orchestration/lane.py build-v5

# Phase gates
python scripts/orchestration/lane.py phase1-gate
```

---

## MCP Helper Commands

### MikroTik MCP setup (Claude/Codex)

```bash
# Claude Code MCP registration
python scripts/orchestration/mcp/setup-mikrotik-mcp-claude.py --check
python scripts/orchestration/mcp/setup-mikrotik-mcp-claude.py

# Codex MCP registration
python scripts/orchestration/mcp/setup-mikrotik-mcp-codex.py --check
python scripts/orchestration/mcp/setup-mikrotik-mcp-codex.py

# Remove MCP registrations
python scripts/orchestration/mcp/setup-mikrotik-mcp-claude.py --remove
python scripts/orchestration/mcp/setup-mikrotik-mcp-codex.py --remove
```

Notes:
- Both scripts decrypt credentials from SOPS secrets.
- Codex registration uses `codex mcp add`; Claude registration writes to Claude config.

---

## Project Commands

### Project Initialization

```bash
# From distribution archive
task project:init-from-dist \
  PROJECT_ROOT=/path/to/new-project \
  PROJECT_ID=my-lab \
  FRAMEWORK_DIST_ZIP=/path/to/framework.zip \
  FRAMEWORK_DIST_VERSION=1.0.8

# From git submodule
task project:init \
  PROJECT_ROOT=/path/to/new-project \
  PROJECT_ID=my-lab \
  FRAMEWORK_SUBMODULE_URL=https://github.com/org/infra-topology-framework.git
```

---

## CI Commands

```bash
task ci:local                      # Local pre-push gate
task ci:local-with-legacy          # Local gate + legacy parity lanes
task ci:python-checks-core         # Core strict chain used by CI
task ci:lane                       # Lane validation core
task ci:topology-mainline          # Strict topology mainline lane
task ci:topology-parity-v4-current # Parity lane against archive v4 baseline
task ci:legacy-maintenance         # Legacy maintenance lane
```

`ci:_strict-validate-core` also runs:
- `task validate:adr-consistency`
- `task validate:module-growth`
- `task validate:adr0047-trigger`
- `task validate:adr0083-reactivation`

---

## Acceptance Commands

```bash
task acceptance:list               # List TUC scenarios
task acceptance:tests-all          # Run all acceptance pytest suites
task acceptance:test               # Run one test file/glob (set TUC_TEST=...)
task acceptance:test-case          # Run one pytest node (set PYTEST_NODE=...)
task acceptance:quality            # Run one scenario quality gate (set TUC_SLUG=...)
task acceptance:quality-all        # Run all quality gates
task acceptance:compile            # Compile artifacts into selected TUC folder
```

---

## Ansible Commands

```bash
task ansible:runtime               # Assemble runtime inventory
task ansible:runtime-inject        # Assemble runtime inventory with secrets injection
task ansible:syntax                # Syntax-check service playbooks
task ansible:check-site            # Run integrated check mode
task ansible:apply-site            # Apply integrated service playbook
```

---

## Terraform Commands

```bash
task terraform:validate-all        # fmt + validate for both lanes
task terraform:plan-proxmox        # Plan Proxmox lane
task terraform:plan-mikrotik       # Plan MikroTik lane
task terraform:init-proxmox-remote # Remote backend init (requires BACKEND_CONFIG)
task terraform:init-mikrotik-remote
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
