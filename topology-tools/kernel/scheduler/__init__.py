"""Plugin scheduler submodules (ADR 0063 decomposition).

This package provides modular components for plugin execution scheduling:

- execution_planner: Plan plugin execution order and filtering
- parallel_executor: Execute plugins in parallel with subinterpreters
- snapshot_builder: Build input snapshots for isolated execution

Usage:
    from kernel.scheduler import ExecutionPlanner, ParallelExecutor
    from kernel.scheduler import SnapshotBuilder, SerializablePluginSpec
"""

from __future__ import annotations

from .execution_planner import ExecutionPlanner, PlanningError
from .parallel_executor import (
    HAS_REAL_SUBINTERPRETERS,
    ParallelExecutor,
    execute_plugin_isolated,
)
from .snapshot_builder import SerializablePluginSpec, SnapshotBuilder

__all__ = [
    # execution_planner
    "ExecutionPlanner",
    "PlanningError",
    # parallel_executor
    "ParallelExecutor",
    "execute_plugin_isolated",
    "HAS_REAL_SUBINTERPRETERS",
    # snapshot_builder
    "SnapshotBuilder",
    "SerializablePluginSpec",
]
