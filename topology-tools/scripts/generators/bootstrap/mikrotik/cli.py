#!/usr/bin/env python3
"""
MikroTik Bootstrap Generator CLI

Generate RouterOS bootstrap script from topology for Terraform automation.

Usage:
    python -m scripts.generators.bootstrap.mikrotik.cli [--topology topology.yaml] [--output-dir DIR]
"""

import argparse
import sys
from pathlib import Path

# Add topology-tools to path
SCRIPT_DIR = Path(__file__).resolve().parent
TOPOLOGY_TOOLS_DIR = SCRIPT_DIR.parent.parent.parent.parent
sys.path.insert(0, str(TOPOLOGY_TOOLS_DIR))

from topology_loader import load_topology

from .generator import MikrotikBootstrapGenerator


def main():
    parser = argparse.ArgumentParser(description="Generate MikroTik bootstrap script from topology")
    parser.add_argument(
        "--topology",
        default="topology.yaml",
        help="Path to topology YAML file (default: topology.yaml)",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Output directory (default: generated/bootstrap/rtr-mikrotik-chateau)",
    )
    parser.add_argument(
        "--password",
        default="CHANGE_THIS_PASSWORD",
        help="Terraform user password placeholder (default: CHANGE_THIS_PASSWORD)",
    )

    args = parser.parse_args()

    print("=" * 70)
    print("MikroTik Bootstrap Generator")
    print("=" * 70)
    print()

    # Load topology
    topology_path = Path(args.topology)
    if not topology_path.exists():
        # Try relative to project root
        project_root = TOPOLOGY_TOOLS_DIR.parent
        topology_path = project_root / args.topology

    if not topology_path.exists():
        print(f"ERROR: Topology file not found: {args.topology}")
        sys.exit(1)

    print(f"Loading topology: {topology_path}")
    topology = load_topology(str(topology_path))
    print("OK Topology loaded")

    # Generate
    output_dir = Path(args.output_dir) if args.output_dir else None
    generator = MikrotikBootstrapGenerator(
        topology=topology,
        output_dir=output_dir,
        terraform_password=args.password,
    )

    print()
    print("Generating bootstrap script...")
    result = generator.generate()

    print()
    print("=" * 70)
    print("Generation Complete!")
    print("=" * 70)
    print()
    print(f"Bootstrap script: {result['bootstrap_script']}")
    print(f"TF vars example:  {result['terraform_vars_example']}")
    print()
    print(f"Router IP:        {result['router_ip']}")
    print(f"REST API URL:     {result['api_url']}")
    print(f"Terraform user:   {result['terraform_user']}")
    print(f"Password value:   {result['terraform_password']}")

    print()
    print("Next steps:")
    print("  1. Preferred day-0 path: run 'cd deploy && make assemble-native'")
    print("  2. Use netinstall-cli with .work/native/bootstrap/rtr-mikrotik-chateau/init-terraform.rsc")
    print("  3. Fallback only: import the generated init-terraform.rsc manually or use the legacy SSH helper")
    print("  4. Replace placeholder password before real bootstrap or immediately after fallback import")
    print("  5. Copy terraform.tfvars.example to local/terraform/mikrotik/terraform.tfvars")
    print()


if __name__ == "__main__":
    main()
