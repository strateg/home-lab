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
        raw = ctx.config.get("generator_templates_root")
        if isinstance(raw, str) and raw.strip():
            return Path(raw)

        candidates: list[Path] = []
        object_modules_root_raw = ctx.config.get("object_modules_root")
        if isinstance(object_modules_root_raw, str) and object_modules_root_raw.strip():
            candidates.append(Path(object_modules_root_raw.strip()) / "orangepi" / "templates")
        topology_path_raw = getattr(ctx, "topology_path", None)
        if isinstance(topology_path_raw, str) and topology_path_raw.strip():
            candidates.append(Path(topology_path_raw.strip()).parent / "object-modules" / "orangepi" / "templates")

        for candidate in candidates:
            if candidate.exists():
                return candidate
        return super().template_root(ctx)

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
        for row in nodes:
            instance_id = str(row.get("instance_id", "")).strip()
            if not instance_id:
                continue
            cloud_init_root = self.resolve_output_path(ctx, "bootstrap", instance_id, "cloud-init")
            files = {
                cloud_init_root / "user-data.example": self.render_template(
                    ctx,
                    "bootstrap/user-data.example.j2",
                    {"instance_id": instance_id},
                ),
                cloud_init_root / "meta-data": self.render_template(
                    ctx,
                    "bootstrap/meta-data.j2",
                    {"instance_id": instance_id},
                ),
                cloud_init_root / "README.md": self.render_template(
                    ctx,
                    "bootstrap/readme.md.j2",
                    {"instance_id": instance_id},
                ),
            }
            for path, content in files.items():
                self.write_text_atomic(path, content)
                written.append(str(path))

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
