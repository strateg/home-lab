"""Generator plugin that emits baseline Proxmox Terraform artifacts."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from kernel.plugin_base import PluginContext, PluginDiagnostic, PluginResult, Stage
from plugins.generators.base_generator import BaseGenerator
from plugins.generators.projections import ProjectionError, build_proxmox_projection


def _render_string_list(items: list[str]) -> str:
    if not items:
        return "[]"
    joined = ", ".join(json.dumps(item, ensure_ascii=True) for item in items)
    return f"[{joined}]"


class TerraformProxmoxGenerator(BaseGenerator):
    """Emit baseline Terraform files from proxmox projection."""

    def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        diagnostics: list[PluginDiagnostic] = []
        payload = ctx.compiled_json
        if not isinstance(payload, dict) or not payload:
            diagnostics.append(
                self.emit_diagnostic(
                    code="E3001",
                    severity="error",
                    stage=stage,
                    message="compiled_json is empty; cannot generate Proxmox Terraform artifacts.",
                    path="generator:terraform_proxmox",
                )
            )
            return self.make_result(diagnostics)

        try:
            projection = build_proxmox_projection(payload)
        except ProjectionError as exc:
            diagnostics.append(
                self.emit_diagnostic(
                    code="E9101",
                    severity="error",
                    stage=stage,
                    message=f"failed to build proxmox projection: {exc}",
                    path="generator:terraform_proxmox",
                )
            )
            return self.make_result(diagnostics)

        out_dir = self.resolve_output_path(ctx, "terraform", "proxmox")

        proxmox_nodes = [str(row.get("instance_id", "")) for row in projection.get("proxmox_nodes", [])]
        lxc_rows = projection.get("lxc", [])
        lxc_instances = [str(row.get("instance_id", "")) for row in lxc_rows]
        service_instances = [str(row.get("instance_id", "")) for row in projection.get("services", [])]
        proxmox_api_url = "https://proxmox.local:8006/api2/json"
        if proxmox_nodes:
            proxmox_api_url = f"https://{proxmox_nodes[0]}:8006/api2/json"

        render_context = {
            "terraform_version": str(ctx.config.get("terraform_version", ">= 1.6.0")),
            "proxmox_provider_source": str(ctx.config.get("proxmox_provider_source", "bpg/proxmox")),
            "proxmox_provider_version": str(ctx.config.get("proxmox_provider_version", ">= 0.66.0")),
            "proxmox_nodes_list_expr": _render_string_list(proxmox_nodes),
            "lxc_instances_list_expr": _render_string_list(lxc_instances),
            "proxmox_nodes_count": len(proxmox_nodes),
            "lxc_count": len(lxc_instances),
            "services_count": len(service_instances),
            "proxmox_api_url": proxmox_api_url,
        }

        templates: dict[str, str] = {
            "versions.tf": "terraform/proxmox/versions.tf.j2",
            "provider.tf": "terraform/proxmox/provider.tf.j2",
            "variables.tf": "terraform/proxmox/variables.tf.j2",
            "bridges.tf": "terraform/proxmox/bridges.tf.j2",
            "lxc.tf": "terraform/proxmox/lxc.tf.j2",
            "vms.tf": "terraform/proxmox/vms.tf.j2",
            "outputs.tf": "terraform/proxmox/outputs.tf.j2",
            "terraform.tfvars.example": "terraform/proxmox/terraform.tfvars.example.j2",
        }

        written: list[str] = []
        for filename, template_name in templates.items():
            output_path = out_dir / filename
            content = self.render_template(ctx, template_name, render_context)
            self.write_text_atomic(output_path, content)
            written.append(str(output_path))

        diagnostics.append(
            self.emit_diagnostic(
                code="I9101",
                severity="info",
                stage=stage,
                message=(
                    "generated baseline Proxmox Terraform artifacts: "
                    f"nodes={len(proxmox_nodes)} lxc={len(lxc_instances)} services={len(service_instances)}"
                ),
                path=str(out_dir),
            )
        )
        self.publish_if_possible(ctx, "generated_dir", str(out_dir))
        self.publish_if_possible(ctx, "generated_files", written)
        self.publish_if_possible(ctx, "terraform_proxmox_files", written)

        return self.make_result(
            diagnostics=diagnostics,
            output_data={
                "terraform_proxmox_dir": str(out_dir),
                "terraform_proxmox_files": written,
            },
        )
