"""Terraform generator domains.

Provides Terraform configuration generators for:
- Proxmox VE (VMs, LXC, bridges, storage)
- MikroTik RouterOS (interfaces, firewall, VPN, QoS)
"""

from .mikrotik import MikrotikTerraformCLI, MikrotikTerraformGenerator
from .proxmox import ProxmoxTerraformCLI, TerraformGenerator

__all__ = [
    "MikrotikTerraformCLI",
    "MikrotikTerraformGenerator",
    "ProxmoxTerraformCLI",
    "TerraformGenerator",
]
