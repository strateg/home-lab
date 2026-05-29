# Plugin Test Requirements

**Date:** 2026-05-29
**Source:** Phase 2 Plugin System Development Plan
**Purpose:** Define test patterns, coverage requirements, and testing standards for plugins

---

## Overview

This guide documents the testing requirements for all plugins in the topology compiler. Following these patterns ensures consistent quality, maintainability, and reliability across the plugin ecosystem.

---

## Coverage Requirements

### Minimum Coverage Thresholds

| Metric | Threshold | Scope |
|--------|-----------|-------|
| Line Coverage | 75% | `topology-tools/` |
| Branch Coverage | 70% | Critical paths |
| Plugin Coverage | 100% | All plugins must have at least one test |

### Configuration

Coverage is enforced via `pyproject.toml`:

```toml
[tool.pytest.ini_options]
addopts = "-v --cov=topology-tools --cov-report=term-missing --cov-fail-under=75"
```

---

## Test Categories

### 1. Unit Tests (`tests/plugins/unit/`)

**Purpose:** Test plugin logic in isolation.

**Pattern:**

```python
from topology_tools.kernel.plugin_base import PluginContext, Stage, PluginStatus

def test_validator_detects_invalid_reference():
    plugin = MyValidator("test.validator", "1.x")
    ctx = _minimal_context(objects={"vm1": {"network_ref": "nonexistent"}})

    result = plugin.execute(ctx, Stage.VALIDATE)

    assert result.status == PluginStatus.FAILED
    assert any(d.code == "E2101" for d in result.diagnostics)
```

**Requirements:**
- Mock external dependencies
- Test both success and failure paths
- Verify diagnostic codes and messages

### 2. Contract Tests (`tests/plugin_contract/`)

**Purpose:** Verify plugin manifests and data contracts.

**Pattern:**

```python
def test_plugin_manifest_valid():
    """All plugin manifests must pass schema validation."""
    manifests = discover_manifests()
    for manifest in manifests:
        validate_manifest_schema(manifest)
```

**Coverage:**
- Manifest schema compliance
- `produces`/`consumes` contract validity
- `depends_on` target existence
- `config_schema` presence

### 3. Integration Tests (`tests/plugin_integration/`)

**Purpose:** Test plugin behavior with realistic context.

**Pattern:**

```python
from tests.helpers.plugin_execution import run_plugin_for_test, publish_for_test

def test_generator_produces_valid_terraform(tmp_path):
    plugin = TerraformGenerator("gen.terraform", "1.x")
    ctx = _full_context(objects=load_fixtures("proxmox"))

    # Publish dependencies
    publish_for_test(ctx, "compiler.instances", "instance_rows", instance_data)

    result = run_plugin_for_test(
        plugin, ctx, Stage.GENERATE,
        consumes_keys={"compiler.instances"}
    )

    assert result.status == PluginStatus.SUCCESS
    assert (tmp_path / "main.tf").exists()
```

**Requirements:**
- Use `run_plugin_for_test` helper
- Publish all required dependencies
- Verify output artifacts

### 4. Regression Tests (`tests/plugin_regression/`)

**Purpose:** Detect output drift and ensure determinism.

**Pattern:**

```python
@pytest.fixture(scope="session")
def generated_artifacts_root(tmp_path_factory):
    """Compile full topology for baseline comparison."""
    # See conftest.py for implementation
    ...

def test_terraform_output_stable(generated_artifacts_root):
    tf_dir = generated_artifacts_root / "terraform" / "proxmox"
    assert (tf_dir / "main.tf").exists()
    # Compare against baseline or verify structure
```

**Coverage:**
- Full pipeline execution
- Generated artifact validation
- Cross-run determinism

---

## Test Helpers

### Location: `tests/helpers/plugin_execution.py`

### Key Functions

```python
def run_plugin_for_test(
    plugin: PluginBase,
    ctx: PluginContext,
    stage: Stage,
    consumes_keys: set[str] | None = None,
) -> PluginResult:
    """Execute plugin with scoped context for testing."""
    ...

def publish_for_test(
    ctx: PluginContext,
    producer_plugin_id: str,
    key: str,
    value: Any,
) -> None:
    """Publish fixture payload to context data bus."""
    ...
```

### Usage Example

```python
from tests.helpers.plugin_execution import run_plugin_for_test, publish_for_test

def test_validator_with_dependencies():
    plugin = ReferenceValidator("validator.refs", "1.x")
    ctx = _context()

    # Setup: publish what the plugin consumes
    publish_for_test(ctx, "compiler.instances", "instance_rows", [...])

    # Execute
    result = run_plugin_for_test(
        plugin, ctx, Stage.VALIDATE,
        consumes_keys={"compiler.instances"}
    )

    # Assert
    assert result.status == PluginStatus.SUCCESS
```

---

## Required Tests Per Plugin Kind

### Discoverers

| Test | Required | Notes |
|------|----------|-------|
| Manifest loading | Yes | Verify discovery output |
| Error handling | Yes | Missing files, invalid YAML |
| Idempotency | Yes | Multiple runs produce same result |

### Compilers

| Test | Required | Notes |
|------|----------|-------|
| Transformation logic | Yes | Input -> output correctness |
| Edge cases | Yes | Empty input, missing optional fields |
| Published data shape | Yes | Verify `produces` contract |

### Validators

| Test | Required | Notes |
|------|----------|-------|
| Valid input passes | Yes | SUCCESS status |
| Invalid input fails | Yes | Correct error code |
| Diagnostic quality | Yes | Actionable messages with hints |
| All error codes covered | Yes | Each diagnostic code has a test |

### Generators

| Test | Required | Notes |
|------|----------|-------|
| Output file creation | Yes | Expected files exist |
| Output content validity | Yes | Parseable Terraform/Ansible/etc. |
| Determinism | Yes | Same input = same output |
| Template rendering | Yes | No Jinja2 errors |

### Assemblers

| Test | Required | Notes |
|------|----------|-------|
| Artifact assembly | Yes | Correct file placement |
| Metadata generation | Yes | Manifests, checksums |
| Incremental builds | If applicable | Changed scopes handling |

### Builders

| Test | Required | Notes |
|------|----------|-------|
| Package creation | Yes | Output exists and is valid |
| Signing (if applicable) | Yes | Signatures verify |
| Release manifest | Yes | Version, checksums present |

---

## Diagnostic Code Testing

Every diagnostic code used by a plugin must have at least one test that:
1. Triggers the specific diagnostic
2. Verifies the code, severity, and message

```python
def test_validator_emits_E2101_for_missing_reference():
    plugin = ReferenceValidator("validator.refs", "1.x")
    ctx = _context(objects={"vm1": {"network_ref": "missing_net"}})

    result = plugin.execute(ctx, Stage.VALIDATE)

    assert result.status == PluginStatus.FAILED
    diags = [d for d in result.diagnostics if d.code == "E2101"]
    assert len(diags) == 1
    assert "missing_net" in diags[0].message
```

---

## CI Integration

### Test Tasks

```bash
task test:plugin-api         # Unit tests for kernel API
task test:plugin-contract    # Contract validation tests
task test:plugin-integration # Integration tests
task test:plugin-regression  # Regression/parity tests
```

### Coverage Reports

```bash
task test:coverage-report    # Generate HTML coverage report
```

### CI Workflow

The `plugin-validation.yml` workflow runs:
1. Plugin API unit tests
2. Plugin contract tests
3. Plugin integration tests
4. Plugin regression tests (on PRs and main)

---

## Adding Tests for New Plugins

### Checklist

1. [ ] Create test file: `tests/plugin_integration/test_<plugin_name>.py`
2. [ ] Import test helpers: `from tests.helpers.plugin_execution import ...`
3. [ ] Write happy path test (SUCCESS status)
4. [ ] Write failure tests (each error code)
5. [ ] Verify `produces` contract if applicable
6. [ ] Verify determinism if generator
7. [ ] Add to CI if category-specific workflow exists

### Template

```python
#!/usr/bin/env python3
"""Tests for <plugin_id> plugin."""

from __future__ import annotations

from pathlib import Path

import pytest

from topology_tools.kernel.plugin_base import PluginContext, PluginStatus, Stage
from tests.helpers.plugin_execution import run_plugin_for_test, publish_for_test

# Import your plugin
from topology_tools.plugins.<family>.<module> import YourPlugin


def _context(**kwargs) -> PluginContext:
    """Create minimal test context."""
    return PluginContext(
        config=kwargs.get("config", {}),
        objects=kwargs.get("objects", {}),
        # ... other context fields
    )


class TestYourPlugin:
    """Test suite for YourPlugin."""

    def test_success_case(self):
        """Plugin succeeds with valid input."""
        plugin = YourPlugin("<plugin_id>", "1.x")
        ctx = _context(objects={...})

        result = run_plugin_for_test(plugin, ctx, Stage.VALIDATE)

        assert result.status == PluginStatus.SUCCESS

    def test_failure_with_E_code(self):
        """Plugin fails with specific error code."""
        plugin = YourPlugin("<plugin_id>", "1.x")
        ctx = _context(objects={...invalid...})

        result = run_plugin_for_test(plugin, ctx, Stage.VALIDATE)

        assert result.status == PluginStatus.FAILED
        assert any(d.code == "EXXXX" for d in result.diagnostics)
```

---

## Related Documents

- [PLUGIN_AUTHORING_GUIDE.md](../PLUGIN_AUTHORING_GUIDE.md) - Plugin development guide
- [PLUGIN-EXECUTION-MODES.md](./PLUGIN-EXECUTION-MODES.md) - Execution mode assignments
- [PLUGIN-NAMESPACE-CONVENTIONS.md](./PLUGIN-NAMESPACE-CONVENTIONS.md) - ID naming conventions
