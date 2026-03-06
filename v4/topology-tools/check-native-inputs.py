#!/usr/bin/env python3
"""Validate that canonical local inputs exist for native execution packages."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from utils.local_inputs import LOCAL_ROOT

REPO_ROOT = Path(__file__).resolve().parents[2]

PACKAGE_INPUTS = {
    "control/terraform/mikrotik": [
        LOCAL_ROOT / "terraform" / "mikrotik" / "terraform.tfvars",
    ],
    "control/terraform/proxmox": [
        LOCAL_ROOT / "terraform" / "proxmox" / "terraform.tfvars",
    ],
    "control/ansible": [
        REPO_ROOT / "ansible" / ".vault_pass",
        REPO_ROOT / "ansible" / "group_vars" / "all" / "vault.yml",
    ],
    "bootstrap/srv-gamayun": [
        LOCAL_ROOT / "bootstrap" / "srv-gamayun" / "answer.override.toml",
    ],
    "bootstrap/srv-orangepi5": [
        LOCAL_ROOT / "bootstrap" / "srv-orangepi5" / "cloud-init" / "user-data",
    ],
}


def check_package(package_id: str, verbose: bool) -> int:
    """Check canonical native local inputs for a package."""
    inputs = PACKAGE_INPUTS.get(package_id)
    if inputs is None:
        print(f"ERROR unknown native package '{package_id}'")
        return 1

    missing = [path for path in inputs if not path.exists()]
    if missing:
        print(f"ERROR native package '{package_id}' is not ready")
        for path in missing:
            print(f"  - missing {path}")
        return 1

    if verbose:
        print(f"OK native package '{package_id}' is ready")
        for path in inputs:
            print(f"  input: {path}")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Check canonical local inputs for native execution")
    parser.add_argument("package_id", help="Package id, for example control/terraform/proxmox")
    parser.add_argument("-q", "--quiet", action="store_true", help="Suppress success output")
    args = parser.parse_args()
    sys.exit(check_package(args.package_id, verbose=not args.quiet))


if __name__ == "__main__":
    main()
