#!/usr/bin/env python3
"""Validate that a dist package is ready for execution and has required local inputs."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
DEFAULT_DIST = REPO_ROOT / "dist"


def load_json(path: Path) -> dict:
    """Load a JSON document from disk."""
    return json.loads(path.read_text())


def resolve_required_input(dist_root: Path, package_id: str, package_root: Path, raw_path: str) -> Path:
    """Resolve a required input path from package metadata."""
    input_path = Path(raw_path)
    package_prefix = Path(package_id)

    try:
        if input_path.parts[: len(package_prefix.parts)] == package_prefix.parts:
            return dist_root / input_path
    except IndexError:
        pass

    return package_root / input_path


def check_package(dist_root: Path, package_id: str, verbose: bool) -> int:
    """Return a process exit code after validating dist package readiness."""
    packages_manifest = dist_root / "manifests" / "packages.json"
    if not packages_manifest.exists():
        print(f"ERROR missing dist manifest: {packages_manifest}")
        return 1

    packages = load_json(packages_manifest).get("packages", {})
    manifest = packages.get(package_id)
    if manifest is None:
        print(f"ERROR package '{package_id}' is not declared in {packages_manifest}")
        return 1

    package_root = dist_root / Path(package_id)
    package_manifest = package_root / "manifest.json"

    errors: list[str] = []
    if not package_root.exists():
        errors.append(f"package directory is missing: {package_root}")
    if not package_manifest.exists():
        errors.append(f"package manifest is missing: {package_manifest}")

    if manifest.get("status") != "ready":
        errors.append(f"package status is '{manifest.get('status')}', expected 'ready'")

    missing_inputs: list[tuple[str, Path]] = []
    for raw_path in manifest.get("required_local_inputs", []):
        resolved_path = resolve_required_input(dist_root, package_id, package_root, raw_path)
        if not resolved_path.exists():
            missing_inputs.append((raw_path, resolved_path))

    if missing_inputs:
        errors.append("required local inputs are missing")

    if errors:
        print(f"ERROR dist package '{package_id}' is not ready for execution")
        for error in errors:
            print(f"  - {error}")
        for raw_path, resolved_path in missing_inputs:
            print(f"  - missing input '{raw_path}' at {resolved_path}")
        return 1

    if verbose:
        print(f"OK dist package '{package_id}' is ready")
        print(f"  root: {package_root}")
        for raw_path in manifest.get("required_local_inputs", []):
            resolved_path = resolve_required_input(dist_root, package_id, package_root, raw_path)
            print(f"  input: {raw_path} -> {resolved_path}")

    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Check a dist package before execution")
    parser.add_argument("package_id", help="Package id, for example control/terraform/proxmox")
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

    sys.exit(check_package(dist_root=args.dist, package_id=args.package_id, verbose=not args.quiet))


if __name__ == "__main__":
    main()
