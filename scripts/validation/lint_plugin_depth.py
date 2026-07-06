#!/usr/bin/env python3
"""Lint plugin dependency graph for maximum depth violations.

This script validates that plugin dependency chains don't exceed thresholds.
Deep dependency chains can indicate architectural issues and affect performance.

Usage:
    python scripts/validation/lint_plugin_depth.py [--max-depth 6] [--warn-depth 5]

Exit codes:
    0 - No depth violations
    1 - Depth exceeds max threshold
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

import yaml

DEFAULT_MAX_DEPTH = 6
DEFAULT_WARN_DEPTH = 5


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


def build_dependency_graph(manifests: list[Path]) -> dict[str, set[str]]:
    """Build plugin dependency graph from manifests.

    Returns:
        Dictionary mapping plugin_id to set of dependency plugin_ids.
    """
    graph: dict[str, set[str]] = {}

    for manifest_path in manifests:
        manifest = _load_yaml(manifest_path)
        for plugin in manifest.get("plugins", []):
            plugin_id = plugin.get("id")
            if not plugin_id:
                continue
            deps = set(plugin.get("depends_on", []))
            graph[plugin_id] = deps

    return graph


def calculate_depths(graph: dict[str, set[str]]) -> dict[str, int]:
    """Calculate max depth from each node to a leaf.

    Depth = longest path from the plugin to a plugin with no dependencies.

    Returns:
        Dictionary mapping plugin_id to its depth.
    """
    depths: dict[str, int] = {}
    computing: set[str] = set()

    def get_depth(node: str) -> int:
        if node in depths:
            return depths[node]
        if node in computing:
            # Cycle detected - handled by cycle checker
            return 0
        if node not in graph:
            # External reference
            return 0

        computing.add(node)
        deps = graph.get(node, set())

        if not deps:
            depth = 0
        else:
            valid_deps = [d for d in deps if d in graph]
            if valid_deps:
                depth = 1 + max(get_depth(d) for d in valid_deps)
            else:
                depth = 0

        computing.remove(node)
        depths[node] = depth
        return depth

    for node in graph:
        get_depth(node)

    return depths


def lint_depths(
    depths: dict[str, int],
    max_depth: int = DEFAULT_MAX_DEPTH,
    warn_depth: int = DEFAULT_WARN_DEPTH,
) -> tuple[list[str], list[str]]:
    """Check depths against thresholds.

    Returns:
        Tuple of (errors, warnings).
    """
    warnings: list[str] = []
    errors: list[str] = []

    for plugin_id, depth in sorted(depths.items(), key=lambda x: (-x[1], x[0])):
        if depth > max_depth:
            errors.append(f"Plugin '{plugin_id}' depth {depth} exceeds max {max_depth}")
        elif depth >= warn_depth:
            warnings.append(f"Plugin '{plugin_id}' depth {depth} approaching limit (warn >= {warn_depth})")

    return errors, warnings


def get_dependency_chain(
    graph: dict[str, set[str]],
    plugin_id: str,
    max_length: int = 10,
) -> list[str]:
    """Get the longest dependency chain for a plugin.

    Returns:
        List of plugin IDs forming the longest chain.
    """

    def find_longest_path(node: str, visited: set[str]) -> list[str]:
        if node in visited or node not in graph:
            return []
        if len(visited) >= max_length:
            return []

        visited.add(node)
        deps = [d for d in graph.get(node, set()) if d in graph]

        if not deps:
            visited.remove(node)
            return [node]

        longest: list[str] = []
        for dep in deps:
            path = find_longest_path(dep, visited)
            if len(path) > len(longest):
                longest = path

        visited.remove(node)
        return [node] + longest

    return find_longest_path(plugin_id, set())


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Lint plugin dependency graph for depth violations.")
    parser.add_argument(
        "--max-depth",
        type=int,
        default=DEFAULT_MAX_DEPTH,
        help=f"Maximum allowed dependency depth (default: {DEFAULT_MAX_DEPTH})",
    )
    parser.add_argument(
        "--warn-depth",
        type=int,
        default=DEFAULT_WARN_DEPTH,
        help=f"Depth threshold for warnings (default: {DEFAULT_WARN_DEPTH})",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Show detailed output including top-depth plugins.",
    )
    parser.add_argument(
        "--show-chains",
        action="store_true",
        help="Show full dependency chains for violations.",
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        help="Write depth report as JSON to specified file.",
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

    graph = build_dependency_graph(manifests)
    print(f"Built dependency graph with {len(graph)} plugins")

    depths = calculate_depths(graph)
    errors, warnings = lint_depths(
        depths,
        max_depth=args.max_depth,
        warn_depth=args.warn_depth,
    )

    # Verbose output: show top-N deepest plugins
    if args.verbose:
        print("\n=== Dependency Depth Report ===")
        top_plugins = sorted(depths.items(), key=lambda x: (-x[1], x[0]))[:15]
        for plugin_id, depth in top_plugins:
            marker = ""
            if depth > args.max_depth:
                marker = " [ERROR]"
            elif depth >= args.warn_depth:
                marker = " [WARN]"
            print(f"  depth={depth}: {plugin_id}{marker}")

    # Show dependency chains for violations
    if args.show_chains and (errors or warnings):
        print("\n=== Dependency Chains ===")
        for msg in errors + warnings:
            plugin_id = msg.split("'")[1]
            chain = get_dependency_chain(graph, plugin_id)
            print(f"  {plugin_id}: {' -> '.join(chain)}")

    # JSON output
    if args.output_json:
        import json

        report = {
            "total_plugins": len(graph),
            "max_depth_threshold": args.max_depth,
            "warn_depth_threshold": args.warn_depth,
            "max_actual_depth": max(depths.values()) if depths else 0,
            "plugins_over_max": len(errors),
            "plugins_at_warn": len(warnings),
            "depths": {k: v for k, v in sorted(depths.items(), key=lambda x: (-x[1], x[0]))},
        }
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(json.dumps(report, indent=2))
        print(f"Report written to {args.output_json}")

    # Summary
    max_actual = max(depths.values()) if depths else 0
    print(f"\nMax dependency depth: {max_actual} (threshold: {args.max_depth})")

    if errors:
        print(f"\nERRORS: {len(errors)} plugins exceed max depth")
        for error in errors:
            print(f"  - {error}")
        return 1

    if warnings:
        print(f"\nWARNINGS: {len(warnings)} plugins approaching depth limit")
        for warning in warnings:
            print(f"  - {warning}")

    print("OK: No depth violations")
    return 0


if __name__ == "__main__":
    sys.exit(main())
