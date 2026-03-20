#!/usr/bin/env python3
"""
Assemble Ansible runtime inventory from generated and manual sources.

Part of ADR 0051: Ansible Runtime, Inventory, and Secret Boundaries

This assembler creates the effective runtime inventory used by Ansible operators:
- Copies generated hosts.yml unchanged
- Creates layered group_vars (10-generated.yml, 90-manual.yml)
- Copies host_vars with conflict detection
- Validates no secrets in committed files

Usage:
    python3 v5/topology-tools/assemble-ansible-runtime.py

Output:
    v5-generated/ansible/runtime/production/
"""

from __future__ import annotations

import argparse
import re
import shutil
import sys
from pathlib import Path
from typing import NamedTuple
import yaml

# Paths relative to repository root
REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ENV = "production"
DEFAULT_TOPOLOGY = REPO_ROOT / "v5" / "topology" / "topology.yaml"


def _load_active_project(topology_path: Path) -> str:
    if not topology_path.exists():
        return "home-lab"
    try:
        payload = yaml.safe_load(topology_path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError:
        return "home-lab"
    if not isinstance(payload, dict):
        return "home-lab"
    project = payload.get("project")
    if not isinstance(project, dict):
        return "home-lab"
    active = project.get("active")
    if isinstance(active, str) and active.strip():
        return active.strip()
    return "home-lab"


DEFAULT_PROJECT = _load_active_project(DEFAULT_TOPOLOGY)

# Input/output defaults
GENERATED_INV = REPO_ROOT / "v5-generated" / DEFAULT_PROJECT / "ansible" / "inventory" / DEFAULT_ENV
MANUAL_OVERRIDES = REPO_ROOT / "v5" / "projects" / DEFAULT_PROJECT / "ansible" / "inventory-overrides" / DEFAULT_ENV
RUNTIME_INV = REPO_ROOT / "v5-generated" / DEFAULT_PROJECT / "ansible" / "runtime" / DEFAULT_ENV


class ValidationError(NamedTuple):
    """Validation error with file path and message."""

    path: Path
    message: str


# Secret patterns that should not appear in committed inventory files
SECRET_PATTERNS = [
    re.compile(r"password\s*[:=]\s*['\"](?!<TODO_|example|changeme)[^'\"]+['\"]", re.I),
    re.compile(r"api_key\s*[:=]\s*['\"](?!<TODO_|example|changeme)[^'\"]+['\"]", re.I),
    re.compile(r"api_token\s*[:=]\s*['\"](?!<TODO_|example|changeme)[^'\"]+['\"]", re.I),
    re.compile(r"secret\s*[:=]\s*['\"](?!<TODO_|example|changeme)[^'\"]+['\"]", re.I),
    re.compile(r"private_key\s*[:=]\s*['\"](?!<TODO_|example|changeme)[^'\"]+['\"]", re.I),
    re.compile(r"authkey\s*[:=]\s*['\"](?!<TODO_|example|changeme)[^'\"]+['\"]", re.I),
]

# Forbidden override fields (topology-derived, should not be overridden manually)
FORBIDDEN_OVERRIDE_FIELDS = [
    "ansible_host",
    "instance_id",
    "object_ref",
    "class_ref",
]


def validate_no_secret_content(file_path: Path) -> list[ValidationError]:
    """Check file for potential secret values."""
    errors: list[ValidationError] = []
    if not file_path.exists():
        return errors

    content = file_path.read_text(encoding="utf-8")
    for pattern in SECRET_PATTERNS:
        if pattern.search(content):
            errors.append(
                ValidationError(
                    path=file_path,
                    message=f"Potential secret detected matching pattern: {pattern.pattern}",
                )
            )
    return errors


def validate_no_forbidden_overrides(
    file_path: Path, allowlist: list[str]
) -> list[ValidationError]:
    """Check that manual overrides don't override topology-derived fields."""
    errors: list[ValidationError] = []
    if not file_path.exists():
        return errors

    if file_path.name in allowlist:
        return errors

    content = file_path.read_text(encoding="utf-8")
    for field in FORBIDDEN_OVERRIDE_FIELDS:
        pattern = re.compile(rf"^\s*{field}\s*:", re.MULTILINE)
        if pattern.search(content):
            errors.append(
                ValidationError(
                    path=file_path,
                    message=f"Forbidden override of topology-derived field: {field}",
                )
            )
    return errors


def assemble_runtime_inventory(
    generated_dir: Path = GENERATED_INV,
    manual_dir: Path = MANUAL_OVERRIDES,
    runtime_dir: Path = RUNTIME_INV,
    allowlist: list[str] | None = None,
    verbose: bool = True,
) -> tuple[bool, list[ValidationError]]:
    """
    Assemble runtime inventory from generated and manual sources.

    Returns (success: bool, errors: list[ValidationError]).
    """
    allowlist = allowlist or []
    errors: list[ValidationError] = []

    if verbose:
        print("=" * 70)
        print("Ansible Runtime Inventory Assembler (v5 - ADR 0051)")
        print("=" * 70)
        print()

    # Validate generated inventory exists
    if not generated_dir.exists():
        print(f"ERROR Generated inventory not found: {generated_dir}")
        print("       Run compile-topology.py first to generate inventory.")
        return False, errors

    if verbose:
        print(f"  Generated source: {generated_dir}")
        print(f"  Manual overrides: {manual_dir}")
        print(f"  Runtime output:   {runtime_dir}")
        print()

    # Clean and create output directory
    if runtime_dir.exists():
        shutil.rmtree(runtime_dir)
        if verbose:
            print("CLEAN Removed existing runtime directory")

    runtime_dir.mkdir(parents=True)
    if verbose:
        print(f"DIR   Created runtime directory: {runtime_dir}")

    # 1. Copy generated hosts.yml unchanged
    generated_hosts = generated_dir / "hosts.yml"
    if not generated_hosts.exists():
        print(f"ERROR Generated hosts.yml not found: {generated_hosts}")
        return False, errors

    shutil.copy(generated_hosts, runtime_dir / "hosts.yml")
    if verbose:
        print("COPY  hosts.yml (generated, unchanged)")

    # 2. Create layered group_vars
    group_vars_dir = runtime_dir / "group_vars" / "all"
    group_vars_dir.mkdir(parents=True)

    # 2a. Generated group_vars becomes 10-generated.yml
    generated_gv = generated_dir / "group_vars" / "all.yml"
    if generated_gv.exists():
        # Validate no secrets in generated
        errors.extend(validate_no_secret_content(generated_gv))
        shutil.copy(generated_gv, group_vars_dir / "10-generated.yml")
        if verbose:
            print("COPY  group_vars/all/10-generated.yml (from generated)")

    # 2b. Manual group_vars becomes 90-manual.yml (if exists)
    if manual_dir.exists():
        manual_gv = manual_dir / "group_vars" / "all.yml"
        if manual_gv.exists():
            errors.extend(validate_no_secret_content(manual_gv))
            shutil.copy(manual_gv, group_vars_dir / "90-manual.yml")
            if verbose:
                print("COPY  group_vars/all/90-manual.yml (from manual overrides)")
        elif verbose:
            print("SKIP  No manual group_vars/all.yml found")
    elif verbose:
        print(f"SKIP  Manual overrides directory not found: {manual_dir}")

    # 3. Copy host_vars
    host_vars_dir = runtime_dir / "host_vars"
    host_vars_dir.mkdir(parents=True)

    # 3a. Copy generated host_vars first
    generated_hv_dir = generated_dir / "host_vars"
    if generated_hv_dir.exists():
        for hv_file in sorted(generated_hv_dir.glob("*.yml")):
            errors.extend(validate_no_secret_content(hv_file))
            shutil.copy(hv_file, host_vars_dir / hv_file.name)
            if verbose:
                print(f"COPY  host_vars/{hv_file.name} (from generated)")

    # 3b. Copy manual host_vars as overlays (if manual dir exists)
    if manual_dir.exists():
        manual_hv_dir = manual_dir / "host_vars"
        if manual_hv_dir.exists():
            for hv_file in sorted(manual_hv_dir.glob("*.yml")):
                # Skip example files
                if hv_file.name.endswith(".example"):
                    continue

                # Validate no secrets
                errors.extend(validate_no_secret_content(hv_file))

                # Validate no forbidden overrides (unless in allowlist)
                errors.extend(validate_no_forbidden_overrides(hv_file, allowlist))

                # Check for conflicts with generated host_vars
                target_file = host_vars_dir / hv_file.name
                if target_file.exists() and hv_file.name not in allowlist:
                    errors.append(
                        ValidationError(
                            path=hv_file,
                            message=(
                                f"CONFLICT: {hv_file.name} conflicts with generated host_vars. "
                                "Use allowlist to permit override."
                            ),
                        )
                    )
                    continue

                shutil.copy(hv_file, target_file)
                if verbose:
                    print(f"COPY  host_vars/{hv_file.name} (from manual overrides)")

    # Print summary
    if verbose:
        print()
        print("-" * 70)

    if errors:
        print(f"ERRORS: {len(errors)} validation errors found:")
        for err in errors:
            print(f"  {err.path}: {err.message}")
        return False, errors

    if verbose:
        print("SUCCESS Runtime inventory assembled successfully")
        print(f"        Output: {runtime_dir}")

    return True, errors


def main() -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Assemble Ansible runtime inventory (ADR 0051)"
    )
    parser.add_argument(
        "--topology",
        type=Path,
        default=DEFAULT_TOPOLOGY,
        help="Path to v5 topology manifest used for active project detection.",
    )
    parser.add_argument(
        "--project",
        default="",
        help="Project id override (defaults to topology project.active).",
    )
    parser.add_argument(
        "--env",
        default=DEFAULT_ENV,
        help="Inventory environment (default: production).",
    )
    parser.add_argument(
        "--generated-dir",
        type=Path,
        default=None,
        help="Path to generated inventory directory (overrides project/env defaults).",
    )
    parser.add_argument(
        "--manual-dir",
        type=Path,
        default=None,
        help="Path to manual overrides directory (overrides project/env defaults).",
    )
    parser.add_argument(
        "--runtime-dir",
        type=Path,
        default=None,
        help="Path to runtime output directory (overrides project/env defaults).",
    )
    parser.add_argument(
        "--allowlist",
        nargs="*",
        default=[],
        help="Host files allowed to override generated values",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress verbose output",
    )

    args = parser.parse_args()
    env = str(args.env).strip() or DEFAULT_ENV
    project_id = str(args.project).strip() or _load_active_project(args.topology)

    generated_dir = (
        args.generated_dir
        if isinstance(args.generated_dir, Path)
        else REPO_ROOT / "v5-generated" / project_id / "ansible" / "inventory" / env
    )
    manual_dir = (
        args.manual_dir
        if isinstance(args.manual_dir, Path)
        else REPO_ROOT / "v5" / "projects" / project_id / "ansible" / "inventory-overrides" / env
    )
    runtime_dir = (
        args.runtime_dir
        if isinstance(args.runtime_dir, Path)
        else REPO_ROOT / "v5-generated" / project_id / "ansible" / "runtime" / env
    )

    success, _ = assemble_runtime_inventory(
        generated_dir=generated_dir,
        manual_dir=manual_dir,
        runtime_dir=runtime_dir,
        allowlist=args.allowlist,
        verbose=not args.quiet,
    )

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
