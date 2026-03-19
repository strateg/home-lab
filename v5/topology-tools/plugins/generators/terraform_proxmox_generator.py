"""Generator plugin that emits baseline Proxmox Terraform artifacts."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

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

        files: dict[str, str] = {
            "versions.tf": _versions_tf(),
            "provider.tf": _provider_tf(),
            "variables.tf": _variables_tf(),
            "bridges.tf": _bridges_tf(proxmox_nodes),
            "lxc.tf": _lxc_tf(lxc_instances),
            "vms.tf": _vms_tf(),
            "outputs.tf": _outputs_tf(proxmox_nodes, lxc_instances, service_instances),
            "terraform.tfvars.example": _tfvars_example(proxmox_nodes),
        }

        written: list[str] = []
        for filename, content in files.items():
            output_path = out_dir / filename
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

        return self.make_result(
            diagnostics=diagnostics,
            output_data={
                "terraform_proxmox_dir": str(out_dir),
                "terraform_proxmox_files": written,
            },
        )


def _versions_tf() -> str:
    return (
        'terraform {\n'
        '  required_version = ">= 1.6.0"\n'
        "  required_providers {\n"
        "    proxmox = {\n"
        '      source  = "bpg/proxmox"\n'
        '      version = ">= 0.66.0"\n'
        "    }\n"
        "  }\n"
        "}\n"
    )


def _provider_tf() -> str:
    return (
        "provider \"proxmox\" {\n"
        "  endpoint  = var.proxmox_api_url\n"
        "  api_token = var.proxmox_api_token\n"
        "  insecure  = var.proxmox_insecure\n"
        "}\n"
    )


def _variables_tf() -> str:
    return (
        "variable \"proxmox_api_url\" {\n"
        "  type        = string\n"
        "  description = \"Proxmox API endpoint URL\"\n"
        "}\n\n"
        "variable \"proxmox_api_token\" {\n"
        "  type        = string\n"
        "  description = \"Proxmox API token\"\n"
        "  sensitive   = true\n"
        "}\n\n"
        "variable \"proxmox_insecure\" {\n"
        "  type        = bool\n"
        "  description = \"Skip TLS verification for API connection\"\n"
        "  default     = true\n"
        "}\n"
    )


def _bridges_tf(proxmox_nodes: list[str]) -> str:
    return (
        "# Baseline projection output; bridge resources are added in parity phase.\n"
        "locals {\n"
        f"  proxmox_nodes = {_render_string_list(proxmox_nodes)}\n"
        "}\n"
    )


def _lxc_tf(lxc_instances: list[str]) -> str:
    return (
        "# Baseline projection output; LXC resource rendering is added in parity phase.\n"
        "locals {\n"
        f"  lxc_instances = {_render_string_list(lxc_instances)}\n"
        "}\n"
    )


def _vms_tf() -> str:
    return (
        "# Baseline projection output; VM resource rendering is added in parity phase.\n"
        "locals {\n"
        "  vm_instances = []\n"
        "}\n"
    )


def _outputs_tf(proxmox_nodes: list[str], lxc_instances: list[str], service_instances: list[str]) -> str:
    return (
        "output \"projection_counts\" {\n"
        "  value = {\n"
        f"    proxmox_nodes = {len(proxmox_nodes)}\n"
        f"    lxc           = {len(lxc_instances)}\n"
        f"    services      = {len(service_instances)}\n"
        "  }\n"
        "}\n"
    )


def _tfvars_example(proxmox_nodes: list[str]) -> str:
    default_endpoint = "https://proxmox.local:8006/api2/json"
    if proxmox_nodes:
        default_endpoint = f"https://{proxmox_nodes[0]}:8006/api2/json"
    return (
        f'proxmox_api_url = "{default_endpoint}"\n'
        'proxmox_api_token = "<TODO_PROXMOX_API_TOKEN>"\n'
        "proxmox_insecure = true\n"
    )

