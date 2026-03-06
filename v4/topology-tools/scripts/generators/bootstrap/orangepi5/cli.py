#!/usr/bin/env python3
"""Orange Pi 5 cloud-init bootstrap generator CLI."""

from __future__ import annotations

import argparse
from pathlib import Path

from .generator import DEFAULT_OUTPUT_DIR, OrangePi5CloudInitGenerator


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate Orange Pi 5 cloud-init bootstrap package from topology")
    parser.add_argument(
        "--topology",
        default="v4/topology.yaml",
        help="Path to topology YAML file (default: topology.yaml)",
    )
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help="Output directory (default: v4-generated/bootstrap/srv-orangepi5/cloud-init)",
    )
    args = parser.parse_args()

    generator = OrangePi5CloudInitGenerator(
        topology_path=args.topology,
        output_dir=Path(args.output_dir),
    )
    result = generator.generate()

    print("=" * 70)
    print("Orange Pi 5 Cloud-Init Generator")
    print("=" * 70)
    print()
    for label, path in result.items():
        print(f"{label:18} {path}")
    print()
    print("Next steps:")
    print("  1. Review user-data.example and materialize a local user-data if needed")
    print("  2. Copy the cloud-init files to the Orange Pi boot media")
    print("  3. Boot the device and continue with deploy automation")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
