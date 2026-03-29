"""Generator plugin that emits baseline Orange Pi bootstrap artifacts."""

from __future__ import annotations

from pathlib import Path

from kernel.plugin_base import PluginContext, PluginDiagnostic, PluginResult, Stage
from plugins.generators.base_generator import BaseGenerator
from plugins.generators.object_projection_loader import load_bootstrap_projection_module

# ADR0078 WP-003: Use shared helpers via dynamic loader
from plugins.generators.shared_helper_loader import load_bootstrap_helpers


class BootstrapOrangePiGenerator(BaseGenerator):
    """Emit baseline cloud-init bundle for Orange Pi nodes."""

    def template_root(self, ctx: PluginContext) -> Path:
        return self.object_template_root(ctx, object_id="orangepi")

    def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        diagnostics: list[PluginDiagnostic] = []
        bootstrap_helpers = load_bootstrap_helpers(ctx=ctx)
        get_bootstrap_files = bootstrap_helpers.get_bootstrap_files
        bootstrap_projections = load_bootstrap_projection_module(ctx=ctx)
        projection_error = bootstrap_projections.ProjectionError
        build_bootstrap_projection = bootstrap_projections.build_bootstrap_projection
        payload = ctx.compiled_json
        if not isinstance(payload, dict) or not payload:
            diagnostics.append(
                self.emit_diagnostic(
                    code="E3001",
                    severity="error",
                    stage=stage,
                    message="compiled_json is empty; cannot generate Orange Pi bootstrap artifacts.",
                    path="generator:bootstrap_orangepi",
                )
            )
            return self.make_result(diagnostics)

        try:
            projection = build_bootstrap_projection(payload)
        except projection_error as exc:
            diagnostics.append(
                self.emit_diagnostic(
                    code="E9601",
                    severity="error",
                    stage=stage,
                    message=f"failed to build bootstrap projection: {exc}",
                    path="generator:bootstrap_orangepi",
                )
            )
            return self.make_result(diagnostics)

        nodes = projection.get("orangepi_nodes", [])
        written: list[str] = []

        # Get file mappings from config (ADR0078 WP-003)
        bootstrap_files = get_bootstrap_files(ctx.config)

        for row in nodes:
            instance_id = str(row.get("instance_id", "")).strip()
            if not instance_id:
                continue
            cloud_init_root = self.resolve_output_path(ctx, "bootstrap", instance_id, "cloud-init")
            render_ctx = {"instance_id": instance_id}

            # Generate bootstrap files from config (ADR0078)
            for file_mapping in bootstrap_files:
                output_file = file_mapping.get("output_file", "")
                template = file_mapping.get("template", "")
                if not output_file or not template:
                    continue
                output_path = cloud_init_root / output_file
                self.write_text_atomic(
                    output_path,
                    self.render_template(ctx, template, render_ctx),
                )
                written.append(str(output_path))

        diagnostics.append(
            self.emit_diagnostic(
                code="I9601",
                severity="info",
                stage=stage,
                message=f"generated baseline Orange Pi bootstrap artifacts: nodes={len(nodes)}",
                path=str(self.resolve_output_path(ctx, "bootstrap")),
            )
        )
        self.publish_if_possible(ctx, "generated_dir", str(self.resolve_output_path(ctx, "bootstrap")))
        self.publish_if_possible(ctx, "generated_files", written)
        self.publish_if_possible(ctx, "bootstrap_orangepi_files", written)
        return self.make_result(
            diagnostics=diagnostics,
            output_data={"bootstrap_orangepi_files": written},
        )
