#!/usr/bin/env python3
"""Copy package-local dist inputs from native roots when local operator files already exist."""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
DEFAULT_DIST = REPO_ROOT / "dist"

INPUT_MAPPINGS = {
    "control/terraform/mikrotik/terraform.tfvars": REPO_ROOT
    / "generated"
    / "terraform"
    / "mikrotik"
    / "terraform.tfvars",
    "control/terraform/proxmox/terraform.tfvars": REPO_ROOT
    / "generated"
    / "terraform"
    / "proxmox"
    / "terraform.tfvars",
    "control/ansible/.vault_pass": REPO_ROOT / "ansible" / ".vault_pass",
    "control/ansible/group_vars/all/vault.yml": REPO_ROOT / "ansible" / "group_vars" / "all" / "vault.yml",
}


def materialize_inputs(dist_root: Path, verbose: bool) -> int:
    """Copy known local inputs from native roots into dist package roots."""
    copied: list[tuple[Path, Path]] = []
    missing: list[tuple[Path, Path]] = []

    for rel_target, source in INPUT_MAPPINGS.items():
        target = dist_root / rel_target
        if source.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            copied.append((source, target))
        else:
            missing.append((source, target))

    if verbose:
        print("=" * 70)
        print("Dist Input Materializer (ADR 0053)")
        print("=" * 70)
        print(f"Dist root: {dist_root}")
        print()
        if copied:
            print("Copied inputs:")
            for source, target in copied:
                print(f"  - {source} -> {target}")
        if missing:
            print()
            print("Missing native inputs:")
            for source, target in missing:
                print(f"  - {source} (target would be {target})")
        print("=" * 70)

    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Materialize dist local inputs from native roots")
    parser.add_argument(
        "--dist",
        type=Path,
        default=DEFAULT_DIST,
        help="Path to dist root",
    )
    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="Suppress summary output",
    )
    args = parser.parse_args()

    sys.exit(materialize_inputs(dist_root=args.dist, verbose=not args.quiet))


if __name__ == "__main__":
    main()
