"""Plugin scheduler submodules.

This package provides modular components for plugin execution scheduling:

- execution_planner: Plan plugin execution order and filtering
- parallel_executor: Execute plugins in parallel with subinterpreters
- snapshot_builder: Build input snapshots for isolated execution

Usage:
    from kernel.scheduler import ExecutionPlanner, ParallelExecutor
    # Or import from main plugin_registry for backwards compatibility
"""

from __future__ import annotations

__all__ = [
    "ExecutionPlanner",
    "ParallelExecutor",
    "SnapshotBuilder",
]


def __getattr__(name: str):
    """Lazy import for backwards compatibility during migration."""
    if name in __all__:
        raise ImportError(
            f"{name} not yet extracted. Import from kernel.plugin_registry instead."
        )
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
