"""Plugin execution planner (ADR 0063 registry decomposition).

This module handles planning plugin execution order and filtering.
"""

from __future__ import annotations

import heapq
from typing import TYPE_CHECKING, Any, Optional

from ..plugin_base import Phase, PluginContext, Stage
from ..registry.spec_validator import SpecValidator

if TYPE_CHECKING:
    from ..plugin_registry import PluginSpec

__all__ = ["ExecutionPlanner", "PlanningError"]


class PlanningError(Exception):
    """Execution planning error."""

    def __init__(self, message: str) -> None:
        super().__init__(message)


class ExecutionPlanner:
    """Plan plugin execution order and filtering."""

    def __init__(self, specs: dict[str, PluginSpec]) -> None:
        """Initialize planner.

        Args:
            specs: Dictionary of plugin ID -> PluginSpec
        """
        self._specs = specs

    @property
    def specs(self) -> dict[str, PluginSpec]:
        """Return specs dictionary."""
        return self._specs

    def get_execution_order(
        self,
        stage: Stage,
        phase: Phase = Phase.RUN,
        profile: Optional[str] = None,
    ) -> list[str]:
        """Get plugins to execute for a stage, in order.

        Args:
            stage: Pipeline stage
            phase: Execution phase
            profile: Current execution profile (for filtering)

        Returns:
            List of plugin IDs in execution order
        """
        # Filter plugins for this stage+phase
        stage_plugins = {
            spec.id: spec
            for spec in self._specs.values()
            if stage in spec.stages and spec.phase == phase and self._profile_allows_spec(spec, profile)
        }

        if not stage_plugins:
            return []

        # Stage-local topological ordering with deterministic ready-queue policy:
        # depends_on -> order -> lexical id
        return self._topological_order(stage_plugins)

    def _topological_order(self, stage_plugins: dict[str, PluginSpec]) -> list[str]:
        """Compute topological order for stage-local plugins.

        Args:
            stage_plugins: Dict of plugin ID -> spec for this stage

        Returns:
            Ordered list of plugin IDs
        """
        from ..registry.dependency_resolver import PluginCycleError

        indegree: dict[str, int] = {plugin_id: 0 for plugin_id in stage_plugins}
        outgoing: dict[str, list[str]] = {plugin_id: [] for plugin_id in stage_plugins}

        for plugin_id, spec in stage_plugins.items():
            for dep_id in spec.depends_on:
                if dep_id not in stage_plugins:
                    # Cross-stage dependency: not part of this stage DAG
                    continue
                indegree[plugin_id] += 1
                outgoing[dep_id].append(plugin_id)

        # Priority queue: (order, plugin_id)
        ready: list[tuple[int, str]] = []
        for plugin_id, spec in stage_plugins.items():
            if indegree[plugin_id] == 0:
                heapq.heappush(ready, (spec.order, plugin_id))

        ordered: list[str] = []
        while ready:
            _, plugin_id = heapq.heappop(ready)
            ordered.append(plugin_id)
            for dependent_id in outgoing[plugin_id]:
                indegree[dependent_id] -= 1
                if indegree[dependent_id] == 0:
                    dependent_spec = stage_plugins[dependent_id]
                    heapq.heappush(ready, (dependent_spec.order, dependent_id))

        if len(ordered) != len(stage_plugins):
            # Defensive guard for unexpected cycles
            remaining = sorted(plugin_id for plugin_id, degree in indegree.items() if degree > 0)
            raise PluginCycleError(remaining)

        return ordered

    def filter_by_context(
        self,
        plugin_ids: list[str],
        ctx: PluginContext,
    ) -> list[str]:
        """Filter plugins by context predicates.

        Args:
            plugin_ids: List of plugin IDs to filter
            ctx: Execution context

        Returns:
            Filtered list of plugin IDs
        """
        return [
            plugin_id
            for plugin_id in plugin_ids
            if plugin_id in self._specs and self._when_predicates_allow(self._specs[plugin_id], ctx)
        ]

    def _profile_allows_spec(self, spec: PluginSpec, profile: Optional[str]) -> bool:
        """Check if profile allows this spec to run."""
        if profile is None:
            return True

        modern = self._string_list(spec.when.get("profiles")) if isinstance(spec.when, dict) else []
        if modern:
            return profile in modern

        return True

    def _when_predicates_allow(self, spec: PluginSpec, ctx: PluginContext) -> bool:
        """Check if all when predicates allow this spec to run."""
        if not isinstance(spec.when, dict) or not spec.when:
            return True

        # Profile check
        profiles = self._string_list(spec.when.get("profiles"))
        if profiles and ctx.profile not in profiles:
            return False

        # Capabilities check
        capabilities = self._string_list(spec.when.get("capabilities"))
        if capabilities:
            available_caps = {key for key in (ctx.capability_catalog or {}).keys() if isinstance(key, str) and key}
            if not set(capabilities).issubset(available_caps):
                return False

        # Pipeline modes check
        pipeline_modes = self._string_list(spec.when.get("pipeline_modes"))
        if pipeline_modes:
            current_mode = str(ctx.config.get("pipeline_mode", ""))
            if current_mode not in pipeline_modes:
                return False

        # Changed scopes check
        changed_scopes = self._string_list(spec.when.get("changed_input_scopes"))
        if changed_scopes:
            active_scopes = self._active_changed_input_scopes(ctx)
            if active_scopes is None:
                # Runtime has not computed dirty scopes yet; keep non-blocking
                return True
            if not active_scopes:
                return False
            if "all" in active_scopes or "*" in active_scopes:
                return True
            if "all" in changed_scopes or "*" in changed_scopes:
                return True
            if active_scopes.isdisjoint(changed_scopes):
                return False

        return True

    def _active_changed_input_scopes(self, ctx: PluginContext) -> set[str] | None:
        """Get active changed input scopes from context."""
        if isinstance(ctx.changed_input_scopes, list):
            return {item for item in ctx.changed_input_scopes if isinstance(item, str) and item}

        configured_scopes = ctx.config.get("changed_input_scopes")
        if isinstance(configured_scopes, list):
            return {item for item in configured_scopes if isinstance(item, str) and item}

        return None

    @staticmethod
    def _string_list(value: Any) -> list[str]:
        """Convert value to list of strings."""
        if not isinstance(value, list):
            return []
        return [item for item in value if isinstance(item, str) and item]

    def plugin_sort_key(self, plugin_id: str) -> tuple[int, str]:
        """Get sort key for plugin (order, id)."""
        import sys

        spec = self._specs.get(plugin_id)
        order = spec.order if spec is not None else sys.maxsize
        return order, plugin_id
