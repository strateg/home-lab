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
from plugins.generators.terraform_ir import build_terraform_module_family_ir
from plugins.generators.terraform_programmatic import render_backend_tf


class TerraformMikroTikGenerator(BaseGenerator):
    """Emit baseline Terraform files from mikrotik projection."""

    _DEFAULT_MIKROTIK_HOST = "mikrotik.invalid"
    _DEFAULT_MIKROTIK_PORT = 443

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
        bridges = projection.get("bridges", [])
        services = [str(row.get("instance_id", "")) for row in projection.get("services", [])]
        vlans = projection.get("vlans", [])
        firewall_policies = projection.get("firewall_policies", [])
        runtime_baseline = projection.get("runtime_baseline", {})
        wireguard = projection.get("wireguard", {})
        if not isinstance(runtime_baseline, dict):
            runtime_baseline = {}
        runtime_baseline.setdefault("dhcp", {})
        if not isinstance(runtime_baseline.get("dhcp"), dict):
            runtime_baseline["dhcp"] = {}
        runtime_baseline.setdefault("dns_servers", [])
        runtime_baseline.setdefault("nat", [])
        runtime_baseline["dhcp"].setdefault("enabled", False)
        mikrotik_host = self._resolve_mikrotik_host(ctx=ctx, routers=routers)

        # Extract security matrix from projection (ADR 0110)
        router_matrix = projection.get("security_matrix", {})

        # Extract capability flags from projection
        caps = projection.get("capabilities", {})
        # Normalize has_qos for backwards compatibility (can be basic or advanced)
        has_qos = caps.get("has_qos_basic", False) or caps.get("has_qos_advanced", False)
        normalized_caps = {
            # Default known template flags to avoid undefined variables when projection omits capabilities.
            "has_vlan": bool(caps.get("has_vlan", False) or vlans),
            "has_wireguard": bool(caps.get("has_wireguard", False)),
            "has_containers": bool(caps.get("has_containers", False)),
            "has_qos_basic": bool(caps.get("has_qos_basic", False)),
            "has_qos_advanced": bool(caps.get("has_qos_advanced", False)),
            **caps,
            "has_qos": has_qos,
        }

        # Extract WireGuard configuration from projection
        wireguard_peers = wireguard.get("wireguard_peers", [])
        wireguard_address = wireguard.get("wireguard_address", "10.100.0.1/30")
        wireguard_listen_port = wireguard.get("wireguard_listen_port", 51820)
        wireguard_mtu = wireguard.get("wireguard_mtu", 1420)

        # Extract WiFi and bridge VLAN configuration from projection
        wifi = projection.get("wifi", {})
        wifi_datapaths = wifi.get("datapaths", [])
        wifi_configurations = wifi.get("configurations", [])
        wifi_securities = wifi.get("securities", [])
        bridge_vlans = projection.get("bridge_vlans", [])

        render_context = {
            "terraform_version": str(ctx.config.get("terraform_version", ">= 1.6.0")),
            "mikrotik_provider_source": str(ctx.config.get("mikrotik_provider_source", "terraform-routeros/routeros")),
            "mikrotik_provider_version": str(ctx.config.get("mikrotik_provider_version", "~> 1.40")),
            "routers_list_expr": render_string_list(routers),
            "networks_list_expr": render_string_list(networks),
            "services_list_expr": render_string_list(services),
            "routers_count": len(routers),
            "networks_count": len(networks),
            "bridges": bridges,
            "bridges_count": len(bridges),
            "services_count": len(services),
            "vlans": vlans,
            "vlans_count": len(vlans),
            "firewall_policies": firewall_policies,
            "runtime_baseline": runtime_baseline,
            "mikrotik_host": mikrotik_host,
            # WireGuard configuration
            "wireguard_peers": wireguard_peers,
            "wireguard_address": wireguard_address,
            "wireguard_listen_port": wireguard_listen_port,
            "wireguard_mtu": wireguard_mtu,
            # WiFi configuration
            "wifi_datapaths": wifi_datapaths,
            "wifi_configurations": wifi_configurations,
            "wifi_securities": wifi_securities,
            # Bridge VLAN entries
            "bridge_vlans": bridge_vlans,
            # Security matrix data (ADR 0110)
            "security_matrix": router_matrix,
            "has_security_matrix": bool(router_matrix and router_matrix.get("zones")),
            # MAC-based VLAN assignments from device instances
            "mac_vlan_assignments": projection.get("mac_vlan_assignments", []),
            # Capability flags for conditional blocks in templates
            **normalized_caps,
        }

        # Core templates (always generated)
        templates: dict[str, str] = {
            "provider.tf": "terraform/provider.tf.j2",
            "interfaces.tf": "terraform/interfaces.tf.j2",
            "bridge_hosts.tf": "terraform/bridge_hosts.tf.j2",
            "firewall.tf": "terraform/firewall.tf.j2",
            "zone_firewall.tf": "terraform/zone_firewall.tf.j2",
            "dhcp.tf": "terraform/dhcp.tf.j2",
            "dns.tf": "terraform/dns.tf.j2",
            "addresses.tf": "terraform/addresses.tf.j2",
            "vpn.tf": "terraform/vpn.tf.j2",
            "wifi.tf": "terraform/wifi.tf.j2",
            "variables.tf": "terraform/variables.tf.j2",
            "outputs.tf": "terraform/outputs.tf.j2",
            "terraform.tfvars.example": "terraform/terraform.tfvars.example.j2",
        }

        # Capability-driven templates from config (ADR0078 WP-002)
        capability_templates = get_capability_templates(normalized_caps, ctx.config)
        templates.update(capability_templates)

        remote_state_backend_name = ""
        remote_state_backend_items: list[tuple[str, str]] = []
        remote_state = resolve_remote_state_backend(ctx.config.get("terraform_remote_state"))
        if remote_state:
            backend_name, backend_items = remote_state
            remote_state_backend_name = backend_name
            remote_state_backend_items = backend_items
            templates["backend.tf"] = "terraform/backend.tf.j2"
            render_context["remote_state_backend"] = backend_name
            render_context["remote_state_items"] = [{"key": key, "value": value} for key, value in backend_items]

        capability_flags = sorted(
            key
            for key, value in normalized_caps.items()
            if isinstance(value, bool) and value and (key.startswith("has_") or key.startswith("cap."))
        )
        terraform_ir = build_terraform_module_family_ir(
            artifact_family="terraform.mikrotik",
            templates=templates,
            capability_templates=capability_templates,
            remote_state_enabled=bool(remote_state),
            capability_flags=capability_flags,
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
            if item.renderer == "programmatic" and filename == "backend.tf" and remote_state:
                content = render_backend_tf(
                    backend_name=remote_state_backend_name,
                    backend_items=remote_state_backend_items,
                )
            else:
                content = self.render_template(ctx, template_name, render_context)
            self.write_text_atomic(output_path, content)
            written.append(str(output_path))

        # Generate WiFi RSC script (WiFi resources not supported by Terraform provider)
        if wifi_datapaths or wifi_configurations:
            wifi_rsc_path = out_dir / "wifi-config.rsc"
            wifi_rsc_content = self.render_template(ctx, "mikrotik/wifi-config.rsc.j2", render_context)
            self.write_text_atomic(wifi_rsc_path, wifi_rsc_content)
            written.append(str(wifi_rsc_path))
            planned_outputs.append(
                build_planned_output(
                    path=str(wifi_rsc_path),
                    renderer="jinja2",
                    template="mikrotik/wifi-config.rsc.j2",
                    reason="capability-enabled",
                )
            )

        # Generate Ansible host_vars for WiFi (automated deployment)
        if wifi_datapaths or wifi_configurations:
            ansible_out_dir = self.resolve_output_path(
                ctx, "ansible", "inventory", "production", "host_vars"
            )
            for router_id in routers:
                wifi_vars_path = ansible_out_dir / f"{router_id}.wifi.yml"
                wifi_vars_content = self.render_template(
                    ctx, "ansible/host_vars_wifi.yml.j2", render_context
                )
                self.write_text_atomic(wifi_vars_path, wifi_vars_content)
                written.append(str(wifi_vars_path))

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
                    f"routers={len(routers)} bridges={len(bridges)} vlans={len(vlans)} "
                    f"networks={len(networks)} services={len(services)} "
                    f"caps=[{cap_summary}] "
                    f"remote_state={'enabled' if remote_state else 'disabled'}"
                ),
                path=str(out_dir),
            )
        )
        ctx.publish("generated_dir", str(out_dir))
        ctx.publish("generated_files", written)
        ctx.publish("terraform_mikrotik_files", written)
        ctx.publish("artifact_plan", artifact_plan)
        ctx.publish("artifact_generation_report", artifact_generation_report)
        ctx.publish("artifact_contract_files", sorted(contract_paths.values()))

        return self.make_result(
            diagnostics=diagnostics,
            output_data={
                "terraform_mikrotik_dir": str(out_dir),
                "terraform_mikrotik_files": written,
                "artifact_plan": artifact_plan,
                "artifact_generation_report": artifact_generation_report,
                "artifact_contract_files": sorted(contract_paths.values()),
                "terraform_ir": terraform_ir.to_dict(),
            },
        )
