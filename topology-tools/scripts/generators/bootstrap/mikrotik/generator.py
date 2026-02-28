"""
MikroTik Bootstrap Script Generator

Generates RouterOS bootstrap script from topology for Terraform automation.
"""

import secrets
import string
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from jinja2 import Environment, FileSystemLoader

# Resolve paths relative to this file
SCRIPT_DIR = Path(__file__).resolve().parent
TOPOLOGY_TOOLS_DIR = SCRIPT_DIR.parent.parent.parent.parent
TEMPLATES_DIR = TOPOLOGY_TOOLS_DIR / "templates" / "bootstrap" / "mikrotik"
DEFAULT_OUTPUT_DIR = TOPOLOGY_TOOLS_DIR.parent / "generated" / "bootstrap" / "rtr-mikrotik-chateau"


class MikrotikBootstrapGenerator:
    """Generate MikroTik bootstrap script from topology."""

    def __init__(
        self,
        topology: Dict[str, Any],
        output_dir: Optional[Path] = None,
        terraform_password: Optional[str] = None,
    ):
        self.topology = topology
        self.output_dir = Path(output_dir) if output_dir else DEFAULT_OUTPUT_DIR
        self.terraform_password = terraform_password or self._generate_password()

        # Jinja2 environment
        self.env = Environment(
            loader=FileSystemLoader(str(TEMPLATES_DIR)),
            trim_blocks=True,
            lstrip_blocks=True,
        )

        # Extract data from topology
        self._extract_config()

    def _generate_password(self, length: int = 20) -> str:
        """Generate a secure random password."""
        alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
        # Ensure at least one of each required character type
        password = [
            secrets.choice(string.ascii_uppercase),
            secrets.choice(string.ascii_lowercase),
            secrets.choice(string.digits),
            secrets.choice("!@#$%^&*"),
        ]
        # Fill the rest
        password += [secrets.choice(alphabet) for _ in range(length - 4)]
        # Shuffle
        secrets.SystemRandom().shuffle(password)
        return "".join(password)

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
            self.lan_network = "192.168.88.0/24"

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
        """Generate bootstrap script and return metadata."""
        # Ensure output directory exists
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Prepare template context
        context = {
            "topology_version": self.topology_version,
            "generation_timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "router_name": self.router_name,
            "router_hostname": self.router_hostname,
            "router_ip": self.router_ip,
            "lan_network": self.lan_network,
            "dns_domain": self.dns_domain,
            "dns_servers": self.dns_servers,
            "api_port": 8443,
            "terraform_user": "terraform",
            "terraform_group": "terraform",
            "terraform_password": self.terraform_password,
        }

        # Render template
        template = self.env.get_template("init-terraform.rsc.j2")
        content = template.render(**context)

        # Write output file
        output_file = self.output_dir / "init-terraform.rsc"
        output_file.write_text(content)

        # Generate terraform.tfvars
        tfvars_content = self._generate_tfvars(context)
        tfvars_file = self.output_dir / "terraform.tfvars"
        tfvars_file.write_text(tfvars_content)

        return {
            "bootstrap_script": str(output_file),
            "terraform_vars": str(tfvars_file),
            "router_ip": self.router_ip,
            "api_url": f"https://{self.router_ip}:{context['api_port']}",
            "terraform_user": context["terraform_user"],
            "terraform_password": self.terraform_password,
        }

    def _generate_tfvars(self, context: Dict[str, Any]) -> str:
        """Generate terraform.tfvars file."""
        return f'''# =============================================================================
# MikroTik Terraform Variables
# Generated from topology v{context["topology_version"]}
# Generated at: {context["generation_timestamp"]}
# =============================================================================

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
'''


def generate_from_topology(
    topology: Dict[str, Any],
    output_dir: Optional[Path] = None,
    terraform_password: Optional[str] = None,
) -> Dict[str, Any]:
    """Convenience function to generate bootstrap script."""
    generator = MikrotikBootstrapGenerator(
        topology=topology,
        output_dir=output_dir,
        terraform_password=terraform_password,
    )
    return generator.generate()
