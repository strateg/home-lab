# Plugin Unit Tests

This directory contains unit tests for individual plugins following ADR 0099 envelope semantics.

## Test Pattern

```python
from tests.helpers.plugin_execution import run_plugin_for_test, run_plugin_isolated

def test_plugin_produces_expected_output(tmp_path):
    plugin = MyValidatorPlugin("my.validator")
    ctx = PluginContext(
        topology_path="test.yaml",
        profile="test",
        model_lock={},
        compiled_json={"instances": {...}},
    )

    # Migration helper (wraps legacy execution context)
    result = run_plugin_for_test(plugin, ctx, Stage.VALIDATE)

    assert result.status == PluginStatus.SUCCESS
```

## Target Pattern (Full Envelope Isolation)

```python
def test_plugin_with_envelope_isolation(tmp_path):
    plugin = MyValidatorPlugin("my.validator")
    ctx = build_test_context(...)

    # Full envelope isolation (ADR 0097 compliant)
    result = run_plugin_isolated(plugin, ctx, Stage.VALIDATE)

    assert result.status == PluginStatus.SUCCESS
```

## Invariants (ADR 0099)

1. **Determinism** - Same input always produces same output
2. **Isolation** - Plugin cannot mutate shared state directly
3. **Ownership** - Only PipelineState commits published data
4. **Visibility** - Plugin sees only declared `consumes` dependencies
5. **Contract** - Manifest declares all inputs/outputs

## Migration Guide

Replace legacy pattern:
```python
# LEGACY (do not use in new tests)
ctx._set_execution_context(plugin.plugin_id, set())
result = plugin.execute(ctx, stage)
ctx._clear_execution_context()
```

With helper:
```python
# MODERN (ADR 0099 compliant)
from tests.helpers.plugin_execution import run_plugin_for_test
result = run_plugin_for_test(plugin, ctx, stage)
```
