"""Generate a topology-backed Orange Pi 5 cloud-init bootstrap package."""

from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader

from scripts.generators.common import load_and_validate_layered_topology

SCRIPT_DIR = Path(__file__).resolve().parent
TOPOLOGY_TOOLS_DIR = SCRIPT_DIR.parent.parent.parent.parent
TEMPLATES_DIR = TOPOLOGY_TOOLS_DIR / "templates" / "bootstrap" / "orangepi5"
DEFAULT_OUTPUT_DIR = TOPOLOGY_TOOLS_DIR.parent / "generated" / "bootstrap" / "srv-orangepi5" / "cloud-init"
DEFAULT_CLOUD_INIT_USER = "ubuntu"
DEFAULT_SSH_KEY_PLACEHOLDER = "ssh-ed25519 REPLACE_WITH_YOUR_PUBLIC_KEY orangepi5-bootstrap"


class OrangePi5CloudInitGenerator:
    """Generate a release-safe cloud-init package for Orange Pi 5."""

    def __init__(
        self,
        topology_path: str,
        output_dir: Path | None = None,
    ):
        self.topology_path = Path(topology_path)
        self.output_dir = Path(output_dir) if output_dir else DEFAULT_OUTPUT_DIR
        self.topology, version_warning = load_and_validate_layered_topology(
            self.topology_path,
            required_sections=[
                "L0_meta",
                "L1_foundation",
                "L2_network",
                "L5_application",
                "L7_operations",
            ],
        )
        if version_warning:
            print(f"WARN  {version_warning}")

        self.env = Environment(
            loader=FileSystemLoader(str(TEMPLATES_DIR)),
            trim_blocks=True,
            lstrip_blocks=True,
        )
        self.context = self._build_context()

    def _find_device(self, device_id: str) -> dict[str, Any]:
        devices = self.topology.get("L1_foundation", {}).get("devices", [])
        for device in devices:
            if isinstance(device, dict) and device.get("id") == device_id:
                return device
        raise ValueError(f"Device not found in topology: {device_id}")

    def _dns_domain(self) -> str:
        zones = self.topology.get("L5_application", {}).get("dns", {}).get("zones", [])
        if zones and isinstance(zones[0], dict):
            return zones[0].get("domain", "home.local")
        return "home.local"

    def _ip_for_host_os(self, host_os_ref: str, network_id: str) -> str | None:
        networks = self.topology.get("L2_network", {}).get("networks", [])
        for network in networks:
            if not isinstance(network, dict) or network.get("id") != network_id:
                continue
            allocations = network.get("ip_allocations", [])
            for allocation in allocations:
                if allocation.get("host_os_ref") == host_os_ref:
                    return allocation.get("ip")
        return None

    def _authorized_keys_for_device(self, device_id: str) -> list[str]:
        security = self.topology.get("L7_operations", {}).get("security", {})
        ssh_keys = security.get("ssh_keys", [])
        keys: list[str] = []
        for entry in ssh_keys:
            if not isinstance(entry, dict):
                continue
            for target in entry.get("authorized_for", []):
                if isinstance(target, dict) and target.get("device_ref") == device_id:
                    public_key = entry.get("public_key")
                    if public_key:
                        keys.append(public_key)
                        break
        return keys

    def _build_context(self) -> dict[str, Any]:
        device = self._find_device("srv-orangepi5")
        host_os_ref = "hos-srv-orangepi5-ubuntu"
        device_id = device["id"]
        domain = self._dns_domain()
        authorized_keys = self._authorized_keys_for_device(device_id)

        return {
            "device_id": device_id,
            "device_name": device.get("name", "Orange Pi 5"),
            "generation_timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "topology_version": self.topology.get("L0_meta", {}).get("version", "unknown"),
            "hostname": device_id,
            "fqdn": f"{device_id}.{domain}",
            "cloud_init_user": DEFAULT_CLOUD_INIT_USER,
            "ssh_authorized_keys": authorized_keys,
            "ssh_key_placeholder": DEFAULT_SSH_KEY_PLACEHOLDER,  # pragma: allowlist secret
            "has_topology_keys": bool(authorized_keys),
            "lan_ip": self._ip_for_host_os(host_os_ref, "net-lan"),
            "management_ip": self._ip_for_host_os(host_os_ref, "net-management"),
        }

    def _render(self, template_name: str) -> str:
        template = self.env.get_template(template_name)
        return template.render(**self.context)

    def generate(self) -> dict[str, str]:
        """Generate the cloud-init package under generated/bootstrap/srv-orangepi5/cloud-init."""
        if self.output_dir.exists():
            shutil.rmtree(self.output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        files = {
            "meta-data": self._render("meta-data.j2"),
            "user-data.example": self._render("user-data.example.j2"),
            "README.md": self._render("README.md.j2"),
        }

        generated_paths: dict[str, str] = {}
        for filename, content in files.items():
            path = self.output_dir / filename
            path.write_text(content)
            generated_paths[filename] = str(path)

        return generated_paths
