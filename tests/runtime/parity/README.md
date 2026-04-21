# Runtime Parity Tests

This directory contains parity tests that verify behavioral equivalence between:

1. Legacy direct execution (`_set_execution_context`)
2. Envelope-based execution (`PluginInputSnapshot` → `PluginExecutionEnvelope`)

## Purpose

Parity tests ensure that the migration from legacy to envelope-based execution
does not change observable behavior. They run the same plugin with the same
input through both paths and compare results.

## Test Pattern

```python
from tests.helpers.plugin_execution import run_plugin_for_test, run_plugin_isolated

def test_validator_parity():
    """Verify legacy and envelope paths produce identical results."""
    plugin = MyValidatorPlugin("my.validator")
    ctx = build_test_context(...)

    # Run through legacy path
    legacy_result = run_plugin_for_test(plugin, ctx.copy(), Stage.VALIDATE)

    # Run through envelope path
    envelope_result = run_plugin_isolated(plugin, ctx.copy(), Stage.VALIDATE)

    # Compare results
    assert legacy_result.status == envelope_result.status
    assert legacy_result.diagnostics == envelope_result.diagnostics
    assert legacy_result.output_data == envelope_result.output_data
```

## Parity Criteria

- Same `PluginStatus` returned
- Same diagnostics (codes, messages, severity)
- Same `output_data` structure and values
- Same published messages (keys, values, scopes)
- Same emitted events (topics, payloads)

## When to Add Parity Tests

1. Before migrating a plugin from legacy to envelope execution
2. When changing plugin execution semantics
3. When refactoring runtime internals

## ADR References

- ADR 0097: Actor-style dataflow execution model
- ADR 0099: Test architecture for snapshot/envelope/pipeline runtime
