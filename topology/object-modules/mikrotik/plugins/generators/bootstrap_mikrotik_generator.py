"""Generator plugin that emits baseline MikroTik bootstrap artifacts."""

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
        planned_outputs: list[dict[str, object]] = []
        ownership_roots: set[str] = set()
        out_root = self.resolve_output_path(ctx, "bootstrap")

        # Get file mappings from config (ADR0078 WP-003)
        bootstrap_files = get_bootstrap_files(ctx.config)

        for row in nodes:
            instance_id = str(row.get("instance_id", "")).strip()
            if not instance_id:
                continue
            node_root = self.resolve_output_path(ctx, "bootstrap", instance_id)
            ownership_roots.add(str(node_root.resolve()))
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
                planned_outputs.append(
                    build_planned_output(
                        path=str(output_path),
                        template=template,
                        reason="base-family",
                    )
                )
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
                        code="E9503",
                        severity="error",
                        stage=stage,
                        message=message,
                        path="generator:bootstrap_mikrotik:obsolete",
                    )
                )
            return self.make_result(diagnostics=diagnostics)

        artifact_family = "bootstrap.mikrotik"
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
                        code="E9504",
                        severity="error",
                        stage=stage,
                        message=message,
                        path="generator:bootstrap_mikrotik:artifact_contract",
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
                code="I9501",
                severity="info",
                stage=stage,
                message=f"generated baseline MikroTik bootstrap artifacts: nodes={len(nodes)}",
                path=str(out_root),
            )
        )
        generated_dir = (
            sorted(ownership_roots)[0]
            if ownership_roots
            else str((out_root / self.plugin_id.replace(".", "__")).resolve())
        )
        self.publish_if_possible(ctx, "generated_dir", generated_dir)
        self.publish_if_possible(ctx, "generated_files", written)
        self.publish_if_possible(ctx, "bootstrap_mikrotik_files", written)
        self.publish_if_possible(ctx, "artifact_plan", artifact_plan)
        self.publish_if_possible(ctx, "artifact_generation_report", artifact_generation_report)
        self.publish_if_possible(ctx, "artifact_contract_files", sorted(contract_paths.values()))
        return self.make_result(
            diagnostics=diagnostics,
            output_data={
                "bootstrap_mikrotik_files": written,
                "artifact_plan": artifact_plan,
                "artifact_generation_report": artifact_generation_report,
                "artifact_contract_files": sorted(contract_paths.values()),
            },
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
