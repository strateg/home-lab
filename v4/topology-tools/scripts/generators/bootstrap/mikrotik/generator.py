"""Generate a release-safe MikroTik bootstrap package from topology."""

import ipaddress
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from jinja2 import Environment, FileSystemLoader

# Resolve paths relative to this file
SCRIPT_DIR = Path(__file__).resolve().parent
TOPOLOGY_TOOLS_DIR = SCRIPT_DIR.parent.parent.parent.parent
TEMPLATES_DIR = TOPOLOGY_TOOLS_DIR / "templates" / "bootstrap" / "mikrotik"
REPO_ROOT = TOPOLOGY_TOOLS_DIR.parent.parent
DEFAULT_OUTPUT_DIR = REPO_ROOT / "v4-generated" / "bootstrap" / "rtr-mikrotik-chateau"
DEFAULT_TERRAFORM_PASSWORD_PLACEHOLDER = "CHANGE_THIS_PASSWORD"  # pragma: allowlist secret


class MikrotikBootstrapGenerator:
    """Generate MikroTik day-0 bootstrap script from topology."""

    def __init__(
        self,
        topology: Dict[str, Any],
        output_dir: Optional[Path] = None,
        terraform_password: str = DEFAULT_TERRAFORM_PASSWORD_PLACEHOLDER,
    ):
        self.topology = topology
        self.output_dir = Path(output_dir) if output_dir else DEFAULT_OUTPUT_DIR
        self.terraform_password = terraform_password

        # Jinja2 environment
        self.env = Environment(
            loader=FileSystemLoader(str(TEMPLATES_DIR)),
            trim_blocks=True,
            lstrip_blocks=True,
        )

        # Extract data from topology
        self._extract_config()

    def _extract_config(self) -> None:
        """Extract configuration from topology."""
        # Get L0 meta
        l0 = self.topology.get("L0_meta", {})
        self.topology_version = l0.get("version", "unknown")

        # Get L1 device info
        self._extract_device_info()

        # Get L2 network info
        self._extract_network_info()

        # Get L5 DNS info
        self._extract_dns_info()

    def _extract_device_info(self) -> None:
        """Extract MikroTik device information from L1."""
        l1 = self.topology.get("L1_foundation", {})
        devices = l1.get("devices", [])

        # Find MikroTik router
        mikrotik = None
        for device in devices:
            if isinstance(device, dict):
                if device.get("type") == "router" and "mikrotik" in device.get("id", "").lower():
                    mikrotik = device
                    break

        if mikrotik:
            self.router_name = mikrotik.get("name", "MikroTik-Router")
            self.router_id = mikrotik.get("id", "mikrotik-router")
        else:
            self.router_name = "MikroTik-Router"
            self.router_id = "mikrotik-router"

        # Router hostname (short name for certificate)
        self.router_hostname = "router"
        # Fallback management interface for optional backup/rsc paths.
        self.mgmt_interface = "bridge"

    def _extract_network_info(self) -> None:
        """Extract network configuration from L2."""
        l2 = self.topology.get("L2_network", {})
        networks = l2.get("networks", [])

        # Find LAN network - prioritize by id "net-lan"
        lan_network = None

        # First pass: look for net-lan specifically
        for net in networks:
            if isinstance(net, dict) and net.get("id") == "net-lan":
                lan_network = net
                break

        # Second pass: look for any network with "lan" in name managed by MikroTik
        if not lan_network:
            for net in networks:
                if isinstance(net, dict):
                    net_id = net.get("id", "").lower()
                    net_name = net.get("name", "").lower()
                    managed_by = net.get("managed_by_ref", "").lower()
                    if ("lan" in net_id or "lan" in net_name) and "mikrotik" in managed_by:
                        lan_network = net
                        break

        if lan_network:
            self.router_ip = lan_network.get("gateway", "192.168.88.1")
            self.lan_cidr = lan_network.get("cidr", "192.168.88.0/24")
            self.lan_network = self.lan_cidr
        else:
            # Fallback to defaults
            self.router_ip = "192.168.88.1"
            self.lan_cidr = "192.168.88.0/24"
            self.lan_network = self.lan_cidr

        # Prefix-aware router address (avoid hardcoded /24 in templates).
        try:
            self.router_prefix = ipaddress.ip_network(self.lan_network, strict=False).prefixlen
        except ValueError:
            self.router_prefix = 24
        self.router_address = f"{self.router_ip}/{self.router_prefix}"

        # Prefer topology allocation hint for management interface if present.
        if isinstance(lan_network, dict):
            allocations = lan_network.get("ip_allocations", [])
            for alloc in allocations:
                if not isinstance(alloc, dict):
                    continue
                if alloc.get("ip") == self.router_ip and alloc.get("interface"):
                    self.mgmt_interface = alloc["interface"]
                    break

        # Find management network for API access allowance.
        mgmt_network = None

        for net in networks:
            if isinstance(net, dict) and net.get("id") in ("net-management", "net-mgmt"):
                mgmt_network = net
                break

        if not mgmt_network:
            for net in networks:
                if not isinstance(net, dict):
                    continue
                net_id = net.get("id", "").lower()
                net_name = net.get("name", "").lower()
                managed_by = net.get("managed_by_ref", "").lower()
                is_mgmt = "management" in net_id or "mgmt" in net_id or "management" in net_name or "mgmt" in net_name
                if is_mgmt and "mikrotik" in managed_by:
                    mgmt_network = net
                    break

        if mgmt_network:
            mgmt_cidr = mgmt_network.get("cidr")
            self.mgmt_network = mgmt_cidr if mgmt_cidr else self.lan_network
        else:
            self.mgmt_network = self.lan_network

        # Day-0 API allowance is anchored to the management network when defined.
        self.api_access_network = self.mgmt_network if mgmt_network else self.lan_network

    def _extract_dns_info(self) -> None:
        """Extract DNS configuration from L5."""
        l5 = self.topology.get("L5_application", {})
        dns_config = l5.get("dns", {})

        # Get domain
        zones = dns_config.get("zones", [])
        if zones and isinstance(zones[0], dict):
            self.dns_domain = zones[0].get("domain", "lan")
        else:
            self.dns_domain = "lan"

        # Get upstream DNS servers
        forwarders = dns_config.get("forwarders", {})
        self.dns_servers = forwarders.get("upstream", ["1.1.1.1", "8.8.8.8"])

    def generate(self) -> Dict[str, Any]:
        """Generate bootstrap scripts and return metadata."""
        # Ensure output directory exists
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Prepare template context
        context = {
            "topology_version": self.topology_version,
            "generation_timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "router_name": self.router_name,
            "router_hostname": self.router_hostname,
            "router_ip": self.router_ip,
            "router_address": self.router_address,
            "lan_network": self.lan_network,
            "mgmt_network": self.mgmt_network,
            "api_access_network": self.api_access_network,
            "mgmt_interface": self.mgmt_interface,
            "dns_domain": self.dns_domain,
            "dns_servers": self.dns_servers,
            "api_port": 8443,
            "terraform_user": "terraform",
            "terraform_group": "terraform",
            "terraform_password": self.terraform_password,
        }

        # Path A (canonical): minimal day-0 handover template.
        template_minimal = self.env.get_template("init-terraform-minimal.rsc.j2")
        output_file = self.output_dir / "init-terraform.rsc"
        output_file.write_text(template_minimal.render(**context), encoding="utf-8")

        # Optional Path B/C artifacts used by compatibility runbooks.
        template_backup = self.env.get_template("backup-restore-overrides.rsc.j2")
        output_file_backup = self.output_dir / "backup-restore-overrides.rsc"
        output_file_backup.write_text(template_backup.render(**context), encoding="utf-8")

        template_rsc = self.env.get_template("exported-config-safe.rsc.j2")
        output_file_rsc = self.output_dir / "exported-config-safe.rsc"
        output_file_rsc.write_text(template_rsc.render(**context), encoding="utf-8")

        # Generate release-safe terraform.tfvars example.
        tfvars_content = self._generate_tfvars_example(context)
        tfvars_file = self.output_dir / "terraform.tfvars.example"
        tfvars_file.write_text(tfvars_content, encoding="utf-8")

        return {
            "bootstrap_script": str(output_file),
            "bootstrap_script_backup": str(output_file_backup),
            "bootstrap_script_rsc": str(output_file_rsc),
            "terraform_vars_example": str(tfvars_file),
            "router_ip": self.router_ip,
            "api_url": f"https://{self.router_ip}:{context['api_port']}",
            "terraform_user": context["terraform_user"],
            "terraform_password": self.terraform_password,
        }

    def _generate_tfvars_example(self, context: Dict[str, Any]) -> str:
        """Generate a release-safe Terraform variables example file."""
        return f"""# =============================================================================
# MikroTik Terraform Variables Example
# Generated from topology v{context["topology_version"]}
# Generated at: {context["generation_timestamp"]}
# =============================================================================
# Copy this file to local/terraform/mikrotik/terraform.tfvars and replace
# placeholder values, then run `cd deploy && make assemble-native`.

mikrotik_host     = "https://{context["router_ip"]}:{context["api_port"]}"
mikrotik_username = "{context["terraform_user"]}"
mikrotik_password = "{context["terraform_password"]}"
mikrotik_insecure = true  # Self-signed certificate

# WireGuard VPN (generate keys: wg genkey | tee privatekey | wg pubkey > publickey)
wireguard_private_key = ""

# WireGuard Peers
wireguard_peers = []

# Container Configuration (optional)
adguard_password  = ""
tailscale_authkey = ""
"""


def generate_from_topology(
    topology: Dict[str, Any],
    output_dir: Optional[Path] = None,
    terraform_password: str = DEFAULT_TERRAFORM_PASSWORD_PLACEHOLDER,
) -> Dict[str, Any]:
    """Convenience function to generate bootstrap script."""
    generator = MikrotikBootstrapGenerator(
        topology=topology,
        output_dir=output_dir,
        terraform_password=terraform_password,
    )
    return generator.generate()
