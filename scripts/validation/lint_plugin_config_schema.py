#!/usr/bin/env python3
"""Lint plugin manifests for required config_schema declarations.

This script validates that all plugins have config_schema declared.
It supports three modes:
  - strict: All plugins must have config_schema (CI enforcement)
  - warn: Missing config_schema triggers warnings only
  - baseline: Check only new plugins against baseline (for incremental adoption)

Usage:
    python scripts/validation/lint_plugin_config_schema.py [--mode strict|warn|baseline]

Exit codes:
    0 - All plugins compliant (or warnings only in warn mode)
    1 - Missing config_schema detected (strict mode)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

import yaml


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _discover_manifests(repo_root: Path) -> list[Path]:
    """Discover all plugin manifest files in deterministic order."""
    manifests = [repo_root / "topology-tools" / "plugins" / "plugins.yaml"]
    manifests.extend(sorted((repo_root / "topology" / "class-modules").rglob("plugins.yaml")))
    manifests.extend(sorted((repo_root / "topology" / "object-modules").rglob("plugins.yaml")))
    # Project manifests
    projects_root = repo_root / "projects"
    if projects_root.exists():
        for project_dir in sorted(projects_root.iterdir()):
            if project_dir.is_dir():
                manifests.extend(sorted(project_dir.rglob("plugins.yaml")))
    return [m for m in manifests if m.exists()]


def _load_yaml(path: Path) -> dict[str, Any]:
    """Load YAML file safely."""
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def _load_baseline(repo_root: Path) -> set[str]:
    """Load baseline plugin IDs from snapshot file (if exists).

    Baseline file format: one plugin ID per line.
    Location: .plugin-baseline.txt (gitignored, generated via --update-baseline)
    """
    baseline_path = repo_root / ".plugin-baseline.txt"
    if not baseline_path.exists():
        return set()
    return {line.strip() for line in baseline_path.read_text().splitlines() if line.strip()}


def _save_baseline(repo_root: Path, plugin_ids: set[str]) -> None:
    """Save current plugin IDs as baseline."""
    baseline_path = repo_root / ".plugin-baseline.txt"
    baseline_path.write_text("\n".join(sorted(plugin_ids)) + "\n")
    print(f"Baseline updated: {baseline_path} ({len(plugin_ids)} plugins)")


def check_config_schema_required(
    manifests: list[Path],
    baseline_ids: set[str] | None = None,
    verbose: bool = False,
) -> tuple[list[str], list[str], set[str]]:
    """Check that all plugins have config_schema declared.

    Args:
        manifests: List of manifest file paths.
        baseline_ids: Optional set of plugin IDs to exclude (grandfathered).
        verbose: Print progress.

    Returns:
        Tuple of (errors, warnings, all_plugin_ids).
    """
    errors: list[str] = []
    warnings: list[str] = []
    all_plugin_ids: set[str] = set()

    for manifest_path in manifests:
        manifest = _load_yaml(manifest_path)
        for plugin in manifest.get("plugins", []):
            plugin_id = plugin.get("id", "<unknown>")
            all_plugin_ids.add(plugin_id)

            has_config_schema = "config_schema" in plugin
            is_grandfathered = baseline_ids is not None and plugin_id in baseline_ids

            if not has_config_schema:
                location = manifest_path.relative_to(_repo_root())
                message = f"Plugin '{plugin_id}' missing config_schema ({location})"

                if is_grandfathered:
                    warnings.append(message)
                    if verbose:
                        print(f"WARN (grandfathered): {message}")
                else:
                    errors.append(message)
                    if verbose:
                        print(f"ERROR: {message}")
            elif verbose:
                print(f"OK: {plugin_id}")

    return errors, warnings, all_plugin_ids


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Lint plugin manifests for required config_schema declarations."
    )
    parser.add_argument(
        "--mode",
        choices=["strict", "warn", "baseline"],
        default="strict",
        help=(
            "Enforcement mode: "
            "'strict' fails on any missing config_schema, "
            "'warn' only prints warnings, "
            "'baseline' only fails for new plugins not in baseline."
        ),
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Print detailed output for each plugin.",
    )
    parser.add_argument(
        "--update-baseline",
        action="store_true",
        help="Update baseline file with current plugin IDs (for --mode baseline).",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    repo_root = _repo_root()

    manifests = _discover_manifests(repo_root)
    if not manifests:
        print("ERROR: No plugin manifests found")
        return 1

    print(f"Scanning {len(manifests)} manifest files...")

    # Load baseline for baseline mode
    baseline_ids: set[str] | None = None
    if args.mode == "baseline":
        baseline_ids = _load_baseline(repo_root)
        if baseline_ids:
            print(f"Loaded baseline: {len(baseline_ids)} grandfathered plugins")
        else:
            print("No baseline found; treating all plugins as new")

    errors, warnings, all_plugin_ids = check_config_schema_required(
        manifests,
        baseline_ids=baseline_ids,
        verbose=args.verbose,
    )

    # Update baseline if requested
    if args.update_baseline:
        _save_baseline(repo_root, all_plugin_ids)
        return 0

    # Summary
    total_plugins = len(all_plugin_ids)
    print(f"\nScanned {total_plugins} plugins across {len(manifests)} manifests")

    if errors:
        print(f"ERRORS: {len(errors)} plugins missing config_schema")
        for error in errors:
            print(f"  - {error}")

    if warnings:
        print(f"WARNINGS: {len(warnings)} grandfathered plugins missing config_schema")
        for warning in warnings:
            print(f"  - {warning}")

    if not errors and not warnings:
        print("OK: All plugins have config_schema declared")

    # Exit code based on mode
    if args.mode == "strict" and errors:
        return 1
    if args.mode == "baseline" and errors:
        return 1
    # warn mode always returns 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
