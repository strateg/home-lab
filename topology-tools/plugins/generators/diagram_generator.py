"""Diagram generator plugin - emits Mermaid topology diagrams (ADR 0005 / ADR 0027)."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from kernel.plugin_base import PluginContext, PluginDiagnostic, PluginResult, Stage
from plugins.generators.base_generator import BaseGenerator
from plugins.generators.projections import ProjectionError, build_diagram_projection
from plugins.icons.icon_manager import IconManager

# Supported icon modes (ADR 0027)
_ICON_MODE_ICON_NODES = "icon-nodes"
_ICON_MODE_COMPAT = "compat"
_ICON_MODE_NONE = "none"
_VALID_ICON_MODES = {_ICON_MODE_ICON_NODES, _ICON_MODE_COMPAT, _ICON_MODE_NONE}

_ICON_RUNTIME_HINTS = {
    _ICON_MODE_ICON_NODES: (
        "Icon packs required: register `si` (Simple Icons) and `mdi` (Material Design Icons) "
        "via Mermaid `registerIconPacks()` or MermaidChart CDN."
    ),
    _ICON_MODE_COMPAT: ("Compatibility mode: icon-compat labels embedded in standard Mermaid nodes."),
    _ICON_MODE_NONE: "",
}


class DiagramGenerator(BaseGenerator):
    """Emit Mermaid-based topology diagram pages from v5 compiled model (ADR 0027)."""

    @staticmethod
    def _collect_icon_ids(projection: dict[str, Any]) -> list[str]:
        icon_ids: set[str] = set()
        for key in ("devices", "trust_zones", "vlans", "bridges", "services", "lxc"):
            rows = projection.get(key)
            if not isinstance(rows, list):
                continue
            for row in rows:
                if not isinstance(row, dict):
                    continue
                icon = row.get("icon")
                if isinstance(icon, str) and ":" in icon:
                    icon_ids.add(icon)
        return sorted(icon_ids)

    @staticmethod
    def _icon_manager(ctx: PluginContext) -> IconManager:
        raw_roots = ctx.config.get("icon_pack_search_roots", [])
        roots: list[Path] = []
        if isinstance(raw_roots, str) and raw_roots.strip():
            roots = [Path(raw_roots.strip())]
        elif isinstance(raw_roots, list):
            roots = [Path(item) for item in raw_roots if isinstance(item, str) and item.strip()]
        return IconManager(search_roots=roots or None)

    def _icon_mode(self, ctx: PluginContext) -> str:
        # env var overrides plugin config (useful from task/CI without manifest edit)
        env_mode = os.environ.get("V5_DIAGRAM_ICON_MODE", "").strip().lower()
        mode = env_mode if env_mode else ctx.config.get("mermaid_icon_mode", _ICON_MODE_NONE)
        if mode not in _VALID_ICON_MODES:
            mode = _ICON_MODE_NONE
        return mode

    def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        diagnostics: list[PluginDiagnostic] = []
        payload = ctx.compiled_json
        if not isinstance(payload, dict) or not payload:
            diagnostics.append(
                self.emit_diagnostic(
                    code="E3001",
                    severity="error",
                    stage=stage,
                    message="compiled_json is empty; cannot generate diagram artifacts.",
                    path="generator:diagrams",
                )
            )
            return self.make_result(diagnostics)

        try:
            projection = build_diagram_projection(payload)
        except ProjectionError as exc:
            diagnostics.append(
                self.emit_diagnostic(
                    code="E9801",
                    severity="error",
                    stage=stage,
                    message=f"failed to build diagram projection: {exc}",
                    path="generator:diagrams",
                )
            )
            return self.make_result(diagnostics)

        icon_mode = self._icon_mode(ctx)
        use_icons = icon_mode == _ICON_MODE_ICON_NODES
        icon_runtime_hint = _ICON_RUNTIME_HINTS[icon_mode]

        diagrams_root = self.resolve_output_path(ctx, "docs", "diagrams")
        generated_files: list[str] = []

        template_ctx = {
            "projection": projection,
            "devices": projection.get("devices", []),
            "trust_zones": projection.get("trust_zones", []),
            "vlans": projection.get("vlans", []),
            "bridges": projection.get("bridges", []),
            "data_links": projection.get("data_links", []),
            "services": projection.get("services", []),
            "lxc": projection.get("lxc", []),
            "counts": projection.get("counts", {}),
            "use_mermaid_icons": use_icons,
            "icon_mode": icon_mode,
            "mermaid_icon_runtime_hint": icon_runtime_hint,
        }

        templates = (
            ("docs/diagrams/physical-topology.md.j2", "physical-topology.md"),
            ("docs/diagrams/network-topology.md.j2", "network-topology.md"),
            ("docs/diagrams/icon-legend.md.j2", "icon-legend.md"),
            ("docs/diagrams/diagrams-index.md.j2", "index.md"),
        )

        for template_name, output_name in templates:
            output_path = diagrams_root / output_name
            try:
                content = self.render_template(ctx, template_name, template_ctx)
                self.write_text_atomic(output_path, content)
                generated_files.append(str(output_path))
            except Exception as exc:
                diagnostics.append(
                    self.emit_diagnostic(
                        code="E9802",
                        severity="error",
                        stage=stage,
                        message=f"failed to render diagram template '{template_name}': {exc}",
                        path=f"generator:diagrams/{output_name}",
                    )
                )

        if icon_mode == _ICON_MODE_ICON_NODES:
            icon_manager = self._icon_manager(ctx)
            icon_ids = self._collect_icon_ids(projection)
            cache_result = icon_manager.cache_svg_assets(icon_ids, diagrams_root / "icons")
            manifest_path = str(cache_result.get("manifest_path", ""))
            if manifest_path:
                generated_files.append(manifest_path)
            unresolved_count = int(cache_result.get("unresolved_count", 0) or 0)
            fallback_count = int(cache_result.get("resolved_via_fallback", 0) or 0)
            diagnostics.append(
                self.emit_diagnostic(
                    code="I9802",
                    severity="info",
                    stage=stage,
                    message=(
                        "icon cache prepared for mermaid icon-nodes: "
                        f"resolved={cache_result.get('resolved_count', 0)}/"
                        f"{cache_result.get('icons_total', 0)} "
                        f"fallback={fallback_count} "
                        f"packs={','.join(cache_result.get('packs_loaded', [])) or 'none'}"
                    ),
                    path=str(diagrams_root / "icons"),
                )
            )
            if unresolved_count > 0:
                diagnostics.append(
                    self.emit_diagnostic(
                        code="W9803",
                        severity="warning",
                        stage=stage,
                        message=(
                            f"{unresolved_count} Mermaid icon IDs remain unresolved; "
                            "provide local Iconify packs under node_modules/@iconify-json "
                            "or extend icon mappings."
                        ),
                        path=str(diagrams_root / "icons"),
                    )
                )

        if generated_files:
            generated_files_path = diagrams_root / "_generated_files.txt"
            self.write_text_atomic(
                generated_files_path,
                "\n".join(sorted(generated_files)) + "\n",
            )
            generated_files.append(str(generated_files_path))

        counts = projection.get("counts", {})
        diagnostics.append(
            self.emit_diagnostic(
                code="I9801",
                severity="info",
                stage=stage,
                message=(
                    f"generated diagram artifacts: icon_mode={icon_mode} "
                    f"devices={counts.get('devices', 0)} "
                    f"trust_zones={counts.get('trust_zones', 0)} "
                    f"vlans={counts.get('vlans', 0)}"
                ),
                path=str(diagrams_root),
            )
        )
        self.publish_if_possible(ctx, "diagram_dir", str(diagrams_root))
        self.publish_if_possible(ctx, "generated_files", generated_files)
        self.publish_if_possible(ctx, "diagram_files", generated_files)

        return self.make_result(
            diagnostics=diagnostics,
            output_data={
                "diagram_dir": str(diagrams_root),
                "diagram_files": generated_files,
                "icon_mode": icon_mode,
            },
        )

    def on_post(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        return self.execute(ctx, stage)
