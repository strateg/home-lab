"""Discover-stage manifest boundary enforcement plugin."""

from __future__ import annotations

from kernel.plugin_base import DiscovererPlugin, PluginContext, PluginDiagnostic, PluginResult, Stage


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
        project_plugins_root_cmp = project_plugins_root.casefold()

        leaked: list[str] = []
        for rel in manifest_list:
            normalized = rel.replace("\\", "/").strip("/")
            normalized_cmp = normalized.casefold()
            # project instances must remain data-only; plugin manifests here are forbidden.
            if "/topology/instances/" in f"/{normalized_cmp}/" or normalized_cmp.startswith("topology/instances/"):
                leaked.append(rel)
                continue
            if not normalized_cmp.startswith("projects/"):
                continue
            if project_plugins_root_cmp and (
                normalized_cmp == project_plugins_root_cmp or normalized_cmp.startswith(f"{project_plugins_root_cmp}/")
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
