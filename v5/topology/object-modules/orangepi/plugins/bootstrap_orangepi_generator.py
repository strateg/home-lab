"""Generator plugin that emits baseline Orange Pi bootstrap artifacts."""

from __future__ import annotations

from pathlib import Path

from kernel.plugin_base import PluginContext, PluginDiagnostic, PluginResult, Stage
from plugins.generators.base_generator import BaseGenerator
from plugins.generators.object_projection_loader import load_bootstrap_projection_module

_BOOTSTRAP_PROJECTIONS = load_bootstrap_projection_module()
ProjectionError = _BOOTSTRAP_PROJECTIONS.ProjectionError
build_bootstrap_projection = _BOOTSTRAP_PROJECTIONS.build_bootstrap_projection


class BootstrapOrangePiGenerator(BaseGenerator):
    """Emit baseline cloud-init bundle for Orange Pi nodes."""

    def template_root(self, ctx: PluginContext) -> Path:
        return self.object_template_root(ctx, object_id="orangepi")

    def _get_bootstrap_files(self, ctx: PluginContext) -> list[dict]:
        """Get bootstrap file mappings from config (ADR0078)."""
        bootstrap_files = ctx.config.get("bootstrap_files")
        if isinstance(bootstrap_files, list):
            return bootstrap_files
        return []

    def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        diagnostics: list[PluginDiagnostic] = []
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
        except ProjectionError as exc:
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

        # Get file mappings from config (ADR0078)
        bootstrap_files = self._get_bootstrap_files(ctx)

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
