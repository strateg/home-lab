#!/usr/bin/env python3
"""Proxmox bootstrap package generator CLI."""

from __future__ import annotations

import argparse
from pathlib import Path

from .generator import DEFAULT_OUTPUT_DIR, ProxmoxBootstrapGenerator


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate Proxmox bootstrap package for srv-gamayun")
    parser.add_argument(
        "--topology",
        default="topology.yaml",
        help="Path to topology YAML file (default: topology.yaml)",
    )
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help="Output directory (default: generated/bootstrap/srv-gamayun)",
    )
    args = parser.parse_args()

    generator = ProxmoxBootstrapGenerator(
        topology_path=args.topology,
        output_dir=Path(args.output_dir),
    )
    result = generator.generate()

    print("=" * 70)
    print("Proxmox Bootstrap Package Generator")
    print("=" * 70)
    print()
    for label, path in result.items():
        print(f"{label:24} {path}")
    print()
    print("Next steps:")
    print("  1. Create local/bootstrap/srv-gamayun/answer.override.toml with a real SHA-512 root password hash")
    print("  2. Run: cd deploy && make materialize-native-inputs")
    print("  3. Run create-uefi-autoinstall-proxmox-usb.sh with a Proxmox ISO and target USB device")
    print("  4. After installation, use the packaged post-install scripts on the host")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
