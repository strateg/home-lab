"""CLI entrypoint for Proxmox Terraform generation."""

from __future__ import annotations

import argparse
import sys

from .generator import TerraformGenerator


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate Terraform configuration from topology v4.0"
    )
    parser.add_argument(
        "--topology",
        default="topology.yaml",
        help="Path to topology YAML file"
    )
    parser.add_argument(
        "--output",
        default="generated/terraform",
        help="Output directory for Terraform files (default: generated/terraform/)"
    )
    parser.add_argument(
        "--templates",
        default="topology-tools/templates",
        help="Directory containing Terraform Jinja2 templates"
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    generator = TerraformGenerator(args.topology, args.output, args.templates)

    print("=" * 70)
    print("Terraform Configuration Generator (Topology v4.0)")
    print("=" * 70)
    print()

    if not generator.load_topology():
        return 1

    print("\nGEN Generating Terraform files...\n")

    if not generator.generate_all():
        print("\nERROR Generation failed with errors")
        return 1

    generator.print_summary()
    print("\nOK Terraform generation completed successfully!\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
