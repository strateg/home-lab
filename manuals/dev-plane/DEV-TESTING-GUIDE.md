# Development Plane Testing Guide

Testing patterns, fixtures, and best practices.

---

## Test Structure

```
tests/
├── conftest.py                    # Shared fixtures
├── plugin_api/                    # Plugin API unit tests
│   ├── test_plugin_context.py
│   ├── test_plugin_result.py
│   └── test_diagnostic.py
├── plugin_contract/               # Plugin contract tests
│   ├── test_manifest_schema.py
│   ├── test_data_exchange.py
│   └── test_phase_handlers.py
├── plugin_integration/            # End-to-end tests
│   ├── test_bootstrap_generators.py
│   ├── test_terraform_proxmox_generator.py
│   ├── test_terraform_mikrotik_generator.py
│   └── test_framework_lock.py
├── plugin_regression/             # Regression tests
│   ├── test_parity_stage_order.py
│   └── test_parallel_profile_parity.py
├── orchestration/                 # Deploy orchestration tests
│   ├── test_bundle.py
│   ├── test_init_node.py
│   ├── test_runner.py
│   └── test_state.py
└── fixtures/                      # Test data
    ├── topology/
    ├── projections/
    └── golden/
```

---

## Running Tests

### All Tests

```bash
task test
# Output: 822 passed, 4 skipped
```

### By Category

```bash
# Plugin API (unit tests)
task test:plugin-api

# Plugin contract tests
task test:plugin-contract

# Integration tests
task test:plugin-integration

# Regression tests
task test:plugin-regression

# Orchestration tests
.venv/bin/python -m pytest tests/orchestration -v
```

### Single File

```bash
.venv/bin/python -m pytest tests/plugin_integration/test_bootstrap_generators.py -v
```

### Single Test

```bash
.venv/bin/python -m pytest tests/plugin_api/test_context.py::test_publish_subscribe -v
```

### With Options

```bash
# Verbose with durations
.venv/bin/python -m pytest tests -v --durations=10

# Stop on first failure
.venv/bin/python -m pytest tests -x

# Show local variables on failure
.venv/bin/python -m pytest tests -l

# Run tests matching pattern
.venv/bin/python -m pytest tests -k "mikrotik"
```

---

## Coverage

### Generate Coverage

```bash
.venv/bin/python -m pytest tests -v \
  --cov=topology-tools \
  --cov-report=html \
  --cov-report=term-missing
```

### View Coverage Report

```bash
# Terminal summary shown automatically
# HTML report at: htmlcov/index.html
```

### CI Coverage

```bash
task test:ci-coverage
# Generates: coverage.xml
```

---

## Writing Tests

### Plugin Unit Test

```python
# tests/plugin_api/test_my_validator.py
import pytest
from kernel.plugin_base import PluginContext, Stage, PluginStatus

from topology_tools.plugins.validators.my_validator import MyValidator


@pytest.fixture
def make_ctx():
    """Factory for test contexts."""
    def _make(compiled_json, config=None):
        return PluginContext(
            topology_path="test/topology.yaml",
            profile="production",
            model_lock={},
            compiled_json=compiled_json,
            config=config or {},
        )
    return _make


class TestMyValidator:
    def test_valid_input(self, make_ctx):
        ctx = make_ctx({"items": [{"name": "valid"}]})
        plugin = MyValidator("test.validator")
        result = plugin.execute(ctx, Stage.VALIDATE)

        assert result.status == PluginStatus.SUCCESS
        assert len(result.diagnostics) == 0

    def test_invalid_input(self, make_ctx):
        ctx = make_ctx({"items": [{"name": ""}]})
        plugin = MyValidator("test.validator")
        result = plugin.execute(ctx, Stage.VALIDATE)

        assert result.status == PluginStatus.FAILED
        assert result.diagnostics[0].code == "E5001"

    def test_empty_items(self, make_ctx):
        ctx = make_ctx({"items": []})
        plugin = MyValidator("test.validator")
        result = plugin.execute(ctx, Stage.VALIDATE)

        assert result.status == PluginStatus.SUCCESS
```

### Generator Integration Test

```python
# tests/plugin_integration/test_my_generator.py
import pytest
from pathlib import Path

from kernel.plugin_base import PluginContext, Stage
from topology_tools.plugins.generators.my_generator import MyGenerator


@pytest.fixture
def output_dir(tmp_path):
    """Temporary output directory."""
    out = tmp_path / "generated"
    out.mkdir()
    return out


@pytest.fixture
def ctx(output_dir):
    """Full context for generator tests."""
    return PluginContext(
        topology_path="test/topology.yaml",
        profile="production",
        model_lock={},
        compiled_json={
            "instances": [
                {"id": "node1", "name": "Node One"},
                {"id": "node2", "name": "Node Two"},
            ]
        },
        output_dir=str(output_dir),
        config={},
    )


def test_generates_files(ctx, output_dir):
    plugin = MyGenerator("test.generator")
    result = plugin.execute(ctx, Stage.GENERATE)

    assert result.status.value == "SUCCESS"

    # Check files were created
    assert (output_dir / "my-output" / "node1.tf").exists()
    assert (output_dir / "my-output" / "node2.tf").exists()


def test_file_content(ctx, output_dir):
    plugin = MyGenerator("test.generator")
    plugin.execute(ctx, Stage.GENERATE)

    content = (output_dir / "my-output" / "node1.tf").read_text()
    assert "Node One" in content
```

### Data Exchange Test

```python
# tests/plugin_contract/test_data_exchange.py
import pytest
from kernel.plugin_base import PluginContext, Stage


def test_publish_subscribe():
    ctx = PluginContext(
        topology_path="test",
        profile="production",
        compiled_json={},
    )

    # Simulate upstream plugin publishing
    ctx._current_plugin_id = "upstream.plugin"
    ctx._allowed_dependencies = set()
    ctx.publish("my_data", {"key": "value"})

    # Simulate downstream plugin subscribing
    ctx._current_plugin_id = "downstream.plugin"
    ctx._allowed_dependencies = {"upstream.plugin"}

    data = ctx.subscribe("upstream.plugin", "my_data")
    assert data == {"key": "value"}


def test_subscribe_missing_key():
    ctx = PluginContext(
        topology_path="test",
        profile="production",
        compiled_json={},
    )

    ctx._current_plugin_id = "downstream.plugin"
    ctx._allowed_dependencies = {"upstream.plugin"}

    # Should return None for missing key
    data = ctx.subscribe("upstream.plugin", "nonexistent")
    assert data is None
```

### Golden File Test

```python
# tests/plugin_integration/test_golden_output.py
import json
import pytest
from pathlib import Path


FIXTURES = Path(__file__).parent.parent / "fixtures"
GOLDEN = FIXTURES / "golden"


@pytest.fixture
def golden_projection():
    path = GOLDEN / "mikrotik_projection.golden.json"
    return json.loads(path.read_text())


def test_projection_matches_golden(ctx, golden_projection):
    plugin = MikrotikProjection("test.projection")
    result = plugin.execute(ctx, Stage.GENERATE)

    actual = ctx.subscribe(plugin.plugin_id, "projection")

    # Compare key fields
    assert actual["vlans"] == golden_projection["vlans"]
    assert actual["bridges"] == golden_projection["bridges"]
```

### Snapshot Test

```python
# tests/plugin_integration/test_snapshots.py
import pytest


def test_terraform_output_snapshot(ctx, output_dir, snapshot):
    """Test that generated Terraform matches snapshot."""
    plugin = TerraformGenerator("test.generator")
    plugin.execute(ctx, Stage.GENERATE)

    content = (output_dir / "terraform" / "main.tf").read_text()

    # Using pytest-snapshot or similar
    snapshot.assert_match(content, "main.tf")
```

---

## Fixtures

### Shared Fixtures (conftest.py)

```python
# tests/conftest.py
import pytest
from pathlib import Path


@pytest.fixture
def repo_root():
    return Path(__file__).parent.parent


@pytest.fixture
def fixtures_root():
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def topology_fixture(fixtures_root):
    return fixtures_root / "topology" / "test-topology.yaml"


@pytest.fixture
def tmp_generated(tmp_path):
    """Temporary generated directory."""
    generated = tmp_path / "generated" / "test-project"
    generated.mkdir(parents=True)
    return generated
```

### Context Factory

```python
# tests/conftest.py
import pytest
from kernel.plugin_base import PluginContext


@pytest.fixture
def make_plugin_context():
    """Factory for creating PluginContext with custom fields."""
    def _make(
        compiled_json=None,
        config=None,
        profile="production",
        output_dir=None,
        **kwargs
    ):
        return PluginContext(
            topology_path="test/topology.yaml",
            profile=profile,
            model_lock={},
            compiled_json=compiled_json or {},
            config=config or {},
            output_dir=output_dir or "/tmp/test",
            **kwargs
        )
    return _make
```

---

## Test Patterns

### Parametrized Tests

```python
import pytest


@pytest.mark.parametrize("input_name,expected_valid", [
    ("br-lan", True),
    ("bridge-servers", True),
    ("a" * 16, False),  # Too long
    ("", False),        # Empty
    ("123bridge", False),  # Starts with number
])
def test_bridge_name_validation(make_ctx, input_name, expected_valid):
    ctx = make_ctx({"bridges": [{"name": input_name}]})
    plugin = BridgeValidator("test.validator")
    result = plugin.execute(ctx, Stage.VALIDATE)

    if expected_valid:
        assert result.status == PluginStatus.SUCCESS
    else:
        assert result.status == PluginStatus.FAILED
```

### Test Markers

```python
import pytest


@pytest.mark.slow
def test_full_compilation():
    """Takes >5 seconds, marked as slow."""
    pass


@pytest.mark.integration
def test_with_real_files():
    """Requires real file system operations."""
    pass


@pytest.mark.skip(reason="Feature not implemented")
def test_future_feature():
    pass
```

### Expected Failures

```python
import pytest


@pytest.mark.xfail(reason="Known bug in upstream library")
def test_known_issue():
    pass
```

---

## Test Categories

### Plugin API Tests

Test individual plugin base classes and context API.

```bash
task test:plugin-api
```

Coverage target: 80%

### Plugin Contract Tests

Test manifest schema, data exchange, phase handlers.

```bash
task test:plugin-contract
```

Coverage target: 70%

### Plugin Integration Tests

End-to-end tests with real topology files.

```bash
task test:plugin-integration
```

### Plugin Regression Tests

Tests for known regressions and parity.

```bash
task test:plugin-regression
```

### Orchestration Tests

Tests for deploy bundle, init-node, runners.

```bash
.venv/bin/python -m pytest tests/orchestration -v
```

---

## Debugging Tests

### Print Debug Output

```python
def test_with_debug(ctx, capsys):
    plugin = MyPlugin("test")
    result = plugin.execute(ctx, Stage.VALIDATE)

    # Print debug info
    print(f"Result: {result}")
    print(f"Diagnostics: {result.diagnostics}")

    # capsys captures stdout/stderr
    captured = capsys.readouterr()
    # Use -s flag to see output: pytest -s
```

### Breakpoint Debugging

```python
def test_with_breakpoint(ctx):
    plugin = MyPlugin("test")

    # Drop into debugger
    breakpoint()

    result = plugin.execute(ctx, Stage.VALIDATE)
```

Run with: `pytest --pdb`

### Logging

```python
import logging


def test_with_logging(ctx, caplog):
    caplog.set_level(logging.DEBUG)

    plugin = MyPlugin("test")
    result = plugin.execute(ctx, Stage.VALIDATE)

    # Check log messages
    assert "Processing" in caplog.text
```

---

## Best Practices

### Do

- Use fixtures for common setup
- Test edge cases and error conditions
- Use parametrized tests for variations
- Check diagnostic codes, not just status
- Use temporary directories for generated files
- Clean up after tests (fixtures do this automatically)

### Don't

- Don't test implementation details
- Don't rely on test execution order
- Don't use hardcoded paths
- Don't skip cleanup on failure
- Don't test multiple concerns in one test

### Naming Convention

```python
def test_<what>_<condition>_<expected>():
    """Example: test_bridge_name_too_long_returns_error"""
    pass

def test_<method>_with_<scenario>():
    """Example: test_execute_with_empty_input"""
    pass
```

---

## CI Integration

### GitHub Actions

```yaml
# .github/workflows/test.yml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: pip install -r requirements.txt
      - run: task test
```

### Coverage Requirements

| Category | Minimum Coverage |
|----------|------------------|
| Plugin API | 80% |
| Plugin Contract | 70% |
| Integration | No minimum |

---

## Troubleshooting

### Test Not Found

```bash
# Ensure __init__.py exists
touch tests/__init__.py
touch tests/plugin_api/__init__.py
```

### Import Errors

```bash
# Run from repo root
cd /home/dmpr/workspaces/projects/home-lab
.venv/bin/python -m pytest tests -v
```

### Fixture Not Found

```bash
# Check conftest.py is in correct location
# Fixtures in tests/conftest.py are available to all tests
# Fixtures in tests/subdir/conftest.py are available to tests/subdir/*
```
