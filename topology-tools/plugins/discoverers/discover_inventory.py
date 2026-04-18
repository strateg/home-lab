"""Discover-stage inventory publisher plugin."""

from __future__ import annotations

from typing import Any

from kernel.plugin_base import DiscovererPlugin, PluginContext, PluginDiagnostic, PluginResult, Stage


class DiscoverInventoryCompiler(DiscovererPlugin):
    """Publish discovered manifest/plugin inventory collected by orchestrator."""

    def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        diagnostics: list[PluginDiagnostic] = []
        manifests = ctx.config.get("discovered_plugin_manifests")
        manifest_list = [item for item in manifests if isinstance(item, str)] if isinstance(manifests, list) else []
        plugin_count = int(ctx.config.get("discovered_plugin_count", 0))
        payload: dict[str, Any] = {
            "manifest_paths": sorted(manifest_list),
            "manifest_count": len(manifest_list),
            "plugin_count": plugin_count,
        }
        ctx.publish("manifest_inventory", payload)
        return self.make_result(diagnostics=diagnostics, output_data=payload)

    def on_run(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        return self.execute(ctx, stage)
