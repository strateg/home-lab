"""Discover-stage manifest loader plugin."""

from __future__ import annotations

from typing import Any

from kernel.plugin_base import DiscovererPlugin, PluginContext, PluginDiagnostic, PluginResult, Stage


class DiscoverManifestLoaderCompiler(DiscovererPlugin):
    """Load module-level plugin manifests during discover/init."""

    def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        diagnostics: list[PluginDiagnostic] = []
        loader = ctx.config.get("discover_load_module_manifests")
        if not callable(loader):
            diagnostics.append(
                self.emit_diagnostic(
                    code="E4001",
                    severity="error",
                    stage=stage,
                    message="discover manifest loader callback is not configured.",
                    path="pipeline:discover_load_module_manifests",
                )
            )
            return self.make_result(diagnostics=diagnostics)

        try:
            summary = loader()
        except Exception as exc:
            diagnostics.append(
                self.emit_diagnostic(
                    code="E4001",
                    severity="error",
                    stage=stage,
                    message=f"discover manifest loader execution failed: {exc}",
                    path="pipeline:discover_load_module_manifests",
                )
            )
            return self.make_result(diagnostics=diagnostics)

        if not isinstance(summary, dict):
            diagnostics.append(
                self.emit_diagnostic(
                    code="E4001",
                    severity="error",
                    stage=stage,
                    message="discover manifest loader returned invalid payload.",
                    path="pipeline:discover_load_module_manifests",
                )
            )
            return self.make_result(diagnostics=diagnostics)

        discovered = summary.get("discovered_manifests")
        discovered_paths = (
            [item for item in discovered if isinstance(item, str)] if isinstance(discovered, list) else []
        )
        plugin_count = summary.get("loaded_plugin_count")
        if isinstance(plugin_count, int):
            ctx.config["discovered_plugin_count"] = plugin_count
        if discovered_paths:
            ctx.config["discovered_plugin_manifests"] = discovered_paths

        errors = summary.get("errors")
        for item in errors if isinstance(errors, list) else []:
            if not isinstance(item, str) or not item:
                continue
            diagnostics.append(
                self.emit_diagnostic(
                    code="E4001",
                    severity="error",
                    stage=stage,
                    message=f"discover manifest load error: {item}",
                    path="discover:module-manifests",
                )
            )

        payload: dict[str, Any] = {
            "module_manifest_count": int(summary.get("module_manifest_count", 0)),
            "loaded_plugin_count": int(summary.get("loaded_plugin_count", 0)),
            "discovered_manifests": discovered_paths,
        }
        diagnostics.append(
            self.emit_diagnostic(
                code="I4001",
                severity="info",
                stage=stage,
                message=(
                    "Plugin manifests loaded via discover bootstrap: "
                    f"plugins={payload['loaded_plugin_count']} "
                    f"manifests={len(discovered_paths)} "
                    f"module_manifests={payload['module_manifest_count']}"
                ),
                path="discover:module-manifests",
            )
        )
        try:
            ctx.publish("manifest_loader_summary", payload)
        except Exception:
            pass
        return self.make_result(diagnostics=diagnostics, output_data=payload)

    def on_init(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        return self.execute(ctx, stage)
