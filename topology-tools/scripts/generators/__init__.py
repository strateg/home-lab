"""Generator domains for infrastructure outputs.

This package provides generators for various infrastructure formats:

- terraform.proxmox: Proxmox VE Terraform configuration
- terraform.mikrotik: MikroTik RouterOS Terraform configuration
- docs: Documentation generation with Mermaid diagrams
- common: Shared base classes and utilities

Usage:
    from scripts.generators.terraform import TerraformGenerator, MikrotikTerraformGenerator
    from scripts.generators.docs import DocumentationGenerator
    from scripts.generators.common import Generator, GeneratorCLI
"""

from .common import Generator, GeneratorCLI, load_and_validate_layered_topology
from .docs import DocumentationGenerator
from .terraform import MikrotikTerraformGenerator, TerraformGenerator

__all__ = [
    # Base classes
    "Generator",
    "GeneratorCLI",
    # Utilities
    "load_and_validate_layered_topology",
    # Generators
    "DocumentationGenerator",
    "MikrotikTerraformGenerator",
    "TerraformGenerator",
]
