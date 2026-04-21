# Plugin Unit Tests (ADR 0099)

Use this layer for plugin business-logic tests that do **not** depend on the
full registry or mutable shared `PluginContext` behavior.

Preferred pattern:

- build stable plugin input fixtures;
- execute once through a local runner/helper;
- assert on returned diagnostics and published outputs;
- avoid direct inspection of pipeline-owned state.

If a test needs registry wiring, stage ordering, or cross-plugin publish/consume
behavior, place it under `tests/plugin_integration/` or `tests/runtime/`.
