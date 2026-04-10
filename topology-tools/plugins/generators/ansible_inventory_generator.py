"""Generator plugin that emits baseline Ansible inventory artifacts."""

from __future__ import annotations

import json

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
from plugins.generators.projections import ProjectionError, build_ansible_projection


class AnsibleInventoryGenerator(BaseGenerator):
    """Emit baseline Ansible inventory from ansible projection."""

    def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        diagnostics: list[PluginDiagnostic] = []
        payload = ctx.compiled_json
        if not isinstance(payload, dict) or not payload:
            diagnostics.append(
                self.emit_diagnostic(
                    code="E3001",
                    severity="error",
                    stage=stage,
                    message="compiled_json is empty; cannot generate Ansible inventory artifacts.",
                    path="generator:ansible_inventory",
                )
            )
            return self.make_result(diagnostics)

        try:
            projection = build_ansible_projection(payload)
        except ProjectionError as exc:
            diagnostics.append(
                self.emit_diagnostic(
                    code="E9301",
                    severity="error",
                    stage=stage,
                    message=f"failed to build ansible projection: {exc}",
                    path="generator:ansible_inventory",
                )
            )
            return self.make_result(diagnostics)

        inventory_profile = str(ctx.config.get("inventory_profile", "production"))
        topology_lane = str(ctx.config.get("topology_lane", "v5"))
        out_root = self.resolve_output_path(ctx, "ansible", "inventory", inventory_profile)
        host_vars_dir = out_root / "host_vars"
        group_vars_dir = out_root / "group_vars"

        hosts_rows = projection.get("hosts", [])
        device_hosts = [row for row in hosts_rows if row.get("inventory_group") == "devices"]
        lxc_hosts = [row for row in hosts_rows if row.get("inventory_group") == "lxc"]

        written: list[str] = []
        planned_outputs: list[dict[str, object]] = []
        write_text = self.__dict__.get("write_text_atomic", self.write_text_atomic)

        hosts_path = out_root / "hosts.yml"
        planned_outputs.append(
            build_planned_output(
                path=str(hosts_path),
                renderer="structured",
                reason="base-family",
            )
        )
        hosts_yml_content = self.render_template(
            ctx,
            "ansible/inventory/hosts.yml.j2",
            {"device_hosts": device_hosts, "lxc_hosts": lxc_hosts},
        )
        write_text(hosts_path, hosts_yml_content)
        written.append(str(hosts_path))

        group_vars_path = group_vars_dir / "all.yml"
        planned_outputs.append(
            build_planned_output(
                path=str(group_vars_path),
                renderer="structured",
                reason="base-family",
            )
        )
        group_vars_content = self.render_template(
            ctx,
            "ansible/inventory/group_vars_all.yml.j2",
            {
                "topology_lane": topology_lane,
                "inventory_profile": inventory_profile,
                "host_count": len(hosts_rows),
            },
        )
        write_text(group_vars_path, group_vars_content)
        written.append(str(group_vars_path))

        for row in hosts_rows:
            instance_id = str(row.get("instance_id", "")).strip()
            if not instance_id:
                continue
            host_var_path = host_vars_dir / f"{instance_id}.yml"
            planned_outputs.append(
                build_planned_output(
                    path=str(host_var_path),
                    renderer="structured",
                    reason="base-family",
                )
            )
            host_var_content = self.render_template(
                ctx,
                "ansible/inventory/host_vars.yml.j2",
                {
                    "instance_id": instance_id,
                    "object_ref": row.get("object_ref", ""),
                    "inventory_group": row.get("inventory_group", ""),
                    "ansible_host": str(row.get("management_ip") or instance_id),
                    "metadata_json": json.dumps(
                        {
                            "class_ref": row.get("class_ref"),
                            "status": row.get("status"),
                        },
                        ensure_ascii=True,
                        sort_keys=True,
                    ),
                },
            )
            write_text(host_var_path, host_var_content)
            written.append(str(host_var_path))

        artifact_family = "ansible.inventory"
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
                        code="E9303",
                        severity="error",
                        stage=stage,
                        message=message,
                        path="generator:ansible_inventory:obsolete",
                    )
                )
            return self.make_result(diagnostics=diagnostics)
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
                        code="E9302",
                        severity="error",
                        stage=stage,
                        message=message,
                        path="generator:ansible_inventory:artifact_contract",
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
                code="I9301",
                severity="info",
                stage=stage,
                message=f"generated baseline Ansible inventory artifacts: hosts={len(hosts_rows)}",
                path=str(out_root),
            )
        )
        self.publish_if_possible(ctx, "generated_dir", str(out_root))
        self.publish_if_possible(ctx, "generated_files", written)
        self.publish_if_possible(ctx, "ansible_inventory_files", written)
        self.publish_if_possible(ctx, "artifact_plan", artifact_plan)
        self.publish_if_possible(ctx, "artifact_generation_report", artifact_generation_report)
        self.publish_if_possible(ctx, "artifact_contract_files", sorted(contract_paths.values()))

        return self.make_result(
            diagnostics=diagnostics,
            output_data={
                "ansible_inventory_dir": str(out_root),
                "ansible_inventory_files": written,
                "artifact_plan": artifact_plan,
                "artifact_generation_report": artifact_generation_report,
                "artifact_contract_files": sorted(contract_paths.values()),
            },
        )
