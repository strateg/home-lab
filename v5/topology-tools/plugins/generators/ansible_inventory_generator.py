"""Generator plugin that emits baseline Ansible inventory artifacts."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from kernel.plugin_base import PluginContext, PluginDiagnostic, PluginResult, Stage
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

        out_root = self.resolve_output_path(ctx, "ansible", "inventory", "production")
        host_vars_dir = out_root / "host_vars"
        group_vars_dir = out_root / "group_vars"

        hosts_rows = projection.get("hosts", [])
        device_hosts = [row for row in hosts_rows if row.get("inventory_group") == "l1_devices"]
        lxc_hosts = [row for row in hosts_rows if row.get("inventory_group") == "l4_lxc"]

        hosts_yml_content = _render_hosts_yaml(device_hosts=device_hosts, lxc_hosts=lxc_hosts)
        group_vars_content = _render_group_vars_all(host_count=len(hosts_rows))

        written: list[str] = []
        hosts_path = out_root / "hosts.yml"
        self.write_text_atomic(hosts_path, hosts_yml_content)
        written.append(str(hosts_path))

        group_vars_path = group_vars_dir / "all.yml"
        self.write_text_atomic(group_vars_path, group_vars_content)
        written.append(str(group_vars_path))

        # Remove stale host_vars files from previous runs to keep output deterministic.
        if host_vars_dir.exists():
            for stale_path in sorted(host_vars_dir.glob("*.yml")):
                stale_path.unlink()

        for row in hosts_rows:
            instance_id = str(row.get("instance_id", "")).strip()
            if not instance_id:
                continue
            host_var_path = host_vars_dir / f"{instance_id}.yml"
            host_var_content = _render_host_vars(instance_id=instance_id, row=row)
            self.write_text_atomic(host_var_path, host_var_content)
            written.append(str(host_var_path))

        diagnostics.append(
            self.emit_diagnostic(
                code="I9301",
                severity="info",
                stage=stage,
                message=f"generated baseline Ansible inventory artifacts: hosts={len(hosts_rows)}",
                path=str(out_root),
            )
        )

        return self.make_result(
            diagnostics=diagnostics,
            output_data={
                "ansible_inventory_dir": str(out_root),
                "ansible_inventory_files": written,
            },
        )


def _render_hosts_yaml(*, device_hosts: list[dict[str, Any]], lxc_hosts: list[dict[str, Any]]) -> str:
    payload = {
        "all": {
            "children": {
                "l1_devices": {
                    "hosts": {str(row["instance_id"]): None for row in device_hosts},
                },
                "l4_lxc": {
                    "hosts": {str(row["instance_id"]): None for row in lxc_hosts},
                },
            },
        },
    }
    return yaml.safe_dump(payload, sort_keys=False, allow_unicode=False)


def _render_group_vars_all(*, host_count: int) -> str:
    payload = {
        "topology_lane": "v5",
        "inventory_profile": "production",
        "inventory_host_count": host_count,
    }
    return yaml.safe_dump(payload, sort_keys=False, allow_unicode=False)


def _render_host_vars(*, instance_id: str, row: dict[str, Any]) -> str:
    payload = {
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
    }
    return yaml.safe_dump(payload, sort_keys=False, allow_unicode=False)
