#!/usr/bin/env python3
"""Validate assembled dist packages using package manifests and optional external tools."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from utils.package_policy import validate_release_safe_tree

REPO_ROOT = Path(__file__).parent.parent
DEFAULT_DIST = REPO_ROOT / "dist"


def load_json(path: Path) -> dict:
    """Load a JSON document from disk."""
    return json.loads(path.read_text())


def validate_package_manifest_contract(package_id: str, manifest: dict) -> list[str]:
    """Validate package-manifest semantics independently of external tools."""
    errors: list[str] = []
    package_class = manifest.get("package_class")
    status = manifest.get("status")
    required_local_inputs = manifest.get("required_local_inputs", [])

    if package_class not in {"release-safe", "local-input-required"}:
        errors.append(f"{package_id}: unsupported package_class '{package_class}'")

    if status not in {"ready", "skipped"}:
        errors.append(f"{package_id}: unsupported status '{status}'")

    if status == "skipped" and required_local_inputs:
        errors.append(f"{package_id}: skipped package must not declare required_local_inputs")

    if package_class == "release-safe" and required_local_inputs:
        errors.append(f"{package_id}: release-safe package must not declare required_local_inputs")

    if status == "ready" and package_class == "local-input-required" and not required_local_inputs:
        errors.append(f"{package_id}: local-input-required package must declare required_local_inputs")

    return errors


def resolve_required_input(dist_root: Path, package_id: str, package_dir: Path, raw_path: str) -> Path:
    """Resolve a required input path from package metadata."""
    input_path = Path(raw_path)
    package_prefix = Path(package_id)

    try:
        if input_path.parts[: len(package_prefix.parts)] == package_prefix.parts:
            return dist_root / input_path
    except IndexError:
        pass

    return package_dir / input_path


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
    terraform_temp_dir = None
    terraform_env = None
    terraform_work_dir = None

    try:
        for command in commands:
            binary = required_binary(command)
            if shutil.which(binary) is None:
                message = f"{package_id}: skipped '{command}' because '{binary}' is not installed"
                if strict_external:
                    errors.append(message)
                else:
                    skipped.append(message)
                continue

            env = None
            run_dir = package_dir
            if binary == "terraform":
                if terraform_temp_dir is None:
                    terraform_temp_dir = tempfile.TemporaryDirectory(prefix="dist-validate-tf-")
                    terraform_env = dict(os.environ)
                    terraform_env["TF_DATA_DIR"] = terraform_temp_dir.name
                    terraform_work_dir = Path(terraform_temp_dir.name) / "package"
                    shutil.copytree(package_dir, terraform_work_dir)
                env = terraform_env
                run_dir = terraform_work_dir
            elif binary.startswith("ansible"):
                env = dict(os.environ)
                ansible_cfg = package_dir / "ansible.cfg"
                if ansible_cfg.exists():
                    env["ANSIBLE_CONFIG"] = str(ansible_cfg)

            result = subprocess.run(
                command,
                cwd=run_dir,
                shell=True,
                text=True,
                capture_output=True,
                check=False,
                env=env,
            )
            if result.returncode != 0:
                errors.append(f"{package_id}: command failed '{command}'\n" f"{result.stdout}{result.stderr}".strip())
    finally:
        if terraform_temp_dir is not None:
            terraform_temp_dir.cleanup()

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
    release_safe_payload = load_json(release_safe_path)
    packages = packages_payload.get("packages", {})
    publishable_packages = set(release_safe_payload.get("publishable_packages", []))
    non_publishable_packages = set(release_safe_payload.get("non_publishable_packages", []))
    skipped_packages = set(release_safe_payload.get("skipped_packages", []))

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

        errors.extend(validate_package_manifest_contract(package_id, manifest))

        package_class = manifest.get("package_class")
        status = manifest.get("status")

        if status == "ready" and package_class == "release-safe" and package_id not in publishable_packages:
            errors.append(f"{package_id}: release-safe package missing from release-safe publishable_packages")
        if status == "ready" and package_class != "release-safe" and package_id in publishable_packages:
            errors.append(f"{package_id}: non-release-safe package must not be publishable")
        if status == "ready" and package_class != "release-safe" and package_id not in non_publishable_packages:
            errors.append(f"{package_id}: non-release-safe package missing from non_publishable_packages")
        if status == "skipped" and package_id in publishable_packages:
            errors.append(f"{package_id}: skipped package must not be publishable")
        if status == "skipped" and package_id not in skipped_packages:
            errors.append(f"{package_id}: skipped package missing from release-safe skipped_packages")
        if status == "skipped" and package_id not in non_publishable_packages:
            errors.append(f"{package_id}: skipped package missing from non_publishable_packages")

        if status == "ready":
            missing_inputs = [
                raw_path
                for raw_path in manifest.get("required_local_inputs", [])
                if not resolve_required_input(dist_root, package_id, package_dir, raw_path).exists()
            ]
            if missing_inputs:
                skipped.append(
                    f"{package_id}: skipped external validation until local inputs exist: {', '.join(missing_inputs)}"
                )
            else:
                command_errors, command_skips = run_manifest_commands(
                    package_dir=package_dir,
                    package_id=package_id,
                    commands=manifest.get("validation_commands", []),
                    strict_external=strict_external,
                )
                errors.extend(command_errors)
                skipped.extend(command_skips)
        else:
            skipped.append(f"{package_id}: skipped package has no assembled payload yet")

    if verbose:
        print("=" * 70)
        print("Dist Validator (ADR 0052)")
        print("=" * 70)
        print(f"Dist root: {dist_root}")
        print(f"Manifest packages: {len(packages)}")
        print(f"Publishable packages: {len(publishable_packages)}")
        print(f"Skipped packages: {len(skipped_packages)}")
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
