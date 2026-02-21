"""Terraform generator domains."""

from .proxmox import TerraformGenerator
from .mikrotik import MikrotikTerraformGenerator

__all__ = ["TerraformGenerator", "MikrotikTerraformGenerator"]
