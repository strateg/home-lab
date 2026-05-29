#!/usr/bin/env python3
"""Check plugin dependency graph for cycles.

This script validates that the plugin dependency graph is acyclic.
Circular dependencies would cause the plugin scheduler to fail at runtime.

Usage:
    python scripts/validation/check_plugin_cycles.py [--verbose]

Exit codes:
    0 - No cycles detected
    1 - Cycles detected or error occurred
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
    # Project manifests are optional
    projects_root = repo_root / "projects"
    if projects_root.exists():
        for project_dir in sorted(projects_root.iterdir()):
            if project_dir.is_dir():
                project_manifests = sorted(project_dir.rglob("plugins.yaml"))
                manifests.extend(project_manifests)
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


def detect_cycles(graph: dict[str, set[str]]) -> list[list[str]]:
    """Detect cycles in dependency graph using DFS.

    Returns:
        List of cycles found. Each cycle is a list of plugin_ids forming the cycle.
    """
    cycles: list[list[str]] = []
    visited: set[str] = set()
    rec_stack: set[str] = set()

    def dfs(node: str, path: list[str]) -> bool:
        """DFS to detect cycles. Returns True if cycle found."""
        visited.add(node)
        rec_stack.add(node)
        path.append(node)

        for neighbor in graph.get(node, set()):
            if neighbor not in graph:
                # Dependency to non-existent plugin - skip (validated elsewhere)
                continue
            if neighbor not in visited:
                if dfs(neighbor, path):
                    return True
            elif neighbor in rec_stack:
                # Found a cycle
                cycle_start = path.index(neighbor)
                cycle = path[cycle_start:] + [neighbor]
                cycles.append(cycle)
                return True

        path.pop()
        rec_stack.remove(node)
        return False

    for node in sorted(graph.keys()):
        if node not in visited:
            dfs(node, [])

    return cycles


def format_cycle(cycle: list[str]) -> str:
    """Format a cycle for display."""
    return " -> ".join(cycle)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Check plugin dependency graph for cycles."
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show detailed output including all plugins scanned.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    repo_root = _repo_root()

    manifests = _discover_manifests(repo_root)
    if not manifests:
        print("ERROR: No plugin manifests found")
        return 1

    if args.verbose:
        print(f"Scanning {len(manifests)} manifest files...")
        for m in manifests:
            print(f"  - {m.relative_to(repo_root)}")

    graph = build_dependency_graph(manifests)
    if args.verbose:
        print(f"Built dependency graph with {len(graph)} plugins")

    cycles = detect_cycles(graph)

    if cycles:
        print(f"ERROR: {len(cycles)} circular dependency cycle(s) detected:")
        for i, cycle in enumerate(cycles, 1):
            print(f"  {i}. {format_cycle(cycle)}")
        return 1

    print(f"OK: No circular dependencies in {len(graph)} plugins")
    return 0


if __name__ == "__main__":
    sys.exit(main())
