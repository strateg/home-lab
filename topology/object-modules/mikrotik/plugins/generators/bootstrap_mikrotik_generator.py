"""Generator plugin that emits baseline MikroTik bootstrap artifacts."""

from __future__ import annotations

from pathlib import Path

from kernel.plugin_base import PluginContext, PluginDiagnostic, PluginResult, Stage
from plugins.generators.base_generator import BaseGenerator
from plugins.generators.object_projection_loader import load_bootstrap_projection_module

# ADR0078 WP-003: Use shared helpers via dynamic loader
from plugins.generators.shared_helper_loader import load_bootstrap_helpers


class BootstrapMikroTikGenerator(BaseGenerator):
    """Emit baseline bootstrap bundle for MikroTik routers."""

    def template_root(self, ctx: PluginContext) -> Path:
        return self.object_template_root(ctx, object_id="mikrotik")

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
                    message="compiled_json is empty; cannot generate MikroTik bootstrap artifacts.",
                    path="generator:bootstrap_mikrotik",
                )
            )
            return self.make_result(diagnostics)

        try:
            projection = build_bootstrap_projection(payload)
        except projection_error as exc:
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
            render_ctx = {
                "instance_id": instance_id,
                "node": row,
                "initialization_contract": self._resolve_initialization_contract(row),
            }

            # Generate bootstrap files from config (ADR0078)
            for file_mapping in bootstrap_files:
                output_file = file_mapping.get("output_file", "")
                template = str(file_mapping.get("template", "")).strip()
                if output_file == "init-terraform.rsc":
                    template = self._resolve_contract_template(row=row, default_template=template)
                if not output_file or not template:
                    continue
                output_path = node_root / output_file
                try:
                    rendered = self.render_template(ctx, template, render_ctx)
                except Exception as exc:
                    diagnostics.append(
                        self.emit_diagnostic(
                            code="E9502",
                            severity="error",
                            stage=stage,
                            message=(
                                f"failed to render bootstrap template '{template}' " f"for node '{instance_id}': {exc}"
                            ),
                            path=f"generator:bootstrap_mikrotik:{instance_id}",
                        )
                    )
                    return self.make_result(diagnostics)
                self.write_text_atomic(output_path, rendered)
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

    @staticmethod
    def _resolve_initialization_contract(row: dict) -> dict:
        obj = row.get("object")
        if not isinstance(obj, dict):
            return {}
        contract = obj.get("initialization_contract")
        if not isinstance(contract, dict):
            return {}
        return contract

    def _resolve_contract_template(self, *, row: dict, default_template: str) -> str:
        contract = self._resolve_initialization_contract(row)
        bootstrap = contract.get("bootstrap")
        if not isinstance(bootstrap, dict):
            return default_template
        template = bootstrap.get("template")
        if not isinstance(template, str):
            return default_template
        resolved = template.strip()
        return resolved or default_template
