"""CLI entrypoint for MikroTik Terraform generation."""

from __future__ import annotations

import argparse
import sys
from typing import Sequence

from scripts.generators.common import GeneratorCLI, run_cli
from .generator import MikrotikTerraformGenerator


class MikrotikTerraformCLI(GeneratorCLI):
    """CLI for MikroTik Terraform configuration generator."""

    description = "Generate MikroTik RouterOS Terraform configuration from topology v4.0"
    banner = "MikroTik Terraform Generator (Topology v4.0)"
    default_output = "generated/terraform-mikrotik"
    success_message = "MikroTik Terraform generation completed successfully!"

    def run_generator(self, generator: MikrotikTerraformGenerator) -> bool:
        """Execute the MikroTik generator workflow with data extraction step."""
        if not generator.load_topology():
            return False

        print("\nSUMMARY Extracting MikroTik configuration...\n")

        if not generator.extract_mikrotik_data():
            print("\nERROR Failed to extract MikroTik data")
            return False

        print("\nGEN Generating Terraform files...\n")

        if not generator.generate_all():
            print("\nERROR Generation failed with errors")
            return False

        generator.print_summary()
        return True


def build_parser() -> argparse.ArgumentParser:
    """Build argument parser (for backwards compatibility)."""
    return MikrotikTerraformCLI(MikrotikTerraformGenerator).build_parser()


def main(argv: Sequence[str] | None = None) -> int:
    """Main entry point."""
    return run_cli(MikrotikTerraformCLI(MikrotikTerraformGenerator), argv)


if __name__ == "__main__":
    sys.exit(main())
