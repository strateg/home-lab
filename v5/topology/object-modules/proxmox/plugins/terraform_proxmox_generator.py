"""Generator plugin that emits baseline Proxmox Terraform artifacts."""

from __future__ import annotations

from pathlib import Path

from kernel.plugin_base import PluginContext, PluginDiagnostic, PluginResult, Stage
from plugins.generators.base_generator import BaseGenerator
from plugins.generators.object_projection_loader import load_object_projection_module

# ADR0078 WP-001/WP-002: Use shared helpers from _shared/plugins/
from topology.object_modules._shared.plugins.capability_helpers import get_capability_templates
from topology.object_modules._shared.plugins.terraform_helpers import render_string_list

_PROJECTIONS = load_object_projection_module("proxmox")
ProjectionError = _PROJECTIONS.ProjectionError
build_proxmox_projection = _PROJECTIONS.build_proxmox_projection


class TerraformProxmoxGenerator(BaseGenerator):
    """Emit baseline Terraform files from proxmox projection."""

    _DEFAULT_PROXMOX_HOST = "proxmox.invalid"
    _DEFAULT_PROXMOX_PORT = 8006
    _DEFAULT_PROXMOX_API_PATH = "api2/json"

    def template_root(self, ctx: PluginContext) -> Path:
        return self.object_template_root(ctx, object_id="proxmox")

    @classmethod
    def _resolve_proxmox_api_url(cls, *, ctx: PluginContext, proxmox_nodes: list[str]) -> str:
        configured_url = ctx.config.get("proxmox_api_url")
        configured_url_str = str(configured_url).strip() if isinstance(configured_url, str) else ""
        if configured_url_str:
            return configured_url_str
        if proxmox_nodes:
            return f"https://{proxmox_nodes[0]}:{cls._DEFAULT_PROXMOX_PORT}/{cls._DEFAULT_PROXMOX_API_PATH}"
        return f"https://{cls._DEFAULT_PROXMOX_HOST}:{cls._DEFAULT_PROXMOX_PORT}/{cls._DEFAULT_PROXMOX_API_PATH}"

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
        proxmox_api_url = self._resolve_proxmox_api_url(ctx=ctx, proxmox_nodes=proxmox_nodes)

        # Extract capability flags from projection (if available)
        caps = projection.get("capabilities", {})

        render_context = {
            "terraform_version": str(ctx.config.get("terraform_version", ">= 1.6.0")),
            "proxmox_provider_source": str(ctx.config.get("proxmox_provider_source", "bpg/proxmox")),
            "proxmox_provider_version": str(ctx.config.get("proxmox_provider_version", ">= 0.66.0")),
            "proxmox_nodes_list_expr": render_string_list(proxmox_nodes),
            "lxc_instances_list_expr": render_string_list(lxc_instances),
            "proxmox_nodes_count": len(proxmox_nodes),
            "lxc_count": len(lxc_instances),
            "services_count": len(service_instances),
            "proxmox_api_url": proxmox_api_url,
            # Capability flags for conditional blocks in templates
            **caps,
        }

        # Core templates (always generated)
        templates: dict[str, str] = {
            "versions.tf": "terraform/versions.tf.j2",
            "provider.tf": "terraform/provider.tf.j2",
            "variables.tf": "terraform/variables.tf.j2",
            "bridges.tf": "terraform/bridges.tf.j2",
            "lxc.tf": "terraform/lxc.tf.j2",
            "vms.tf": "terraform/vms.tf.j2",
            "outputs.tf": "terraform/outputs.tf.j2",
            "terraform.tfvars.example": "terraform/terraform.tfvars.example.j2",
        }

        # Capability-driven templates from config (ADR0078 WP-002)
        capability_templates = get_capability_templates(caps, ctx.config)
        templates.update(capability_templates)

        written: list[str] = []
        for filename, template_name in templates.items():
            output_path = out_dir / filename
            content = self.render_template(ctx, template_name, render_context)
            self.write_text_atomic(output_path, content)
            written.append(str(output_path))

        # Build capability summary for diagnostic
        cap_summary_parts = list(capability_templates.keys())
        cap_summary = ",".join(cap_summary_parts) if cap_summary_parts else "none"

        diagnostics.append(
            self.emit_diagnostic(
                code="I9101",
                severity="info",
                stage=stage,
                message=(
                    "generated baseline Proxmox Terraform artifacts: "
                    f"nodes={len(proxmox_nodes)} lxc={len(lxc_instances)} services={len(service_instances)} "
                    f"caps=[{cap_summary}]"
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
