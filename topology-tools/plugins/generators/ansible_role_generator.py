"""Generator plugin that emits role-based Ansible host_vars and playbooks (ADR 0104).

This generator scans instances for capability markers and produces:
- host_vars files with role-specific variables
- playbook files for role application

Static role content (tasks, handlers, templates) remains in projects/*/ansible/roles/.
"""

from __future__ import annotations

from kernel.plugin_base import PluginContext, PluginDiagnostic, PluginResult, Stage
from plugins.generators.ansible_role_projections import (
    build_wireguard_gateway_vars,
    resolve_tunnel_instance,
    resolve_vlan_instance,
)
from plugins.generators.artifact_contract import (
    build_artifact_plan,
    build_generation_report,
    build_planned_output,
    compute_obsolete_entries,
    validate_contract_payloads,
    write_contract_artifacts,
)
from plugins.generators.base_generator import BaseGenerator
from plugins.generators.projections import ProjectionError, build_ansible_role_projection


class AnsibleRoleGenerator(BaseGenerator):
    """Emit role-based Ansible host_vars and playbooks from topology capabilities."""

    def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        diagnostics: list[PluginDiagnostic] = []
        payload = ctx.compiled_json

        if not isinstance(payload, dict) or not payload:
            diagnostics.append(
                self.emit_diagnostic(
                    code="E3101",
                    severity="error",
                    stage=stage,
                    message="compiled_json is empty; cannot generate Ansible role artifacts.",
                    path="generator:ansible_role",
                )
            )
            return self.make_result(diagnostics)

        # Build projection to find role assignments
        try:
            projection = build_ansible_role_projection(payload)
        except ProjectionError as exc:
            diagnostics.append(
                self.emit_diagnostic(
                    code="E3102",
                    severity="error",
                    stage=stage,
                    message=f"failed to build ansible role projection: {exc}",
                    path="generator:ansible_role",
                )
            )
            return self.make_result(diagnostics)

        role_assignments = projection.get("role_assignments", [])

        if not role_assignments:
            diagnostics.append(
                self.emit_diagnostic(
                    code="I3101",
                    severity="info",
                    stage=stage,
                    message="No role assignments found (no capability markers); skipping Ansible role generation.",
                    path="generator:ansible_role",
                )
            )
            return self.make_result(diagnostics)

        # Setup output paths
        inventory_profile = str(ctx.config.get("inventory_profile", "production"))
        out_root = self.resolve_output_path(ctx, "ansible")
        host_vars_dir = out_root / "inventory" / inventory_profile / "host_vars"
        playbooks_dir = out_root / "playbooks"

        written: list[str] = []
        planned_outputs: list[dict[str, object]] = []
        write_text = getattr(self, "write_text_atomic", self._fallback_write)

        # Process each role assignment
        for assignment in role_assignments:
            instance_id = assignment.get("instance_id", "")
            role_name = assignment.get("role", "")
            instance_data = assignment.get("instance_data", {})

            if not instance_id or not role_name:
                continue

            if role_name == "wireguard_gateway":
                # Resolve related topology objects
                wg_gateway = instance_data.get("wireguard_gateway", {})
                if not wg_gateway:
                    inst_data_inner = instance_data.get("instance_data", {})
                    wg_gateway = inst_data_inner.get("wireguard_gateway", {})

                tunnel_ref = wg_gateway.get("tunnel_ref", "")
                tunnel = resolve_tunnel_instance(payload, tunnel_ref) if tunnel_ref else {}

                # Get VLAN ref from routed_networks
                vlan_ref = ""
                routed_networks = wg_gateway.get("routed_networks", [])
                if routed_networks:
                    vlan_ref = routed_networks[0].get("vlan_ref", "")
                vlan = resolve_vlan_instance(payload, vlan_ref) if vlan_ref else {}

                # Build role variables
                try:
                    role_vars = build_wireguard_gateway_vars(instance_data, tunnel, vlan)
                except Exception as exc:
                    diagnostics.append(
                        self.emit_diagnostic(
                            code="E3103",
                            severity="error",
                            stage=stage,
                            message=f"failed to build wireguard_gateway vars for {instance_id}: {exc}",
                            path=f"generator:ansible_role:{instance_id}",
                        )
                    )
                    continue

                # Generate host_vars file
                host_vars_path = host_vars_dir / f"{instance_id}.yml"
                planned_outputs.append(
                    build_planned_output(
                        path=str(host_vars_path),
                        renderer="jinja2",
                        reason="capability-enabled",
                    )
                )
                try:
                    host_vars_content = self.render_template(
                        ctx,
                        "ansible/host_vars/wireguard_gateway.yml.j2",
                        role_vars,
                    )
                    write_text(host_vars_path, host_vars_content)
                    written.append(str(host_vars_path))
                except Exception as exc:
                    diagnostics.append(
                        self.emit_diagnostic(
                            code="E3104",
                            severity="error",
                            stage=stage,
                            message=f"failed to render host_vars for {instance_id}: {exc}",
                            path=str(host_vars_path),
                        )
                    )
                    continue

                # Generate playbook file
                playbook_path = playbooks_dir / "vpn-gateway.yml"
                planned_outputs.append(
                    build_planned_output(
                        path=str(playbook_path),
                        renderer="jinja2",
                        reason="capability-enabled",
                    )
                )
                try:
                    playbook_content = self.render_template(
                        ctx,
                        "ansible/playbooks/vpn-gateway.yml.j2",
                        role_vars,
                    )
                    write_text(playbook_path, playbook_content)
                    if str(playbook_path) not in written:
                        written.append(str(playbook_path))
                except Exception as exc:
                    diagnostics.append(
                        self.emit_diagnostic(
                            code="E3105",
                            severity="error",
                            stage=stage,
                            message=f"failed to render playbook for {instance_id}: {exc}",
                            path=str(playbook_path),
                        )
                    )
                    continue

                diagnostics.append(
                    self.emit_diagnostic(
                        code="I3102",
                        severity="info",
                        stage=stage,
                        message=f"generated wireguard_gateway artifacts for {instance_id}",
                        path=str(host_vars_path),
                    )
                )

        if not written:
            diagnostics.append(
                self.emit_diagnostic(
                    code="W3101",
                    severity="warning",
                    stage=stage,
                    message="No artifacts were generated despite role assignments found.",
                    path="generator:ansible_role",
                )
            )
            return self.make_result(diagnostics)

        # Artifact contract handling
        artifact_family = "ansible.role"
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
                        code="E3106",
                        severity="error",
                        stage=stage,
                        message=message,
                        path="generator:ansible_role:obsolete",
                    )
                )

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
                        code="E3107",
                        severity="error",
                        stage=stage,
                        message=message,
                        path="generator:ansible_role:artifact_contract",
                    )
                )

        contract_paths = write_contract_artifacts(
            ctx=ctx,
            plugin_id=self.plugin_id,
            artifact_plan=artifact_plan,
            generation_report=artifact_generation_report,
        )

        diagnostics.append(
            self.emit_diagnostic(
                code="I3103",
                severity="info",
                stage=stage,
                message=f"generated Ansible role artifacts: {len(written)} files for {len(role_assignments)} assignments",
                path=str(out_root),
            )
        )

        ctx.publish("ansible_role_files", written)
        ctx.publish("ansible_role_artifact_plan", artifact_plan)
        ctx.publish("ansible_role_generation_report", artifact_generation_report)

        return self.make_result(
            diagnostics=diagnostics,
            output_data={
                "ansible_role_dir": str(out_root),
                "ansible_role_files": written,
                "artifact_plan": artifact_plan,
                "artifact_generation_report": artifact_generation_report,
                "artifact_contract_files": sorted(contract_paths.values()) if contract_paths else [],
            },
        )

    def _fallback_write(self, path, content: str) -> None:
        """Fallback write method if write_text_atomic not available."""
        from pathlib import Path
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
