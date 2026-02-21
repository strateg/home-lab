"""CLI entrypoint for Proxmox Terraform generation."""

from __future__ import annotations

import argparse
import sys
from typing import Sequence

from scripts.generators.common import GeneratorCLI, run_cli
from .generator import TerraformGenerator


class ProxmoxTerraformCLI(GeneratorCLI):
    """CLI for Proxmox Terraform configuration generator."""

    description = "Generate Terraform configuration from topology v4.0"
    banner = "Terraform Configuration Generator (Topology v4.0)"
    default_output = "generated/terraform"
    success_message = "Terraform generation completed successfully!"


def build_parser() -> argparse.ArgumentParser:
    """Build argument parser (for backwards compatibility)."""
    return ProxmoxTerraformCLI(TerraformGenerator).build_parser()


def main(argv: Sequence[str] | None = None) -> int:
    """Main entry point."""
    return run_cli(ProxmoxTerraformCLI(TerraformGenerator), argv)


if __name__ == "__main__":
    sys.exit(main())
