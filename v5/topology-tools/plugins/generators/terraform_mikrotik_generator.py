"""Generator plugin that emits baseline MikroTik Terraform artifacts."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

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

        files: dict[str, str] = {
            "provider.tf": _provider_tf(),
            "interfaces.tf": _interfaces_tf(routers),
            "firewall.tf": _firewall_tf(networks),
            "dhcp.tf": _dhcp_tf(networks),
            "dns.tf": _dns_tf(),
            "addresses.tf": _addresses_tf(networks),
            "qos.tf": _qos_tf(),
            "vpn.tf": _vpn_tf(),
            "containers.tf": _containers_tf(services),
            "variables.tf": _variables_tf(),
            "outputs.tf": _outputs_tf(routers, networks, services),
            "terraform.tfvars.example": _tfvars_example(routers),
        }

        written: list[str] = []
        for filename, content in files.items():
            output_path = out_dir / filename
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

        return self.make_result(
            diagnostics=diagnostics,
            output_data={
                "terraform_mikrotik_dir": str(out_dir),
                "terraform_mikrotik_files": written,
            },
        )


def _provider_tf() -> str:
    return (
        'terraform {\n'
        '  required_version = ">= 1.6.0"\n'
        "  required_providers {\n"
        "    routeros = {\n"
        '      source  = "terraform-routeros/routeros"\n'
        '      version = "~> 1.40"\n'
        "    }\n"
        "  }\n"
        "}\n\n"
        'provider "routeros" {\n'
        "  hosturl  = var.mikrotik_host\n"
        "  username = var.mikrotik_username\n"
        "  password = var.mikrotik_password\n"
        "  insecure = var.mikrotik_insecure\n"
        "}\n"
    )


def _variables_tf() -> str:
    return (
        'variable "mikrotik_host" {\n'
        "  description = \"MikroTik router URL (https://ip:port)\"\n"
        "  type        = string\n"
        "}\n\n"
        'variable "mikrotik_username" {\n'
        "  description = \"MikroTik API username\"\n"
        "  type        = string\n"
        "  default     = \"terraform\"\n"
        "}\n\n"
        'variable "mikrotik_password" {\n'
        "  description = \"MikroTik API password\"\n"
        "  type        = string\n"
        "  sensitive   = true\n"
        "}\n\n"
        'variable "mikrotik_insecure" {\n'
        "  description = \"Skip TLS certificate verification\"\n"
        "  type        = bool\n"
        "  default     = true\n"
        "}\n\n"
        'variable "wireguard_private_key" {\n'
        "  description = \"WireGuard private key\"\n"
        "  type        = string\n"
        "  sensitive   = true\n"
        "  default     = \"\"\n"
        "}\n\n"
        'variable "wireguard_peers" {\n'
        "  description = \"WireGuard peers list\"\n"
        "  type        = list(object({\n"
        "    name        = string\n"
        "    public_key  = string\n"
        "    allowed_ips = list(string)\n"
        "    comment     = optional(string)\n"
        "  }))\n"
        "  default = []\n"
        "}\n\n"
        'variable "adguard_password" {\n'
        "  description = \"AdGuard Home admin password (hash)\"\n"
        "  type        = string\n"
        "  sensitive   = true\n"
        "  default     = \"\"\n"
        "}\n\n"
        'variable "tailscale_authkey" {\n'
        "  description = \"Tailscale auth key\"\n"
        "  type        = string\n"
        "  sensitive   = true\n"
        "  default     = \"\"\n"
        "}\n"
    )


def _interfaces_tf(routers: list[str]) -> str:
    return (
        "# Baseline projection output; detailed interface resources are added in parity phase.\n"
        "locals {\n"
        f"  mikrotik_routers = {_render_string_list(routers)}\n"
        "}\n"
    )


def _firewall_tf(networks: list[str]) -> str:
    return (
        "# Baseline projection output; firewall resources are added in parity phase.\n"
        "locals {\n"
        f"  mikrotik_networks_for_firewall = {_render_string_list(networks)}\n"
        "}\n"
    )


def _dhcp_tf(networks: list[str]) -> str:
    return (
        "# Baseline projection output; DHCP resources are added in parity phase.\n"
        "locals {\n"
        f"  mikrotik_networks_for_dhcp = {_render_string_list(networks)}\n"
        "}\n"
    )


def _dns_tf() -> str:
    return (
        "# Baseline projection output; DNS resources are added in parity phase.\n"
        "locals {\n"
        "  mikrotik_dns_enabled = true\n"
        "}\n"
    )


def _addresses_tf(networks: list[str]) -> str:
    return (
        "# Baseline projection output; address resources are added in parity phase.\n"
        "locals {\n"
        f"  mikrotik_networks_for_addresses = {_render_string_list(networks)}\n"
        "}\n"
    )


def _qos_tf() -> str:
    return (
        "# Baseline projection output; QoS resources are added in parity phase.\n"
        "locals {\n"
        "  mikrotik_qos_profiles = []\n"
        "}\n"
    )


def _vpn_tf() -> str:
    return (
        "# Baseline projection output; WireGuard resources are added in parity phase.\n"
        "locals {\n"
        "  wireguard_interface_name = \"wg_home\"\n"
        "}\n"
    )


def _containers_tf(services: list[str]) -> str:
    return (
        "# Baseline projection output; container resources are added in parity phase.\n"
        "locals {\n"
        f"  mikrotik_service_instances = {_render_string_list(services)}\n"
        "}\n"
    )


def _outputs_tf(routers: list[str], networks: list[str], services: list[str]) -> str:
    return (
        'output "projection_counts" {\n'
        "  value = {\n"
        f"    routers  = {len(routers)}\n"
        f"    networks = {len(networks)}\n"
        f"    services = {len(services)}\n"
        "  }\n"
        "}\n"
    )


def _tfvars_example(routers: list[str]) -> str:
    default_host = "https://192.168.88.1:8443"
    if routers:
        default_host = f"https://{routers[0]}:8443"
    return (
        f'mikrotik_host = "{default_host}"\n'
        'mikrotik_username = "terraform"\n'
        'mikrotik_password = "<TODO_MIKROTIK_PASSWORD>"\n'
        "mikrotik_insecure = true\n"
        'wireguard_private_key = "<TODO_WG_PRIVATE_KEY>"\n'
        "wireguard_peers = []\n"
        'adguard_password = "<TODO_ADGUARD_PASSWORD_HASH>"\n'
        'tailscale_authkey = "<TODO_TAILSCALE_AUTHKEY>"\n'
    )

