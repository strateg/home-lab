"""Generator plugin that emits baseline MikroTik Terraform artifacts."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from kernel.plugin_base import PluginContext, PluginDiagnostic, PluginResult, Stage
from plugins.generators.base_generator import BaseGenerator
from plugins.generators.projections import ProjectionError, build_mikrotik_projection


def _render_string_list(items: list[str]) -> str:
    if not items:
        return "[]"
    joined = ", ".join(json.dumps(item, ensure_ascii=True) for item in items)
    return f"[{joined}]"


class TerraformMikroTikGenerator(BaseGenerator):
    """Emit baseline Terraform files from mikrotik projection."""

    def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        diagnostics: list[PluginDiagnostic] = []
        payload = ctx.compiled_json
        if not isinstance(payload, dict) or not payload:
            diagnostics.append(
                self.emit_diagnostic(
                    code="E3001",
                    severity="error",
                    stage=stage,
                    message="compiled_json is empty; cannot generate MikroTik Terraform artifacts.",
                    path="generator:terraform_mikrotik",
                )
            )
            return self.make_result(diagnostics)

        try:
            projection = build_mikrotik_projection(payload)
        except ProjectionError as exc:
            diagnostics.append(
                self.emit_diagnostic(
                    code="E9201",
                    severity="error",
                    stage=stage,
                    message=f"failed to build mikrotik projection: {exc}",
                    path="generator:terraform_mikrotik",
                )
            )
            return self.make_result(diagnostics)

        out_dir = self.resolve_output_path(ctx, "terraform", "mikrotik")

        routers = [str(row.get("instance_id", "")) for row in projection.get("routers", [])]
        networks = [str(row.get("instance_id", "")) for row in projection.get("networks", [])]
        services = [str(row.get("instance_id", "")) for row in projection.get("services", [])]
        mikrotik_host = "https://192.168.88.1:8443"
        if routers:
            mikrotik_host = f"https://{routers[0]}:8443"

        render_context = {
            "terraform_version": str(ctx.config.get("terraform_version", ">= 1.6.0")),
            "mikrotik_provider_source": str(ctx.config.get("mikrotik_provider_source", "terraform-routeros/routeros")),
            "mikrotik_provider_version": str(ctx.config.get("mikrotik_provider_version", "~> 1.40")),
            "routers_list_expr": _render_string_list(routers),
            "networks_list_expr": _render_string_list(networks),
            "services_list_expr": _render_string_list(services),
            "routers_count": len(routers),
            "networks_count": len(networks),
            "services_count": len(services),
            "mikrotik_host": mikrotik_host,
        }

        templates: dict[str, str] = {
            "provider.tf": "terraform/mikrotik/provider.tf.j2",
            "interfaces.tf": "terraform/mikrotik/interfaces.tf.j2",
            "firewall.tf": "terraform/mikrotik/firewall.tf.j2",
            "dhcp.tf": "terraform/mikrotik/dhcp.tf.j2",
            "dns.tf": "terraform/mikrotik/dns.tf.j2",
            "addresses.tf": "terraform/mikrotik/addresses.tf.j2",
            "qos.tf": "terraform/mikrotik/qos.tf.j2",
            "vpn.tf": "terraform/mikrotik/vpn.tf.j2",
            "containers.tf": "terraform/mikrotik/containers.tf.j2",
            "variables.tf": "terraform/mikrotik/variables.tf.j2",
            "outputs.tf": "terraform/mikrotik/outputs.tf.j2",
            "terraform.tfvars.example": "terraform/mikrotik/terraform.tfvars.example.j2",
        }

        written: list[str] = []
        for filename, template_name in templates.items():
            output_path = out_dir / filename
            content = self.render_template(ctx, template_name, render_context)
            self.write_text_atomic(output_path, content)
            written.append(str(output_path))

        diagnostics.append(
            self.emit_diagnostic(
                code="I9201",
                severity="info",
                stage=stage,
                message=(
                    "generated baseline MikroTik Terraform artifacts: "
                    f"routers={len(routers)} networks={len(networks)} services={len(services)}"
                ),
                path=str(out_dir),
            )
        )
        self.publish_if_possible(ctx, "generated_dir", str(out_dir))
        self.publish_if_possible(ctx, "generated_files", written)
        self.publish_if_possible(ctx, "terraform_mikrotik_files", written)

        return self.make_result(
            diagnostics=diagnostics,
            output_data={
                "terraform_mikrotik_dir": str(out_dir),
                "terraform_mikrotik_files": written,
            },
        )
