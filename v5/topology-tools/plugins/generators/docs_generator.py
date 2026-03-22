"""Generator plugin that emits baseline docs artifacts from compiled model."""

from __future__ import annotations

from kernel.plugin_base import PluginContext, PluginDiagnostic, PluginResult, Stage
from plugins.generators.base_generator import BaseGenerator
from plugins.generators.projections import ProjectionError, build_docs_projection


class DocsGenerator(BaseGenerator):
    """Emit deterministic markdown docs from compiled model projection."""

    def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        diagnostics: list[PluginDiagnostic] = []
        payload = ctx.compiled_json
        if not isinstance(payload, dict) or not payload:
            diagnostics.append(
                self.emit_diagnostic(
                    code="E3001",
                    severity="error",
                    stage=stage,
                    message="compiled_json is empty; cannot generate docs artifacts.",
                    path="generator:docs",
                )
            )
            return self.make_result(diagnostics)

        try:
            projection = build_docs_projection(payload)
        except ProjectionError as exc:
            diagnostics.append(
                self.emit_diagnostic(
                    code="E9701",
                    severity="error",
                    stage=stage,
                    message=f"failed to build docs projection: {exc}",
                    path="generator:docs",
                )
            )
            return self.make_result(diagnostics)

        docs_root = self.resolve_output_path(ctx, "docs")
        generated_files: list[str] = []
        templates = (
            ("docs/overview.md.j2", "overview.md"),
            ("docs/devices.md.j2", "devices.md"),
            ("docs/services.md.j2", "services.md"),
        )
        template_ctx = {
            "projection": projection,
            "counts": projection.get("counts", {}),
            "devices": projection.get("devices", []),
            "services": projection.get("services", []),
            "groups": projection.get("groups", {}),
        }
        for template_name, output_name in templates:
            output_path = docs_root / output_name
            content = self.render_template(ctx, template_name, template_ctx)
            self.write_text_atomic(output_path, content)
            generated_files.append(str(output_path))

        generated_files_path = docs_root / "_generated_files.txt"
        generated_files_payload = "\n".join(sorted(generated_files)) + "\n"
        self.write_text_atomic(generated_files_path, generated_files_payload)
        generated_files.append(str(generated_files_path))

        diagnostics.append(
            self.emit_diagnostic(
                code="I9701",
                severity="info",
                stage=stage,
                message=(
                    "generated baseline docs artifacts: "
                    f"devices={projection['counts']['devices']} services={projection['counts']['services']}"
                ),
                path=str(docs_root),
            )
        )
        self.publish_if_possible(ctx, "generated_dir", str(docs_root))
        self.publish_if_possible(ctx, "generated_files", generated_files)
        self.publish_if_possible(ctx, "docs_files", generated_files)
        self.publish_if_possible(ctx, "docs_projection", projection)

        return self.make_result(
            diagnostics=diagnostics,
            output_data={
                "docs_dir": str(docs_root),
                "docs_files": generated_files,
            },
        )
