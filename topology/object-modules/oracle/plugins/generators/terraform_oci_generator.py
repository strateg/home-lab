"""Generator plugin that emits baseline OCI (Oracle Cloud) Terraform artifacts."""

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
from plugins.generators.object_projection_loader import load_object_projection_module
from plugins.generators.terraform_ir import build_terraform_module_family_ir


class TerraformOCIGenerator(BaseGenerator):
    """Emit baseline Terraform files from OCI projection."""

    def template_root(self, ctx: PluginContext) -> Path:
        return self.object_template_root(ctx, object_id="oracle")

    def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        diagnostics: list[PluginDiagnostic] = []

        # Load OCI-specific projection module
        projections = load_object_projection_module("oracle", ctx=ctx)
        projection_error = projections.ProjectionError
        build_oci_projection = projections.build_oci_projection

        payload = ctx.compiled_json
        if not isinstance(payload, dict) or not payload:
            diagnostics.append(
                self.emit_diagnostic(
                    code="E3001",
                    severity="error",
                    stage=stage,
                    message="compiled_json is empty; cannot generate OCI Terraform artifacts.",
                    path="generator:terraform_oci",
                )
            )
            return self.make_result(diagnostics)

        try:
            projection = build_oci_projection(payload)
        except projection_error as exc:
            diagnostics.append(
                self.emit_diagnostic(
                    code="E9301",
                    severity="error",
                    stage=stage,
                    message=f"failed to build OCI projection: {exc}",
                    path="generator:terraform_oci",
                )
            )
            return self.make_result(diagnostics)

        instances = projection.get("instances", [])
        if not instances:
            diagnostics.append(
                self.emit_diagnostic(
                    code="I9301",
                    severity="info",
                    stage=stage,
                    message="No OCI instances found in topology; skipping Terraform generation.",
                    path="generator:terraform_oci",
                )
            )
            return self.make_result(diagnostics)

        out_dir = self.resolve_output_path(ctx, "terraform", "oci")

        # Determine primary region and default availability domain
        primary_region = projection.get("primary_region", "eu-frankfurt-1")
        # Extract availability domain from first instance if available
        default_ad = ""
        if instances:
            default_ad = instances[0].get("availability_domain", "")

        render_context = {
            "terraform_version": str(ctx.config.get("terraform_version", ">= 1.6.0")),
            "oci_provider_source": str(ctx.config.get("oci_provider_source", "oracle/oci")),
            "oci_provider_version": str(ctx.config.get("oci_provider_version", ">= 5.0")),
            "instances": instances,
            "instances_count": len(instances),
            "region": primary_region,
            "default_availability_domain": default_ad,
        }

        # Core templates (always generated)
        templates: dict[str, str] = {
            "provider.tf": "terraform/provider.tf.j2",
            "instance.tf": "terraform/instance.tf.j2",
            "variables.tf": "terraform/variables.tf.j2",
            "outputs.tf": "terraform/outputs.tf.j2",
            "terraform.tfvars.example": "terraform/terraform.tfvars.example.j2",
        }

        terraform_ir = build_terraform_module_family_ir(
            artifact_family="terraform.oci",
            templates=templates,
            capability_templates={},
            remote_state_enabled=False,
            capability_flags=[],
        )

        written: list[str] = []
        planned_outputs: list[dict[str, object]] = []

        for item in terraform_ir.planned_files:
            filename = item.filename
            template_name = item.template
            output_path = out_dir / filename
            planned_outputs.append(
                build_planned_output(
                    path=str(output_path),
                    renderer=item.renderer,
                    template=template_name,
                    reason=item.reason,
                )
            )
            content = self.render_template(ctx, template_name, render_context)
            self.write_text_atomic(output_path, content)
            written.append(str(output_path))

        obsolete_entries, obsolete_errors = compute_obsolete_entries(
            ctx=ctx,
            plugin_id=self.plugin_id,
            output_root=out_dir,
            planned_outputs=planned_outputs,
        )
        if obsolete_errors:
            for message in obsolete_errors:
                diagnostics.append(
                    self.emit_diagnostic(
                        code="E9303",
                        severity="error",
                        stage=stage,
                        message=message,
                        path="generator:terraform_oci:obsolete",
                    )
                )
            return self.make_result(diagnostics=diagnostics)

        artifact_family = "terraform.oci"
        artifact_plan = build_artifact_plan(
            plugin_id=self.plugin_id,
            artifact_family=artifact_family,
            planned_outputs=planned_outputs,
            projection_version=terraform_ir.projection_version,
            ir_version=terraform_ir.ir_version,
            obsolete_candidates=obsolete_entries,
            capabilities=list(terraform_ir.capabilities),
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
                        code="E9302",
                        severity="error",
                        stage=stage,
                        message=message,
                        path="generator:terraform_oci:artifact_contract",
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
                code="I9302",
                severity="info",
                stage=stage,
                message=(
                    f"generated OCI Terraform artifacts: instances={len(instances)} "
                    f"region={primary_region}"
                ),
                path=str(out_dir),
            )
        )

        ctx.publish("generated_dir", str(out_dir))
        ctx.publish("generated_files", written)
        ctx.publish("terraform_oci_files", written)
        ctx.publish("artifact_plan", artifact_plan)
        ctx.publish("artifact_generation_report", artifact_generation_report)
        ctx.publish("artifact_contract_files", sorted(contract_paths.values()))

        return self.make_result(
            diagnostics=diagnostics,
            output_data={
                "terraform_oci_dir": str(out_dir),
                "terraform_oci_files": written,
                "artifact_plan": artifact_plan,
                "artifact_generation_report": artifact_generation_report,
                "artifact_contract_files": sorted(contract_paths.values()),
                "terraform_ir": terraform_ir.to_dict(),
            },
        )
