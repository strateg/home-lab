"""Discover-stage capability contract preflight plugin."""

from __future__ import annotations

from pathlib import Path

from kernel.plugin_base import DiscovererPlugin, PluginContext, PluginDiagnostic, PluginResult, Stage


class DiscoverCapabilityPreflightCompiler(DiscovererPlugin):
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
        ctx.publish("capability_preflight_ok", len(missing) == 0)
        return self.make_result(diagnostics=diagnostics)

    def on_verify(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        return self.execute(ctx, stage)
