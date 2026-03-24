#!/usr/bin/env python3
"""Assemble deploy-oriented dist packages from canonical source and generated roots."""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

from utils.package_manifest import PackageManifest, write_json_manifest, write_package_manifest
from utils.package_policy import LOCAL_SECRET_PATH_PATTERNS, is_local_secret_path, validate_release_safe_tree
from utils.terraform_overrides import apply_overrides, override_source_roots

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ENV = "production"
DEFAULT_DIST = REPO_ROOT / "v4-dist"

ANSIBLE_SOURCE = REPO_ROOT / "v4" / "ansible"
ANSIBLE_RUNTIME = REPO_ROOT / "v4-generated" / "ansible" / "runtime" / DEFAULT_ENV
TERRAFORM_ROOT = REPO_ROOT / "v4-generated" / "terraform"
TERRAFORM_PACKAGES = {
    "control/terraform/mikrotik": TERRAFORM_ROOT / "mikrotik",
    "control/terraform/proxmox": TERRAFORM_ROOT / "proxmox",
}
BOOTSTRAP_ROOT = REPO_ROOT / "v4-generated" / "bootstrap"
BOOTSTRAP_PACKAGES = {
    "bootstrap/rtr-mikrotik-chateau": {
        "source_dir": BOOTSTRAP_ROOT / "rtr-mikrotik-chateau",
        "package_class": "release-safe",
        "required_local_inputs": [],
        "validation_commands": [],
    },
    "bootstrap/srv-gamayun": {
        "source_dir": BOOTSTRAP_ROOT / "srv-gamayun",
        "package_class": "local-input-required",
        "required_local_inputs": [
            "bootstrap/srv-gamayun/answer.toml",
        ],
        "validation_commands": [],
    },
    "bootstrap/srv-orangepi5": {
        "source_dir": BOOTSTRAP_ROOT / "srv-orangepi5",
        "package_class": "local-input-required",
        "required_local_inputs": [
            "bootstrap/srv-orangepi5/cloud-init/user-data",
        ],
        "validation_commands": [],
    },
}
ANSIBLE_PACKAGE_ID = "control/ansible"


def relpath(path: Path, base: Path) -> str:
    """Return POSIX-style relative path."""
    return path.relative_to(base).as_posix()


def ensure_clean_dir(path: Path) -> None:
    """Remove and recreate a directory."""
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def copy_tree_filtered(
    src: Path,
    dst: Path,
    repo_root: Path,
    excluded_names: set[str] | None = None,
) -> tuple[list[str], list[str]]:
    """Copy a directory tree while excluding local-secret and transient paths."""
    included: list[str] = []
    excluded: list[str] = []
    excluded_names = excluded_names or set()

    if not src.exists():
        raise FileNotFoundError(f"Source directory not found: {src}")

    for path in sorted(src.rglob("*")):
        rel = path.relative_to(src)
        if not rel.parts:
            continue

        if any(part == "__pycache__" for part in rel.parts):
            excluded.append(relpath(path, repo_root))
            continue

        if path.name in excluded_names:
            excluded.append(relpath(path, repo_root))
            continue

        if is_local_secret_path(rel) or is_local_secret_path(path):
            excluded.append(relpath(path, repo_root))
            continue

        target = dst / rel
        if path.is_dir():
            target.mkdir(parents=True, exist_ok=True)
            continue

        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
        included.append(relpath(path, repo_root))

    return included, excluded


def has_non_directory_content(path: Path) -> bool:
    """Return True when a directory contains at least one file."""
    if not path.exists() or not path.is_dir():
        return False

    return any(item.is_file() for item in path.rglob("*"))


def build_ansible_cfg(source_cfg: Path, output_cfg: Path) -> None:
    """Write a package-local ansible.cfg that points to ./inventory."""
    lines = source_cfg.read_text().splitlines()
    rendered: list[str] = []
    replaced = False

    for line in lines:
        if line.strip().startswith("inventory = "):
            rendered.append("inventory = ./inventory")
            replaced = True
            continue
        rendered.append(line)

    if not replaced:
        raise ValueError(f"Could not rewrite inventory path in {source_cfg}")

    output_cfg.write_text("\n".join(rendered) + "\n")


def assemble_ansible_package(dist_root: Path) -> PackageManifest:
    """Assemble dist/control/ansible from ansible/ and assembled runtime inventory."""
    package_dir = dist_root / "control" / "ansible"
    package_dir.mkdir(parents=True, exist_ok=True)

    included_paths: list[str] = []
    excluded_paths: list[str] = []
    excluded_names = {"README.md"}

    for directory_name in ["playbooks", "roles"]:
        source_dir = ANSIBLE_SOURCE / directory_name
        if source_dir.exists():
            included, excluded = copy_tree_filtered(
                source_dir,
                package_dir / directory_name,
                REPO_ROOT,
                excluded_names=excluded_names,
            )
            included_paths.extend(included)
            excluded_paths.extend(excluded)

    vault_example = ANSIBLE_SOURCE / "group_vars" / "all" / "vault.yml.example"
    if vault_example.exists():
        target = package_dir / "group_vars" / "all" / "vault.yml.example"
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(vault_example, target)
        included_paths.append(relpath(vault_example, REPO_ROOT))

    legacy_vars = ANSIBLE_SOURCE / "group_vars" / "all" / "vars.yml"
    if legacy_vars.exists():
        excluded_paths.append(relpath(legacy_vars, REPO_ROOT))

    requirements_file = ANSIBLE_SOURCE / "requirements.yml"
    if requirements_file.exists():
        shutil.copy2(requirements_file, package_dir / "requirements.yml")
        included_paths.append(relpath(requirements_file, REPO_ROOT))

    ansible_cfg = ANSIBLE_SOURCE / "ansible.cfg"
    build_ansible_cfg(ansible_cfg, package_dir / "ansible.cfg")
    included_paths.append(relpath(ansible_cfg, REPO_ROOT))

    runtime_inventory = ANSIBLE_RUNTIME
    if not runtime_inventory.exists():
        raise FileNotFoundError(f"Assembled runtime inventory not found: {runtime_inventory}")

    included, excluded = copy_tree_filtered(runtime_inventory, package_dir / "inventory", REPO_ROOT)
    included_paths.extend(included)
    excluded_paths.extend(excluded)

    manifest = PackageManifest(
        package_id=ANSIBLE_PACKAGE_ID,
        package_class="local-input-required",
        source_roots=[
            relpath(ANSIBLE_SOURCE, REPO_ROOT),
            relpath(ANSIBLE_RUNTIME, REPO_ROOT),
        ],
        assembled_from_runtime_contract="ADR 0051",
        included_paths=sorted(included_paths),
        excluded_paths=sorted(set(excluded_paths)),
        required_local_inputs=[
            ".vault_pass",
            "group_vars/all/vault.yml",
        ],
        validation_commands=[
            "ansible-inventory -i inventory --list",
            "ansible-playbook --syntax-check playbooks/common.yml",
            "ansible-playbook --syntax-check playbooks/postgresql.yml",
            "ansible-playbook --syntax-check playbooks/redis.yml",
        ],
    )
    write_package_manifest(package_dir / "manifest.json", manifest)
    return manifest


def assemble_terraform_package(package_id: str, source_dir: Path, dist_root: Path) -> PackageManifest:
    """Assemble a Terraform package from a generated Terraform root."""
    if not source_dir.exists():
        raise FileNotFoundError(f"Terraform package source not found: {source_dir}")

    package_dir = dist_root / Path(package_id)
    package_dir.mkdir(parents=True, exist_ok=True)
    included_paths, excluded_paths = copy_tree_filtered(source_dir, package_dir, REPO_ROOT)
    target = package_id.split("/")[-1]
    override_report = apply_overrides(target, package_dir)
    if override_report.errors:
        raise ValueError("; ".join(override_report.errors))

    override_roots = override_source_roots(target)
    for source, _destination in override_report.copied:
        included_paths.append(relpath(source, REPO_ROOT))

    manifest = PackageManifest(
        package_id=package_id,
        package_class="local-input-required",
        source_roots=[relpath(source_dir, REPO_ROOT), *override_roots],
        included_paths=sorted(included_paths),
        excluded_paths=sorted(set(excluded_paths)),
        required_local_inputs=[
            f"{package_id}/terraform.tfvars",
        ],
        validation_commands=[
            "terraform init -backend=false",
            "terraform validate",
        ],
    )
    write_package_manifest(package_dir / "manifest.json", manifest)
    return manifest


def assemble_bootstrap_package(package_id: str, package_config: dict, dist_root: Path) -> PackageManifest:
    """Assemble an explicit bootstrap package or mark it skipped."""
    source_dir = package_config["source_dir"]
    package_class = package_config["package_class"]
    required_local_inputs = package_config.get("required_local_inputs", [])
    validation_commands = package_config.get("validation_commands", [])

    package_dir = dist_root / Path(package_id)
    package_dir.mkdir(parents=True, exist_ok=True)

    if not has_non_directory_content(source_dir):
        manifest = PackageManifest(
            package_id=package_id,
            package_class=package_class,
            source_roots=[relpath(source_dir, REPO_ROOT)],
            status="skipped",
            excluded_paths=[relpath(source_dir, REPO_ROOT)],
        )
        write_package_manifest(package_dir / "manifest.json", manifest)
        return manifest

    included_paths, excluded_paths = copy_tree_filtered(source_dir, package_dir, REPO_ROOT)
    manifest = PackageManifest(
        package_id=package_id,
        package_class=package_class,
        source_roots=[relpath(source_dir, REPO_ROOT)],
        included_paths=sorted(included_paths),
        excluded_paths=sorted(set(excluded_paths)),
        required_local_inputs=required_local_inputs,
        validation_commands=validation_commands,
    )
    write_package_manifest(package_dir / "manifest.json", manifest)
    return manifest


def write_top_level_manifests(dist_root: Path, manifests: list[PackageManifest]) -> None:
    """Write aggregate manifests under dist/manifests."""
    manifests_dir = dist_root / "manifests"
    manifests_dir.mkdir(parents=True, exist_ok=True)

    package_map = {manifest.package_id: manifest.to_dict() for manifest in manifests}
    publishable_packages = sorted(
        manifest.package_id
        for manifest in manifests
        if manifest.status == "ready" and manifest.package_class == "release-safe"
    )
    non_publishable_packages = sorted(
        manifest.package_id
        for manifest in manifests
        if manifest.status != "ready" or manifest.package_class != "release-safe"
    )
    skipped_packages = sorted(manifest.package_id for manifest in manifests if manifest.status == "skipped")
    local_inputs = {
        manifest.package_id: manifest.required_local_inputs
        for manifest in manifests
        if manifest.status == "ready" and manifest.required_local_inputs
    }
    source_roots = {manifest.package_id: manifest.source_roots for manifest in manifests}

    write_json_manifest(
        manifests_dir / "sources.json",
        {
            "schema_version": "1",
            "packages": source_roots,
        },
    )
    write_json_manifest(
        manifests_dir / "release-safe.json",
        {
            "schema_version": "1",
            "publishable_packages": publishable_packages,
            "non_publishable_packages": non_publishable_packages,
            "skipped_packages": skipped_packages,
            "excluded_local_secret_patterns": LOCAL_SECRET_PATH_PATTERNS,
        },
    )
    write_json_manifest(
        manifests_dir / "local-inputs.json",
        {
            "schema_version": "1",
            "packages": local_inputs,
        },
    )
    write_json_manifest(
        manifests_dir / "packages.json",
        {
            "schema_version": "1",
            "packages": package_map,
        },
    )


def assemble_dist(dist_root: Path = DEFAULT_DIST, verbose: bool = True) -> bool:
    """Assemble deploy-ready dist packages."""
    ensure_clean_dir(dist_root)
    manifests: list[PackageManifest] = []

    try:
        manifests.append(assemble_ansible_package(dist_root))
        for package_id, source_dir in TERRAFORM_PACKAGES.items():
            manifests.append(assemble_terraform_package(package_id, source_dir, dist_root))
        for package_id, package_config in BOOTSTRAP_PACKAGES.items():
            manifests.append(assemble_bootstrap_package(package_id, package_config, dist_root))
        write_top_level_manifests(dist_root, manifests)
        violations = validate_release_safe_tree(dist_root)
        if violations:
            print("ERROR Release-safe validation failed:")
            for violation in violations:
                print(f"  - {violation}")
            return False
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR Failed to assemble dist: {exc}")
        return False

    if verbose:
        print("=" * 70)
        print("Deploy Package Assembler (ADR 0052)")
        print("=" * 70)
        print(f"Output: {dist_root}")
        print()
        for manifest in manifests:
            marker = "SKIP" if manifest.status == "skipped" else "OK  "
            print(f"{marker}  {manifest.package_id} [{manifest.package_class}]")
        print()
        print("Manifest schema version: 1")
        print()
        print("Top-level manifests:")
        print(f"  - {dist_root / 'manifests' / 'packages.json'}")
        print(f"  - {dist_root / 'manifests' / 'sources.json'}")
        print(f"  - {dist_root / 'manifests' / 'release-safe.json'}")
        print(f"  - {dist_root / 'manifests' / 'local-inputs.json'}")
        print("=" * 70)

    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="Assemble deploy-ready dist packages (ADR 0052)")
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_DIST,
        help="Path for dist output",
    )
    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="Suppress verbose output",
    )
    args = parser.parse_args()

    success = assemble_dist(dist_root=args.output, verbose=not args.quiet)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
