"""Generator plugin that emits baseline MikroTik Terraform artifacts."""

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

# ADR0078 WP-001/WP-002: Use shared helpers via dynamic loader
from plugins.generators.shared_helper_loader import load_capability_helpers, load_terraform_helpers


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

    def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        diagnostics: list[PluginDiagnostic] = []
        cap_helpers = load_capability_helpers(ctx=ctx)
        tf_helpers = load_terraform_helpers(ctx=ctx)
        get_capability_templates = cap_helpers.get_capability_templates
        render_string_list = tf_helpers.render_string_list
        resolve_remote_state_backend = tf_helpers.resolve_remote_state_backend

        projections = load_object_projection_module("mikrotik", ctx=ctx)
        projection_error = projections.ProjectionError
        build_mikrotik_projection = projections.build_mikrotik_projection
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
        except projection_error as exc:
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
        vlans = projection.get("vlans", [])
        firewall_policies = projection.get("firewall_policies", [])
        mikrotik_host = self._resolve_mikrotik_host(ctx=ctx, routers=routers)

        # Extract capability flags from projection
        caps = projection.get("capabilities", {})
        # Normalize has_qos for backwards compatibility (can be basic or advanced)
        has_qos = caps.get("has_qos_basic", False) or caps.get("has_qos_advanced", False)
        normalized_caps = {
            # Default known template flags to avoid undefined variables when projection omits capabilities.
            "has_vlan": bool(caps.get("has_vlan", False)),
            "has_wireguard": bool(caps.get("has_wireguard", False)),
            "has_containers": bool(caps.get("has_containers", False)),
            "has_qos_basic": bool(caps.get("has_qos_basic", False)),
            "has_qos_advanced": bool(caps.get("has_qos_advanced", False)),
            **caps,
            "has_qos": has_qos,
        }

        render_context = {
            "terraform_version": str(ctx.config.get("terraform_version", ">= 1.6.0")),
            "mikrotik_provider_source": str(ctx.config.get("mikrotik_provider_source", "terraform-routeros/routeros")),
            "mikrotik_provider_version": str(ctx.config.get("mikrotik_provider_version", "~> 1.40")),
            "routers_list_expr": render_string_list(routers),
            "networks_list_expr": render_string_list(networks),
            "services_list_expr": render_string_list(services),
            "routers_count": len(routers),
            "networks_count": len(networks),
            "services_count": len(services),
            "vlans": vlans,
            "vlans_count": len(vlans),
            "firewall_policies": firewall_policies,
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

        # Capability-driven templates from config (ADR0078 WP-002)
        capability_templates = get_capability_templates(normalized_caps, ctx.config)
        templates.update(capability_templates)

        remote_state = resolve_remote_state_backend(ctx.config.get("terraform_remote_state"))
        if remote_state:
            backend_name, backend_items = remote_state
            templates["backend.tf"] = "terraform/backend.tf.j2"
            render_context["remote_state_backend"] = backend_name
            render_context["remote_state_items"] = [{"key": key, "value": value} for key, value in backend_items]

        written: list[str] = []
        planned_outputs: list[dict[str, object]] = []
        for filename, template_name in templates.items():
            output_path = out_dir / filename
            reason = "base-family"
            if filename in capability_templates:
                reason = "capability-enabled"
            elif filename == "backend.tf":
                reason = "dependency-enabled"
            planned_outputs.append(
                build_planned_output(
                    path=str(output_path),
                    template=template_name,
                    reason=reason,
                )
            )
            content = self.render_template(ctx, template_name, render_context)
            self.write_text_atomic(output_path, content)
            written.append(str(output_path))

        capability_flags = sorted(
            key
            for key, value in normalized_caps.items()
            if isinstance(value, bool) and value and (key.startswith("has_") or key.startswith("cap."))
        )
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
                        code="E9203",
                        severity="error",
                        stage=stage,
                        message=message,
                        path="generator:terraform_mikrotik:obsolete",
                    )
                )
            return self.make_result(diagnostics=diagnostics)
        artifact_family = "terraform.mikrotik"
        artifact_plan = build_artifact_plan(
            plugin_id=self.plugin_id,
            artifact_family=artifact_family,
            planned_outputs=planned_outputs,
            projection_version="1.0",
            ir_version="1.0",
            obsolete_candidates=obsolete_entries,
            capabilities=capability_flags,
            validation_profiles=[ctx.profile],
        )
        artifact_generation_report = build_generation_report(
            plugin_id=self.plugin_id,
            artifact_family=artifact_family,
            planned_outputs=planned_outputs,
            generated=written,
            obsolete=obsolete_entries,
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
                        code="E9202",
                        severity="error",
                        stage=stage,
                        message=message,
                        path="generator:terraform_mikrotik:artifact_contract",
                    )
                )
            return self.make_result(diagnostics=diagnostics)
        contract_paths = write_contract_artifacts(
            ctx=ctx,
            plugin_id=self.plugin_id,
            artifact_plan=artifact_plan,
            generation_report=artifact_generation_report,
        )

        # Build capability summary for diagnostic (based on which templates were added)
        cap_summary_parts = list(capability_templates.keys())
        cap_summary = ",".join(cap_summary_parts) if cap_summary_parts else "none"

        diagnostics.append(
            self.emit_diagnostic(
                code="I9201",
                severity="info",
                stage=stage,
                message=(
                    "generated MikroTik Terraform artifacts: "
                    f"routers={len(routers)} vlans={len(vlans)} networks={len(networks)} services={len(services)} "
                    f"caps=[{cap_summary}] "
                    f"remote_state={'enabled' if remote_state else 'disabled'}"
                ),
                path=str(out_dir),
            )
        )
        self.publish_if_possible(ctx, "generated_dir", str(out_dir))
        self.publish_if_possible(ctx, "generated_files", written)
        self.publish_if_possible(ctx, "terraform_mikrotik_files", written)
        self.publish_if_possible(ctx, "artifact_plan", artifact_plan)
        self.publish_if_possible(ctx, "artifact_generation_report", artifact_generation_report)
        self.publish_if_possible(ctx, "artifact_contract_files", sorted(contract_paths.values()))

        return self.make_result(
            diagnostics=diagnostics,
            output_data={
                "terraform_mikrotik_dir": str(out_dir),
                "terraform_mikrotik_files": written,
                "artifact_plan": artifact_plan,
                "artifact_generation_report": artifact_generation_report,
                "artifact_contract_files": sorted(contract_paths.values()),
            },
        )
