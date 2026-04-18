"""Generator plugin that emits baseline Orange Pi bootstrap artifacts."""

from __future__ import annotations

from pathlib import Path

from kernel.plugin_base import PluginContext, PluginDiagnostic, PluginResult, Stage
from plugins.generators.artifact_contract import (
    build_artifact_plan,
    build_generation_report,
    build_planned_output,
    compute_obsolete_entries,
    validate_contract_payloads,
    write_contract_artifacts,
)
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
        planned_outputs: list[dict[str, object]] = []
        ownership_roots: set[str] = set()
        out_root = self.resolve_output_path(ctx, "bootstrap")

        # Get file mappings from config (ADR0078 WP-003)
        bootstrap_files = get_bootstrap_files(ctx.config)

        for row in nodes:
            instance_id = str(row.get("instance_id", "")).strip()
            if not instance_id:
                continue
            cloud_init_root = self.resolve_output_path(ctx, "bootstrap", instance_id, "cloud-init")
            ownership_roots.add(str(cloud_init_root.resolve()))
            render_ctx = {"instance_id": instance_id}

            # Generate bootstrap files from config (ADR0078)
            for file_mapping in bootstrap_files:
                output_file = file_mapping.get("output_file", "")
                template = file_mapping.get("template", "")
                if not output_file or not template:
                    continue
                output_path = cloud_init_root / output_file
                planned_outputs.append(
                    build_planned_output(
                        path=str(output_path),
                        template=str(template),
                        reason="base-family",
                    )
                )
                self.write_text_atomic(
                    output_path,
                    self.render_template(ctx, template, render_ctx),
                )
                written.append(str(output_path))

        obsolete_entries, obsolete_errors = compute_obsolete_entries(
            ctx=ctx,
            plugin_id=self.plugin_id,
            output_root=out_root,
            planned_outputs=planned_outputs,
        )
        if obsolete_errors:
            for message in obsolete_errors:
                diagnostics.append(
                    self.emit_diagnostic(
                        code="E9602",
                        severity="error",
                        stage=stage,
                        message=message,
                        path="generator:bootstrap_orangepi:obsolete",
                    )
                )
            return self.make_result(diagnostics=diagnostics)

        artifact_family = "bootstrap.orangepi"
        artifact_plan = build_artifact_plan(
            plugin_id=self.plugin_id,
            artifact_family=artifact_family,
            planned_outputs=planned_outputs,
            projection_version="1.0",
            ir_version="1.0",
            obsolete_candidates=obsolete_entries,
            validation_profiles=[ctx.profile],
            ctx=ctx,
        )
        artifact_generation_report = build_generation_report(
            plugin_id=self.plugin_id,
            artifact_family=artifact_family,
            planned_outputs=planned_outputs,
            generated=written,
            obsolete=obsolete_entries,
            ctx=ctx,
        )
        contract_validation_errors = validate_contract_payloads(
            artifact_plan=artifact_plan,
            generation_report=artifact_generation_report,
            ctx=ctx,
        )
        if contract_validation_errors:
            for message in contract_validation_errors:
                diagnostics.append(
                    self.emit_diagnostic(
                        code="E9603",
                        severity="error",
                        stage=stage,
                        message=message,
                        path="generator:bootstrap_orangepi:artifact_contract",
                    )
                )
            return self.make_result(diagnostics=diagnostics)
        contract_paths = write_contract_artifacts(
            ctx=ctx,
            plugin_id=self.plugin_id,
            artifact_plan=artifact_plan,
            generation_report=artifact_generation_report,
        )

        diagnostics.append(
            self.emit_diagnostic(
                code="I9601",
                severity="info",
                stage=stage,
                message=f"generated baseline Orange Pi bootstrap artifacts: nodes={len(nodes)}",
                path=str(out_root),
            )
        )
        generated_dir = (
            sorted(ownership_roots)[0]
            if ownership_roots
            else str((out_root / self.plugin_id.replace(".", "__")).resolve())
        )
        ctx.publish("generated_dir", generated_dir)
        ctx.publish("generated_files", written)
        ctx.publish("bootstrap_orangepi_files", written)
        ctx.publish("artifact_plan", artifact_plan)
        ctx.publish("artifact_generation_report", artifact_generation_report)
        ctx.publish("artifact_contract_files", sorted(contract_paths.values()))
        return self.make_result(
            diagnostics=diagnostics,
            output_data={
                "bootstrap_orangepi_files": written,
                "artifact_plan": artifact_plan,
                "artifact_generation_report": artifact_generation_report,
                "artifact_contract_files": sorted(contract_paths.values()),
            },
        )
