"""Terraform generator domains.

Provides Terraform configuration generators for:
- Proxmox VE (VMs, LXC, bridges, storage)
- MikroTik RouterOS (interfaces, firewall, VPN, QoS)
"""

from .base import TerraformGeneratorBase
from .mikrotik import MikrotikTerraformCLI, MikrotikTerraformGenerator
from .proxmox import ProxmoxTerraformCLI, TerraformGenerator
from .resolvers import build_storage_map, resolve_interface_names, resolve_lxc_resources

__all__ = [
    "MikrotikTerraformCLI",
    "MikrotikTerraformGenerator",
    "ProxmoxTerraformCLI",
    "TerraformGeneratorBase",
    "TerraformGenerator",
    "build_storage_map",
    "resolve_interface_names",
    "resolve_lxc_resources",
]
