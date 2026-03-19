"""Generator plugin that emits baseline MikroTik bootstrap artifacts."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from kernel.plugin_base import PluginContext, PluginDiagnostic, PluginResult, Stage
from plugins.generators.base_generator import BaseGenerator
from plugins.generators.projections import ProjectionError, build_bootstrap_projection


class BootstrapMikroTikGenerator(BaseGenerator):
    """Emit baseline bootstrap bundle for MikroTik routers."""

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
        for row in nodes:
            instance_id = str(row.get("instance_id", "")).strip()
            if not instance_id:
                continue
            node_root = self.resolve_output_path(ctx, "bootstrap", instance_id)
            files = {
                node_root / "init-terraform.rsc": self.render_template(
                    ctx,
                    "bootstrap/mikrotik/init-terraform.rsc.j2",
                    {"instance_id": instance_id},
                ),
                node_root / "backup-restore-overrides.rsc": self.render_template(
                    ctx,
                    "bootstrap/mikrotik/backup-restore-overrides.rsc.j2",
                    {"instance_id": instance_id},
                ),
                node_root / "terraform.tfvars.example": self.render_template(
                    ctx,
                    "bootstrap/mikrotik/terraform.tfvars.example.j2",
                    {},
                ),
                node_root / "README.md": self.render_template(
                    ctx,
                    "bootstrap/mikrotik/readme.md.j2",
                    {"instance_id": instance_id},
                ),
            }
            for path, content in files.items():
                self.write_text_atomic(path, content)
                written.append(str(path))

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
