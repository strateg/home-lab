#!/usr/bin/env python3
"""Check that dist execution roots remain in parity with native deploy roots."""

from __future__ import annotations

import argparse
import configparser
import hashlib
import sys
from pathlib import Path

from utils.package_policy import is_local_secret_path

REPO_ROOT = Path(__file__).parent.parent
DEFAULT_DIST = REPO_ROOT / "dist"


def sha256(path: Path) -> str:
    """Return a stable file hash."""
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def compare_file_sets(
    label: str,
    native_root: Path,
    dist_root: Path,
    ignored_native: set[str] | None = None,
    ignored_dist: set[str] | None = None,
) -> list[str]:
    """Compare file lists and contents between two roots."""
    ignored_native = ignored_native or set()
    ignored_dist = ignored_dist or set()

    native_files = {
        str(path.relative_to(native_root)).replace("\\", "/"): path for path in native_root.rglob("*") if path.is_file()
    }
    dist_files = {
        str(path.relative_to(dist_root)).replace("\\", "/"): path for path in dist_root.rglob("*") if path.is_file()
    }

    native_files = {rel: path for rel, path in native_files.items() if not is_local_secret_path(Path(rel))}
    dist_files = {rel: path for rel, path in dist_files.items() if not is_local_secret_path(Path(rel))}

    for ignored in ignored_native:
        native_files.pop(ignored, None)
    for ignored in ignored_dist:
        dist_files.pop(ignored, None)

    errors: list[str] = []

    missing_in_dist = sorted(set(native_files) - set(dist_files))
    extra_in_dist = sorted(set(dist_files) - set(native_files))
    if missing_in_dist:
        errors.append(f"{label}: missing files in dist: {', '.join(missing_in_dist)}")
    if extra_in_dist:
        errors.append(f"{label}: extra files in dist: {', '.join(extra_in_dist)}")

    for rel_path in sorted(set(native_files) & set(dist_files)):
        if sha256(native_files[rel_path]) != sha256(dist_files[rel_path]):
            errors.append(f"{label}: content mismatch for {rel_path}")

    return errors


def check_ansible_cfg(package_root: Path) -> list[str]:
    """Validate package-local ansible.cfg semantics for dist execution."""
    config_path = package_root / "ansible.cfg"
    parser = configparser.ConfigParser()
    parser.read(config_path)

    errors: list[str] = []
    defaults = parser["defaults"] if parser.has_section("defaults") else {}

    if defaults.get("inventory") != "./inventory":
        errors.append("control/ansible: ansible.cfg must set inventory = ./inventory")
    if ".vault_pass" not in defaults.get("vault_password_file", ""):
        errors.append("control/ansible: ansible.cfg must reference package-local .vault_pass")

    roles_path = defaults.get("roles_path", "")
    if not roles_path.startswith("./roles"):
        errors.append("control/ansible: ansible.cfg roles_path must start with ./roles")

    return errors


def check_parity(dist_root: Path, verbose: bool) -> int:
    """Run parity assertions for dist execution roots."""
    errors: list[str] = []

    terraform_pairs = [
        ("control/terraform/mikrotik", REPO_ROOT / "generated" / "terraform" / "mikrotik"),
        ("control/terraform/proxmox", REPO_ROOT / "generated" / "terraform" / "proxmox"),
    ]
    for package_id, native_root in terraform_pairs:
        package_root = dist_root / package_id
        errors.extend(
            compare_file_sets(
                label=package_id,
                native_root=native_root,
                dist_root=package_root,
                ignored_dist={"manifest.json"},
            )
        )

    ansible_package_root = dist_root / "control" / "ansible"
    errors.extend(
        compare_file_sets(
            label="control/ansible playbooks+roles",
            native_root=REPO_ROOT / "ansible" / "playbooks",
            dist_root=ansible_package_root / "playbooks",
        )
    )
    errors.extend(
        compare_file_sets(
            label="control/ansible roles",
            native_root=REPO_ROOT / "ansible" / "roles",
            dist_root=ansible_package_root / "roles",
            ignored_native={"proxmox/README.md"},
        )
    )
    errors.extend(
        compare_file_sets(
            label="control/ansible runtime inventory",
            native_root=REPO_ROOT / "generated" / "ansible" / "runtime" / "production",
            dist_root=ansible_package_root / "inventory",
        )
    )

    requirements_native = REPO_ROOT / "ansible" / "requirements.yml"
    requirements_dist = ansible_package_root / "requirements.yml"
    if sha256(requirements_native) != sha256(requirements_dist):
        errors.append("control/ansible: requirements.yml differs from native source")

    vault_example_native = REPO_ROOT / "ansible" / "group_vars" / "all" / "vault.yml.example"
    vault_example_dist = ansible_package_root / "group_vars" / "all" / "vault.yml.example"
    if sha256(vault_example_native) != sha256(vault_example_dist):
        errors.append("control/ansible: vault.yml.example differs from native source")

    errors.extend(check_ansible_cfg(ansible_package_root))

    if errors:
        print("ERROR native/dist parity check failed:")
        for error in errors:
            print(f"  - {error}")
        return 1

    if verbose:
        print("OK deploy execution parity passed")
        print(f"  dist root: {dist_root}")

    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Check native versus dist deploy parity")
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
        help="Suppress success output",
    )
    args = parser.parse_args()

    sys.exit(check_parity(dist_root=args.dist, verbose=not args.quiet))


if __name__ == "__main__":
    main()
