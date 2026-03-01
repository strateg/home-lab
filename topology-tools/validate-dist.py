#!/usr/bin/env python3
"""Validate assembled dist packages using package manifests and optional external tools."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

from utils.package_policy import validate_release_safe_tree

REPO_ROOT = Path(__file__).parent.parent
DEFAULT_DIST = REPO_ROOT / "dist"


def load_json(path: Path) -> dict:
    """Load a JSON document from disk."""
    return json.loads(path.read_text())


def required_binary(command: str) -> str:
    """Extract the executable name from a validation command."""
    return command.split()[0]


def run_manifest_commands(
    package_dir: Path,
    package_id: str,
    commands: list[str],
    strict_external: bool,
) -> tuple[list[str], list[str]]:
    """Run package validation commands with graceful missing-tool handling."""
    errors: list[str] = []
    skipped: list[str] = []

    for command in commands:
        binary = required_binary(command)
        if shutil.which(binary) is None:
            message = f"{package_id}: skipped '{command}' because '{binary}' is not installed"
            if strict_external:
                errors.append(message)
            else:
                skipped.append(message)
            continue

        result = subprocess.run(
            command,
            cwd=package_dir,
            shell=True,
            text=True,
            capture_output=True,
            check=False,
        )
        if result.returncode != 0:
            errors.append(f"{package_id}: command failed '{command}'\n" f"{result.stdout}{result.stderr}".strip())

    return errors, skipped


def validate_dist(dist_root: Path, strict_external: bool, verbose: bool) -> bool:
    """Validate dist manifests, release-safe tree, and optional external commands."""
    manifests_dir = dist_root / "manifests"
    packages_manifest_path = manifests_dir / "packages.json"
    release_safe_path = manifests_dir / "release-safe.json"
    local_inputs_path = manifests_dir / "local-inputs.json"
    sources_path = manifests_dir / "sources.json"

    required_files = [
        packages_manifest_path,
        release_safe_path,
        local_inputs_path,
        sources_path,
    ]
    missing_files = [str(path) for path in required_files if not path.exists()]
    if missing_files:
        print("ERROR Dist manifests are incomplete:")
        for path in missing_files:
            print(f"  - missing {path}")
        return False

    violations = validate_release_safe_tree(dist_root)
    if violations:
        print("ERROR Dist tree violates release-safe policy:")
        for violation in violations:
            print(f"  - {violation}")
        return False

    packages_payload = load_json(packages_manifest_path)
    packages = packages_payload.get("packages", {})

    errors: list[str] = []
    skipped: list[str] = []

    for package_id, manifest in sorted(packages.items()):
        package_dir = dist_root / Path(package_id)
        if not package_dir.exists():
            errors.append(f"{package_id}: package directory missing at {package_dir}")
            continue

        package_manifest = package_dir / "manifest.json"
        if not package_manifest.exists():
            errors.append(f"{package_id}: package manifest missing at {package_manifest}")
            continue

        if manifest.get("package_id") != package_id:
            errors.append(f"{package_id}: manifest package_id mismatch")

        command_errors, command_skips = run_manifest_commands(
            package_dir=package_dir,
            package_id=package_id,
            commands=manifest.get("validation_commands", []),
            strict_external=strict_external,
        )
        errors.extend(command_errors)
        skipped.extend(command_skips)

    if verbose:
        print("=" * 70)
        print("Dist Validator (ADR 0052)")
        print("=" * 70)
        print(f"Dist root: {dist_root}")
        print(f"Manifest packages: {len(packages)}")
        if skipped:
            print()
            print("Skipped external validations:")
            for item in skipped:
                print(f"  - {item}")

    if errors:
        print()
        print("ERROR Dist validation failed:")
        for error in errors:
            print(f"  - {error}")
        return False

    if verbose:
        print()
        print("OK    Dist validation passed")
        print("=" * 70)

    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate assembled dist packages (ADR 0052)")
    parser.add_argument(
        "--dist",
        type=Path,
        default=DEFAULT_DIST,
        help="Path to dist root",
    )
    parser.add_argument(
        "--strict-external",
        action="store_true",
        help="Fail when external tools required by validation_commands are not installed",
    )
    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="Suppress summary output",
    )
    args = parser.parse_args()

    success = validate_dist(dist_root=args.dist, strict_external=args.strict_external, verbose=not args.quiet)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
