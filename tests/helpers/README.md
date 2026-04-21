# Test Helpers (ADR 0099)

Shared helpers for transitional ADR0099 migration.

## Available helpers

- `run_plugin_for_test(plugin, ctx, stage, *, consumes_keys=None)`
  - wraps temporary execution-context setup for direct plugin execution tests.
- `publish_for_test(ctx, producer_plugin_id, key, value, *, consumes_keys=None)`
  - publishes fixture payloads under a producer identity without open-coded
    `ctx._set_execution_context(...)` / `ctx._clear_execution_context()`.

## Usage rule

Prefer these helpers in touched or new tests. If a test must still call
`_set_execution_context()` directly, keep the usage tightly scoped and document
why the helper is insufficient.
