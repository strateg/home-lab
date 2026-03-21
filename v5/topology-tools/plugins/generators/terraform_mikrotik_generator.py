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

    def template_root(self, ctx: PluginContext) -> Path:
        raw = ctx.config.get("generator_templates_root")
        if isinstance(raw, str) and raw.strip():
            return Path(raw)

        candidates: list[Path] = []
        object_modules_root_raw = ctx.config.get("object_modules_root")
        if isinstance(object_modules_root_raw, str) and object_modules_root_raw.strip():
            candidates.append(Path(object_modules_root_raw.strip()) / "mikrotik" / "templates")
        topology_path_raw = getattr(ctx, "topology_path", None)
        if isinstance(topology_path_raw, str) and topology_path_raw.strip():
            candidates.append(Path(topology_path_raw.strip()).parent / "object-modules" / "mikrotik" / "templates")

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

        # Extract capability flags from projection
        caps = projection.get("capabilities", {})
        has_wireguard = caps.get("has_wireguard", False)
        has_containers = caps.get("has_containers", False)
        has_qos = caps.get("has_qos_basic", False) or caps.get("has_qos_advanced", False)

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
            # Capability flags for conditional blocks in templates
            "has_wireguard": has_wireguard,
            "has_containers": has_containers,
            "has_qos": has_qos,
            **caps,  # Include all capability flags
        }

        # Core templates (always generated)
        templates: dict[str, str] = {
            "provider.tf": "terraform/provider.tf.j2",
            "interfaces.tf": "terraform/interfaces.tf.j2",
            "firewall.tf": "terraform/firewall.tf.j2",
            "dhcp.tf": "terraform/dhcp.tf.j2",
            "dns.tf": "terraform/dns.tf.j2",
            "addresses.tf": "terraform/addresses.tf.j2",
            "variables.tf": "terraform/variables.tf.j2",
            "outputs.tf": "terraform/outputs.tf.j2",
            "terraform.tfvars.example": "terraform/terraform.tfvars.example.j2",
        }

        # Capability-driven templates (only generated if capability present)
        if has_qos:
            templates["qos.tf"] = "terraform/qos.tf.j2"
        if has_wireguard:
            templates["vpn.tf"] = "terraform/vpn.tf.j2"
        if has_containers:
            templates["containers.tf"] = "terraform/containers.tf.j2"

        written: list[str] = []
        for filename, template_name in templates.items():
            output_path = out_dir / filename
            content = self.render_template(ctx, template_name, render_context)
            self.write_text_atomic(output_path, content)
            written.append(str(output_path))

        # Build capability summary for diagnostic
        cap_summary_parts = []
        if has_wireguard:
            cap_summary_parts.append("wireguard")
        if has_containers:
            cap_summary_parts.append("containers")
        if has_qos:
            cap_summary_parts.append("qos")
        cap_summary = ",".join(cap_summary_parts) if cap_summary_parts else "none"

        diagnostics.append(
            self.emit_diagnostic(
                code="I9201",
                severity="info",
                stage=stage,
                message=(
                    "generated baseline MikroTik Terraform artifacts: "
                    f"routers={len(routers)} networks={len(networks)} services={len(services)} "
                    f"caps=[{cap_summary}]"
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
