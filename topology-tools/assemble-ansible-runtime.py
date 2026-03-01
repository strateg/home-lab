#!/usr/bin/env python3
"""
Assemble Ansible runtime inventory from generated and manual sources.

Part of ADR 0051: Ansible Runtime, Inventory, and Secret Boundaries

This assembler creates the effective runtime inventory used by Ansible operators:
- Copies generated hosts.yml unchanged
- Creates layered group_vars (10-generated.yml, 90-manual.yml)
- Copies host_vars with conflict detection

Usage:
    python3 topology-tools/assemble-ansible-runtime.py

Output:
    generated/ansible/runtime/production/
"""

import argparse
import shutil
import sys
from pathlib import Path

from utils.package_policy import validate_no_forbidden_topology_overrides, validate_no_secret_content

# Paths relative to repository root
REPO_ROOT = Path(__file__).parent.parent
DEFAULT_ENV = "production"
GENERATED_INV = REPO_ROOT / "generated" / "ansible" / "inventory" / DEFAULT_ENV
MANUAL_INV = REPO_ROOT / "ansible/inventory-overrides/production"
RUNTIME_INV = REPO_ROOT / "generated/ansible/runtime/production"


def assemble_runtime_inventory(
    generated_dir: Path = GENERATED_INV,
    manual_dir: Path = MANUAL_INV,
    runtime_dir: Path = RUNTIME_INV,
    allowlist: list[str] = None,
    verbose: bool = True,
) -> bool:
    """
    Assemble runtime inventory from generated and manual sources.

    Returns True on success, False on failure.
    """
    allowlist = allowlist or []
    errors = []

    if verbose:
        print("=" * 70)
        print("Ansible Runtime Inventory Assembler (ADR 0051)")
        print("=" * 70)
        print()

    # Validate inputs exist
    if not generated_dir.exists():
        print(f"ERROR Generated inventory not found: {generated_dir}")
        return False

    if verbose:
        print(f"  Generated source: {generated_dir}")
        print(f"  Manual overrides: {manual_dir}")
        print(f"  Runtime output:   {runtime_dir}")
        print()

    # Clean and create output directory
    if runtime_dir.exists():
        shutil.rmtree(runtime_dir)
        if verbose:
            print(f"CLEAN Removed existing runtime directory")

    runtime_dir.mkdir(parents=True)
    if verbose:
        print(f"DIR   Created runtime directory: {runtime_dir}")

    # 1. Copy generated hosts.yml unchanged
    generated_hosts = generated_dir / "hosts.yml"
    if not generated_hosts.exists():
        print(f"ERROR Generated hosts.yml not found: {generated_hosts}")
        return False

    shutil.copy(generated_hosts, runtime_dir / "hosts.yml")
    if verbose:
        print(f"COPY  hosts.yml (generated, unchanged)")

    # 2. Create layered group_vars
    group_vars_dir = runtime_dir / "group_vars" / "all"
    group_vars_dir.mkdir(parents=True)

    # 2a. Generated group_vars becomes 10-generated.yml
    generated_gv = generated_dir / "group_vars" / "all.yml"
    if generated_gv.exists():
        # Validate no secrets in generated
        violations = validate_no_secret_content(generated_gv)
        errors.extend(violations)

        shutil.copy(generated_gv, group_vars_dir / "10-generated.yml")
        if verbose:
            print(f"COPY  group_vars/all/10-generated.yml (from generated)")

    # 2b. Manual group_vars becomes 90-manual.yml
    manual_gv = manual_dir / "group_vars" / "all.yml"
    if manual_gv.exists():
        # Validate no secrets in manual overrides
        violations = validate_no_secret_content(manual_gv)
        errors.extend(violations)

        shutil.copy(manual_gv, group_vars_dir / "90-manual.yml")
        if verbose:
            print(f"COPY  group_vars/all/90-manual.yml (from manual overrides)")
    else:
        if verbose:
            print(f"SKIP  No manual group_vars/all.yml found")

    # 3. Copy host_vars
    host_vars_dir = runtime_dir / "host_vars"
    host_vars_dir.mkdir(parents=True)

    # 3a. Copy generated host_vars first
    generated_hv_dir = generated_dir / "host_vars"
    if generated_hv_dir.exists():
        for hv_file in generated_hv_dir.glob("*.yml"):
            violations = validate_no_secret_content(hv_file)
            errors.extend(violations)

            shutil.copy(hv_file, host_vars_dir / hv_file.name)
            if verbose:
                print(f"COPY  host_vars/{hv_file.name} (from generated)")

    # 3b. Copy manual host_vars as overlays
    manual_hv_dir = manual_dir / "host_vars"
    if manual_hv_dir.exists():
        for hv_file in manual_hv_dir.glob("*.yml"):
            # Skip example files
            if hv_file.name.endswith(".example"):
                continue

            # Validate no secrets
            violations = validate_no_secret_content(hv_file)
            errors.extend(violations)

            # Validate no forbidden overrides (unless in allowlist)
            violations = validate_no_forbidden_topology_overrides(hv_file, allowlist)
            errors.extend(violations)

            # Check for conflicts with generated host_vars
            target_file = host_vars_dir / hv_file.name
            if target_file.exists() and hv_file.name not in allowlist:
                errors.append(
                    f"CONFLICT: {hv_file} conflicts with generated host_vars. "
                    f"Add to allowlist if intentional override."
                )
                continue

            shutil.copy(hv_file, host_vars_dir / hv_file.name)
            if verbose:
                print(f"COPY  host_vars/{hv_file.name} (from manual overrides)")

    # Report results
    print()
    if errors:
        print("=" * 70)
        print("ERRORS FOUND:")
        print("=" * 70)
        for error in errors:
            print(f"  - {error}")
        print()
        print(f"ERROR Assembly failed with {len(errors)} error(s)")
        return False

    if verbose:
        print("=" * 70)
        print(f"OK    Runtime inventory assembled: {runtime_dir}")
        print()
        print("Next steps:")
        print(f"  1. Validate: ansible-inventory -i {runtime_dir} --list > /dev/null")
        print(f"  2. Compare:  diff old-inventory.json new-inventory.json")
        print("=" * 70)

    return True


def main():
    parser = argparse.ArgumentParser(description="Assemble Ansible runtime inventory (ADR 0051)")
    parser.add_argument(
        "--generated",
        type=Path,
        default=GENERATED_INV,
        help="Path to generated inventory",
    )
    parser.add_argument(
        "--manual",
        type=Path,
        default=MANUAL_INV,
        help="Path to manual overrides",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=RUNTIME_INV,
        help="Path for runtime inventory output",
    )
    parser.add_argument(
        "--allowlist",
        type=str,
        nargs="*",
        default=[],
        help="Host_vars files allowed to override topology-owned facts",
    )
    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="Suppress verbose output",
    )

    args = parser.parse_args()

    success = assemble_runtime_inventory(
        generated_dir=args.generated,
        manual_dir=args.manual,
        runtime_dir=args.output,
        allowlist=args.allowlist,
        verbose=not args.quiet,
    )

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
