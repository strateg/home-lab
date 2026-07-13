#!/usr/bin/env python3
"""Run-phase dispatch compatibility test for base-manifest plugins.

Split verbatim from tests/test_plugin_registry.py in S9 of
docs/analysis/PLUGIN-REGISTRY-DECOMPOSITION-PLAN-2026-07-07.md.
Loads every base plugin through the facade (PluginLoader path)
and asserts execute_phase(RUN) dispatches to execute().
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import MethodType

V5_TOOLS = Path(__file__).resolve().parents[3] / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

from kernel import (  # noqa: E402
    PluginContext,
    PluginRegistry,
    PluginResult,
    PluginStatus,
)
from kernel.plugin_base import Phase  # noqa: E402


def test_base_manifest_run_phase_dispatch_uses_execute():
    """Run-phase dispatch must remain execute()-compatible for all base plugins."""
    manifest_path = V5_TOOLS / "plugins" / "plugins.yaml"
    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(manifest_path)
    # Get plugin IDs from registry (supports sharded manifests with includes)
    base_plugin_ids = list(registry.specs.keys())
    ctx = PluginContext(topology_path="test", profile="test-real", model_lock={})

    dispatched = 0
    for plugin_id in base_plugin_ids:
        spec = registry.specs[plugin_id]
        plugin = registry.load_plugin(plugin_id)
        stage = spec.stages[0]

        def _sentinel_execute(self, _ctx, _stage):
            return PluginResult.success(
                plugin_id=self.plugin_id,
                api_version=self.api_version,
                output_data={"dispatch": "execute", "plugin_id": self.plugin_id},
            )

        original_execute = plugin.execute
        plugin.execute = MethodType(_sentinel_execute, plugin)  # type: ignore[assignment]
        try:
            result = plugin.execute_phase(ctx, stage, Phase.RUN)
        finally:
            plugin.execute = original_execute  # type: ignore[assignment]

        assert result.status == PluginStatus.SUCCESS
        assert result.output_data == {"dispatch": "execute", "plugin_id": plugin_id}
        dispatched += 1

    assert dispatched >= 47
