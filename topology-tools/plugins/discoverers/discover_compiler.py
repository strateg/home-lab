"""Discover-stage plugins for runtime inventory/preflight (ADR 0080)."""

from __future__ import annotations

from pathlib import Path
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
        try:
            ctx.publish("manifest_inventory", payload)
        except Exception:
            pass
        return self.make_result(diagnostics=diagnostics, output_data=payload)

    def on_run(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        return self.execute(ctx, stage)


class DiscoverBoundaryCompiler(DiscovererPlugin):
    """Enforce discover-stage manifest boundary.

    Rules:
    1. Project-level plugin manifests are allowed only under configured project plugin root.
    2. Manifests under project instances data roots are always forbidden.
    """

    def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        diagnostics: list[PluginDiagnostic] = []
        manifests = ctx.config.get("discovered_plugin_manifests")
        manifest_list = [item for item in manifests if isinstance(item, str)] if isinstance(manifests, list) else []
        project_plugins_root_raw = ctx.config.get("project_plugins_root")
        project_plugins_root = (
            str(project_plugins_root_raw).replace("\\", "/").strip("/")
            if isinstance(project_plugins_root_raw, str) and str(project_plugins_root_raw).strip()
            else ""
        )

        leaked: list[str] = []
        for rel in manifest_list:
            normalized = rel.replace("\\", "/").strip("/")
            # project instances must remain data-only; plugin manifests here are forbidden.
            if "/topology/instances/" in f"/{normalized}/" or normalized.startswith("topology/instances/"):
                leaked.append(rel)
                continue
            if not normalized.startswith("projects/"):
                continue
            if project_plugins_root and (
                normalized == project_plugins_root or normalized.startswith(f"{project_plugins_root}/")
            ):
                continue
            leaked.append(rel)

        for rel in leaked:
            diagnostics.append(
                self.emit_diagnostic(
                    code="E3201",
                    severity="error",
                    stage=stage,
                    message=f"plugin manifest is outside allowed boundary: {rel}",
                    path=rel,
                )
            )
        try:
            ctx.publish("boundary_ok", len(leaked) == 0)
        except Exception:
            pass
        return self.make_result(diagnostics=diagnostics)

    def on_pre(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        return self.execute(ctx, stage)


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
        try:
            ctx.publish("capability_preflight_ok", len(missing) == 0)
        except Exception:
            pass
        return self.make_result(diagnostics=diagnostics)

    def on_verify(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        return self.execute(ctx, stage)
