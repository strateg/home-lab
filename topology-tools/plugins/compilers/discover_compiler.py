"""Discover-stage plugins for runtime inventory/preflight (ADR 0080)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from kernel.plugin_base import CompilerPlugin, PluginContext, PluginDiagnostic, PluginResult, Stage


class DiscoverInventoryCompiler(CompilerPlugin):
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
        try:
            ctx.publish("manifest_inventory", payload)
        except Exception:
            pass
        return self.make_result(diagnostics=diagnostics, output_data=payload)

    def on_run(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        return self.execute(ctx, stage)


class DiscoverCapabilityPreflightCompiler(CompilerPlugin):
    """Check capability contract files are present before compile/validate stages."""

    def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        diagnostics: list[PluginDiagnostic] = []
        catalog_path_raw = ctx.config.get("capability_catalog_path")
        packs_path_raw = ctx.config.get("capability_packs_path")
        missing: list[str] = []
        for raw in (catalog_path_raw, packs_path_raw):
            if isinstance(raw, str) and raw.strip():
                if not Path(raw).exists():
                    missing.append(raw)
        if missing:
            for path in missing:
                diagnostics.append(
                    self.emit_diagnostic(
                        code="E7107",
                        severity="error",
                        stage=stage,
                        message=f"capability contract path is missing: {path}",
                        path=path,
                    )
                )
        try:
            ctx.publish("capability_preflight_ok", len(missing) == 0)
        except Exception:
            pass
        return self.make_result(diagnostics=diagnostics)

    def on_verify(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        return self.execute(ctx, stage)
