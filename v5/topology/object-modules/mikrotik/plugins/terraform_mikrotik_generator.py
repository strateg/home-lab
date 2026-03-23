"""Generator plugin that emits baseline MikroTik Terraform artifacts."""

from __future__ import annotations

import json
from pathlib import Path

from kernel.plugin_base import PluginContext, PluginDiagnostic, PluginResult, Stage
from plugins.generators.base_generator import BaseGenerator
from plugins.generators.object_projection_loader import load_object_projection_module

_PROJECTIONS = load_object_projection_module("mikrotik")
ProjectionError = _PROJECTIONS.ProjectionError
build_mikrotik_projection = _PROJECTIONS.build_mikrotik_projection


def _render_string_list(items: list[str]) -> str:
    if not items:
        return "[]"
    joined = ", ".join(json.dumps(item, ensure_ascii=True) for item in items)
    return f"[{joined}]"


class TerraformMikroTikGenerator(BaseGenerator):
    """Emit baseline Terraform files from mikrotik projection."""

    _DEFAULT_MIKROTIK_HOST = "mikrotik.invalid"
    _DEFAULT_MIKROTIK_PORT = 8443

    def template_root(self, ctx: PluginContext) -> Path:
        return self.object_template_root(ctx, object_id="mikrotik")

    @classmethod
    def _resolve_mikrotik_host(cls, *, ctx: PluginContext, routers: list[str]) -> str:
        configured_host = ctx.config.get("mikrotik_api_host")
        if not configured_host:
            configured_host = ctx.config.get("mikrotik_host")
        configured_host_str = str(configured_host).strip() if isinstance(configured_host, str) else ""
        if configured_host_str:
            return configured_host_str
        if routers:
            return f"https://{routers[0]}:{cls._DEFAULT_MIKROTIK_PORT}"
        return f"https://{cls._DEFAULT_MIKROTIK_HOST}:{cls._DEFAULT_MIKROTIK_PORT}"

    def _get_capability_templates(self, capabilities: dict, ctx: PluginContext) -> dict[str, str]:
        """Resolve capability-driven templates from config.

        Returns dict mapping output_file -> template_path for enabled capabilities.
        """
        result: dict[str, str] = {}
        cap_templates = ctx.config.get("capability_templates")
        # ADR0078 specifies dict format only
        if not isinstance(cap_templates, dict):
            return result

        for mapping in cap_templates.values():
            if not isinstance(mapping, dict):
                continue

            enabled_by = mapping.get("enabled_by")
            # TODO(ADR0078-cleanup): Remove capability_key fallback after v5.1 migration
            if not isinstance(enabled_by, str) or not enabled_by.strip():
                cap_key = mapping.get("capability_key", "")
                if isinstance(cap_key, str) and cap_key.strip():
                    enabled_by = f"capabilities.{cap_key.strip()}"

            template = mapping.get("template", "")
            output_file = mapping.get("output")
            # TODO(ADR0078-cleanup): Remove output_file fallback after v5.1 migration
            if not isinstance(output_file, str) or not output_file.strip():
                output_file = mapping.get("output_file", "")

            if not isinstance(enabled_by, str) or not enabled_by.strip() or not template or not output_file:
                continue

            if self._capability_expression_enabled(capabilities, enabled_by):
                result[str(output_file)] = str(template)

        return result

    @staticmethod
    def _capability_expression_enabled(capabilities: dict, enabled_by: str) -> bool:
        expr = enabled_by.strip()
        if not expr:
            return False
        if expr.startswith("capabilities."):
            expr = expr[len("capabilities.") :]

        current = capabilities
        for segment in expr.split("."):
            if not isinstance(current, dict):
                return False
            current = current.get(segment)
        return bool(current)

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
        mikrotik_host = self._resolve_mikrotik_host(ctx=ctx, routers=routers)

        # Extract capability flags from projection
        caps = projection.get("capabilities", {})
        # Normalize has_qos for backwards compatibility (can be basic or advanced)
        has_qos = caps.get("has_qos_basic", False) or caps.get("has_qos_advanced", False)
        normalized_caps = {**caps, "has_qos": has_qos}

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
            **normalized_caps,
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

        # Capability-driven templates from config (ADR0078 WP9)
        capability_templates = self._get_capability_templates(normalized_caps, ctx)
        templates.update(capability_templates)

        written: list[str] = []
        for filename, template_name in templates.items():
            output_path = out_dir / filename
            content = self.render_template(ctx, template_name, render_context)
            self.write_text_atomic(output_path, content)
            written.append(str(output_path))

        # Build capability summary for diagnostic (based on which templates were added)
        cap_summary_parts = list(capability_templates.keys())
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
