"""Generator plugin that emits baseline MikroTik bootstrap artifacts."""

from __future__ import annotations

from pathlib import Path

from kernel.plugin_base import PluginContext, PluginDiagnostic, PluginResult, Stage
from plugins.generators.base_generator import BaseGenerator
from plugins.generators.object_projection_loader import load_bootstrap_projection_module

# ADR0078 WP-003: Use shared helpers from _shared/plugins/
from topology.object_modules._shared.plugins.bootstrap_helpers import get_bootstrap_files

_BOOTSTRAP_PROJECTIONS = load_bootstrap_projection_module()
ProjectionError = _BOOTSTRAP_PROJECTIONS.ProjectionError
build_bootstrap_projection = _BOOTSTRAP_PROJECTIONS.build_bootstrap_projection


class BootstrapMikroTikGenerator(BaseGenerator):
    """Emit baseline bootstrap bundle for MikroTik routers."""

    def template_root(self, ctx: PluginContext) -> Path:
        return self.object_template_root(ctx, object_id="mikrotik")

    def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        diagnostics: list[PluginDiagnostic] = []
        payload = ctx.compiled_json
        if not isinstance(payload, dict) or not payload:
            diagnostics.append(
                self.emit_diagnostic(
                    code="E3001",
                    severity="error",
                    stage=stage,
                    message="compiled_json is empty; cannot generate MikroTik bootstrap artifacts.",
                    path="generator:bootstrap_mikrotik",
                )
            )
            return self.make_result(diagnostics)

        try:
            projection = build_bootstrap_projection(payload)
        except ProjectionError as exc:
            diagnostics.append(
                self.emit_diagnostic(
                    code="E9501",
                    severity="error",
                    stage=stage,
                    message=f"failed to build bootstrap projection: {exc}",
                    path="generator:bootstrap_mikrotik",
                )
            )
            return self.make_result(diagnostics)

        nodes = projection.get("mikrotik_nodes", [])
        written: list[str] = []

        # Get file mappings from config (ADR0078 WP-003)
        bootstrap_files = get_bootstrap_files(ctx.config)

        for row in nodes:
            instance_id = str(row.get("instance_id", "")).strip()
            if not instance_id:
                continue
            node_root = self.resolve_output_path(ctx, "bootstrap", instance_id)
            render_ctx = {"instance_id": instance_id}

            # Generate bootstrap files from config (ADR0078)
            for file_mapping in bootstrap_files:
                output_file = file_mapping.get("output_file", "")
                template = file_mapping.get("template", "")
                if not output_file or not template:
                    continue
                output_path = node_root / output_file
                self.write_text_atomic(
                    output_path,
                    self.render_template(ctx, template, render_ctx),
                )
                written.append(str(output_path))

        diagnostics.append(
            self.emit_diagnostic(
                code="I9501",
                severity="info",
                stage=stage,
                message=f"generated baseline MikroTik bootstrap artifacts: nodes={len(nodes)}",
                path=str(self.resolve_output_path(ctx, "bootstrap")),
            )
        )
        self.publish_if_possible(ctx, "generated_dir", str(self.resolve_output_path(ctx, "bootstrap")))
        self.publish_if_possible(ctx, "generated_files", written)
        self.publish_if_possible(ctx, "bootstrap_mikrotik_files", written)
        return self.make_result(
            diagnostics=diagnostics,
            output_data={"bootstrap_mikrotik_files": written},
        )
