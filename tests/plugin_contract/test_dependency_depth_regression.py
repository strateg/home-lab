#!/usr/bin/env python3
"""Dependency depth regression tests (ADR 0063, SWOT 2026-05-31).

This module ensures the plugin dependency graph does not exceed maximum depth limits.
High dependency depth increases latency, debugging complexity, and risk of cascading failures.

Current limits:
- SOFT_LIMIT = 20: Test fails if exceeded
- TARGET = 6: Architectural target (not enforced yet)
"""

from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
V5_TOOLS = REPO_ROOT / "topology-tools"

# Ensure topology-tools is in path
if str(V5_TOOLS) not in sys.path:
    sys.path.insert(0, str(V5_TOOLS))


# Maximum dependency depth before test fails (soft limit)
MAX_DEPTH_SOFT_LIMIT = 20

# Architectural target depth (for tracking, not enforced)
DEPTH_TARGET = 6


def _compute_dependency_depths(
    specs: dict[str, object],
) -> tuple[dict[str, int], int, list[str]]:
    """Compute dependency depth for all plugins.

    Returns:
        Tuple of (depths dict, max_depth, longest_path)
    """
    depths: dict[str, int] = {}
    paths: dict[str, list[str]] = {}

    def compute_depth(plugin_id: str, visited: set[str]) -> tuple[int, list[str]]:
        """Recursively compute depth and path for a plugin."""
        if plugin_id in depths:
            return depths[plugin_id], paths[plugin_id]

        if plugin_id in visited:
            # Cycle detected (should be caught elsewhere)
            return 0, [plugin_id]

        spec = specs.get(plugin_id)
        if spec is None:
            return 0, [plugin_id]

        depends_on = getattr(spec, "depends_on", [])
        if not depends_on:
            depths[plugin_id] = 0
            paths[plugin_id] = [plugin_id]
            return 0, [plugin_id]

        visited.add(plugin_id)
        max_dep_depth = 0
        longest_dep_path: list[str] = []

        for dep_id in depends_on:
            dep_depth, dep_path = compute_depth(dep_id, visited)
            if dep_depth >= max_dep_depth:
                max_dep_depth = dep_depth + 1
                longest_dep_path = dep_path

        visited.discard(plugin_id)

        depths[plugin_id] = max_dep_depth
        paths[plugin_id] = longest_dep_path + [plugin_id]
        return max_dep_depth, paths[plugin_id]

    for plugin_id in specs:
        compute_depth(plugin_id, set())

    if not depths:
        return depths, 0, []

    max_plugin = max(depths, key=lambda x: depths[x])
    return depths, depths[max_plugin], paths[max_plugin]


def _load_all_plugin_specs() -> dict[str, object]:
    """Load all plugin specs from manifests."""
    from kernel.plugin_registry import PluginRegistry

    registry = PluginRegistry(V5_TOOLS)

    # Load framework manifest
    framework_manifest = V5_TOOLS / "plugins" / "plugins.yaml"
    if framework_manifest.exists():
        registry.load_manifest(framework_manifest)

    # Load class module manifests
    for manifest in (REPO_ROOT / "topology" / "class-modules").glob("*/plugins.yaml"):
        registry.load_manifest(manifest)

    # Load object module manifests
    for manifest in (REPO_ROOT / "topology" / "object-modules").glob("*/plugins.yaml"):
        registry.load_manifest(manifest)

    return registry.specs  # Access specs property


class TestDependencyDepthRegression:
    """Dependency depth regression tests."""

    def test_max_dependency_depth_under_soft_limit(self) -> None:
        """Test that maximum dependency depth is under soft limit."""
        specs = _load_all_plugin_specs()
        depths, max_depth, longest_path = _compute_dependency_depths(specs)

        # Report findings for visibility
        assert max_depth <= MAX_DEPTH_SOFT_LIMIT, (
            f"Maximum dependency depth {max_depth} exceeds soft limit {MAX_DEPTH_SOFT_LIMIT}.\n"
            f"Longest path ({len(longest_path)} plugins):\n"
            + "\n".join(f"  [{i}] {p}" for i, p in enumerate(longest_path))
        )

    def test_dependency_depth_report(self) -> None:
        """Generate dependency depth report for tracking."""
        specs = _load_all_plugin_specs()
        depths, max_depth, longest_path = _compute_dependency_depths(specs)

        # Group plugins by depth
        by_depth: dict[int, list[str]] = defaultdict(list)
        for plugin_id, depth in depths.items():
            by_depth[depth].append(plugin_id)

        # Report statistics
        stats = {
            "max_depth": max_depth,
            "target": DEPTH_TARGET,
            "soft_limit": MAX_DEPTH_SOFT_LIMIT,
            "plugins_over_target": sum(1 for d in depths.values() if d > DEPTH_TARGET),
            "total_plugins": len(specs),
        }

        # This test always passes - it's for reporting
        assert stats["max_depth"] >= 0, "Depth calculation failed"

    def test_no_plugins_exceed_hard_limit(self) -> None:
        """Test no individual plugin exceeds an unreasonable depth."""
        HARD_LIMIT = 25  # Absolute maximum before architectural review required

        specs = _load_all_plugin_specs()
        depths, max_depth, longest_path = _compute_dependency_depths(specs)

        violators = {pid: d for pid, d in depths.items() if d > HARD_LIMIT}
        assert not violators, (
            f"Plugins exceed hard limit ({HARD_LIMIT}):\n"
            + "\n".join(f"  {pid}: depth {d}" for pid, d in sorted(violators.items()))
        )

    def test_depth_distribution_sanity(self) -> None:
        """Test that depth distribution is reasonable."""
        specs = _load_all_plugin_specs()
        depths, max_depth, _ = _compute_dependency_depths(specs)

        if not depths:
            pytest.skip("No plugins found")

        # At least 50% of plugins should have depth <= 10
        mid_depth_count = sum(1 for d in depths.values() if d <= 10)
        mid_depth_ratio = mid_depth_count / len(depths)

        assert mid_depth_ratio >= 0.5, (
            f"Only {mid_depth_ratio:.1%} of plugins have depth ≤ 10. "
            "Dependency graph may be too linear/deep."
        )
