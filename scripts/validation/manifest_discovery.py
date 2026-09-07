#!/usr/bin/env python3
"""Shared manifest discovery utilities for validation scripts.

F06 fix: Provides a single implementation of manifest discovery with:
- Proper visited set during recursion to prevent infinite loops
- Warning on missing includes (fail-open but logged)
- Consistent discovery logic across all validation scripts
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import yaml


def load_yaml(path: Path) -> dict[str, Any]:
    """Load YAML file safely."""
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def resolve_includes(
    manifest_path: Path,
    *,
    visited: set[Path] | None = None,
    warnings: list[str] | None = None,
) -> list[Path]:
    """Resolve includes from a manifest file recursively.

    F06 fix:
    - Uses visited set during recursion to prevent infinite loops
    - Logs warning for missing includes (fail-open but visible)

    Args:
        manifest_path: Path to manifest file to process.
        visited: Set of already-visited paths (for cycle detection).
        warnings: Optional list to collect warning messages.

    Returns:
        List of resolved include paths (may contain duplicates if called
        multiple times on overlapping trees - caller should deduplicate).
    """
    if visited is None:
        visited = set()
    if warnings is None:
        warnings = []

    result: list[Path] = []
    resolved_path = manifest_path.resolve()

    # F06: Cycle detection via visited set
    if resolved_path in visited:
        return result
    visited.add(resolved_path)

    if not manifest_path.exists():
        return result

    manifest_data = load_yaml(manifest_path)
    includes = manifest_data.get("includes", [])
    if not isinstance(includes, list):
        return result

    manifest_dir = manifest_path.parent
    for include in includes:
        if not isinstance(include, str):
            continue
        include_path = (manifest_dir / include).resolve()
        if include_path.exists():
            result.append(include_path)
            # Recursively resolve nested includes with same visited set
            result.extend(resolve_includes(include_path, visited=visited, warnings=warnings))
        else:
            # F06: Warn about missing includes instead of silently ignoring
            warnings.append(f"Missing include: {include_path} (from {manifest_path})")

    return result


def discover_manifests(
    repo_root: Path,
    *,
    include_projects: bool = True,
    warnings: list[str] | None = None,
) -> list[Path]:
    """Discover all plugin manifest files in deterministic order.

    F06 fix:
    - Single implementation used by all validation scripts
    - Processes includes consistently for all manifests
    - Proper cycle detection via visited set

    Args:
        repo_root: Repository root path.
        include_projects: Whether to include project-level manifests.
        warnings: Optional list to collect warning messages.

    Returns:
        Deduplicated list of manifest paths in deterministic order.
    """
    if warnings is None:
        warnings = []

    manifests: list[Path] = []
    visited: set[Path] = set()

    # Root framework manifest and its includes
    root_manifest = repo_root / "topology-tools" / "plugins" / "plugins.yaml"
    if root_manifest.exists():
        manifests.append(root_manifest)
        manifests.extend(resolve_includes(root_manifest, visited=visited, warnings=warnings))

    # Class modules
    class_modules_root = repo_root / "topology" / "class-modules"
    for manifest in sorted(class_modules_root.rglob("plugins.yaml")):
        manifests.append(manifest)
        # F06: Also resolve includes for class module manifests
        manifests.extend(resolve_includes(manifest, visited=visited, warnings=warnings))

    # Object modules
    object_modules_root = repo_root / "topology" / "object-modules"
    for manifest in sorted(object_modules_root.rglob("plugins.yaml")):
        manifests.append(manifest)
        # F06: Also resolve includes for object module manifests
        manifests.extend(resolve_includes(manifest, visited=visited, warnings=warnings))

    # Project manifests (optional)
    if include_projects:
        projects_root = repo_root / "projects"
        if projects_root.exists():
            for project_dir in sorted(projects_root.iterdir()):
                if project_dir.is_dir():
                    for manifest in sorted(project_dir.rglob("plugins.yaml")):
                        manifests.append(manifest)
                        # F06: Also resolve includes for project manifests
                        manifests.extend(resolve_includes(manifest, visited=visited, warnings=warnings))

    # Deduplicate while preserving order
    seen: set[Path] = set()
    result: list[Path] = []
    for m in manifests:
        resolved = m.resolve()
        if resolved.exists() and resolved not in seen:
            seen.add(resolved)
            result.append(m)

    return result


def main() -> int:
    """CLI for testing manifest discovery."""
    from argparse import ArgumentParser

    parser = ArgumentParser(description="Discover plugin manifests")
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--no-projects", action="store_true", help="Exclude project manifests")
    parser.add_argument("--show-warnings", action="store_true", help="Show missing include warnings")
    args = parser.parse_args()

    warnings: list[str] = []
    manifests = discover_manifests(
        args.repo_root,
        include_projects=not args.no_projects,
        warnings=warnings,
    )

    print(f"Discovered {len(manifests)} manifest files:")
    for m in manifests:
        print(f"  - {m.relative_to(args.repo_root)}")

    if args.show_warnings and warnings:
        print(f"\nWarnings ({len(warnings)}):")
        for w in warnings:
            print(f"  - {w}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
