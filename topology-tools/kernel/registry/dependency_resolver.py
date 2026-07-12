"""Plugin dependency resolver (ADR 0063 registry decomposition).

This module handles plugin dependency graph resolution and validation.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .spec_validator import SpecValidator

if TYPE_CHECKING:
    from ..specs import PluginSpec

__all__ = ["DependencyResolver", "PluginCycleError", "DependencyError"]


class DependencyError(Exception):
    """Dependency resolution error."""

    def __init__(self, plugin_id: str, message: str) -> None:
        self.plugin_id = plugin_id
        super().__init__(f"Plugin '{plugin_id}': {message}")


class PluginCycleError(Exception):
    """Circular dependency detected in plugins."""

    def __init__(self, cycle: list[str]) -> None:
        self.cycle = cycle
        super().__init__(f"Circular plugin dependency: {' -> '.join(cycle)}")


class DependencyResolver:
    """Resolve plugin dependency graph and compute execution order."""

    def __init__(self, specs: dict[str, PluginSpec]) -> None:
        """Initialize resolver.

        Args:
            specs: Dictionary of plugin ID -> PluginSpec
        """
        self._specs = specs
        self._order: list[str] | None = None

    @property
    def specs(self) -> dict[str, PluginSpec]:
        """Return specs dictionary."""
        return self._specs

    def resolve(self) -> list[str]:
        """Resolve plugin dependencies and return execution order.

        Returns:
            List of plugin IDs in topological order

        Raises:
            PluginCycleError: If circular dependency detected
            DependencyError: If dependency not found or invalid
        """
        self._validate_dependencies()
        self._validate_data_bus_contracts()
        self._order = self._topological_sort()
        return self._order

    def _validate_dependencies(self) -> None:
        """Validate all declared dependencies exist and are valid."""
        for spec in self._specs.values():
            for dep_id in spec.depends_on:
                if dep_id not in self._specs:
                    raise DependencyError(spec.id, f"Missing dependency: {dep_id}")

                dep_spec = self._specs[dep_id]
                if not self._is_allowed_dependency(spec, dep_spec):
                    raise DependencyError(
                        spec.id,
                        f"Forward stage/phase dependency is not allowed: "
                        f"'{spec.id}' ({[s.value for s in spec.stages]}/{spec.phase.value}) depends on "
                        f"'{dep_id}' ({[s.value for s in dep_spec.stages]}/{dep_spec.phase.value})",
                    )

    def _is_allowed_dependency(self, spec: PluginSpec, dep_spec: PluginSpec) -> bool:
        """Check if dependency is allowed (backward or same stage/phase)."""
        for stage in spec.stages:
            for dep_stage in dep_spec.stages:
                dep_stage_rank = SpecValidator.stage_rank(dep_stage)
                stage_rank = SpecValidator.stage_rank(stage)

                # Earlier stage is always allowed
                if dep_stage_rank < stage_rank:
                    return True

                # Same stage: check phase order
                if dep_stage_rank == stage_rank:
                    if SpecValidator.phase_rank(dep_spec.phase) <= SpecValidator.phase_rank(spec.phase):
                        return True

        return False

    def _validate_data_bus_contracts(self) -> None:
        """Validate declared consumes/producers compatibility across specs."""
        for consumer_spec in self._specs.values():
            for consume_entry in consumer_spec.consumes:
                if not isinstance(consume_entry, dict):
                    continue

                from_plugin = consume_entry.get("from_plugin")
                key = consume_entry.get("key")

                if not isinstance(from_plugin, str) or not from_plugin:
                    continue
                if not isinstance(key, str) or not key:
                    continue

                producer_spec = self._specs.get(from_plugin)
                if producer_spec is None:
                    if from_plugin in consumer_spec.depends_on:
                        raise DependencyError(
                            consumer_spec.id,
                            f"consumes references unknown producer '{from_plugin}'.",
                        )
                    # Base-manifest bootstrap may declare consumes against module/plugin
                    # manifests that are discovered only after discover-stage startup.
                    # Treat those consume-only references as deferred and validate them
                    # once the producer manifest is actually loaded into the registry.
                    continue

                if from_plugin not in consumer_spec.depends_on and not self._is_consume_order_valid(
                    consumer_spec, producer_spec
                ):
                    raise DependencyError(
                        consumer_spec.id,
                        "consumes requires an earlier producer by stage/phase/order "
                        f"or an explicit depends_on entry: '{from_plugin}.{key}'.",
                    )

                # Check produced scope
                produced_scopes = producer_spec.declared_produced_scopes()
                if produced_scopes and key not in produced_scopes:
                    raise DependencyError(
                        consumer_spec.id,
                        f"consumes references undeclared producer key '{from_plugin}.{key}'.",
                    )

                # Validate stage_local scope
                key_scope = produced_scopes.get(key)
                if key_scope == "stage_local" and not self._is_stage_local_consumption_valid(
                    producer_spec, consumer_spec
                ):
                    raise DependencyError(
                        consumer_spec.id,
                        f"stage_local key cannot cross stage boundary: "
                        f"'{from_plugin}.{key}' from {producer_spec.phase.value}/{[s.value for s in producer_spec.stages]} "
                        f"to {consumer_spec.phase.value}/{[s.value for s in consumer_spec.stages]}",
                    )

    def _is_consume_order_valid(self, consumer_spec: PluginSpec, producer_spec: PluginSpec) -> bool:
        """Return True when consumes can rely on stage/phase/order instead of depends_on."""
        for consumer_stage in consumer_spec.stages:
            consumer_stage_rank = SpecValidator.stage_rank(consumer_stage)
            consumer_phase_rank = SpecValidator.phase_rank(consumer_spec.phase)
            for producer_stage in producer_spec.stages:
                producer_stage_rank = SpecValidator.stage_rank(producer_stage)
                producer_phase_rank = SpecValidator.phase_rank(producer_spec.phase)

                if producer_stage_rank < consumer_stage_rank:
                    return True
                if producer_stage_rank > consumer_stage_rank:
                    continue
                if producer_phase_rank < consumer_phase_rank:
                    return True
                if producer_phase_rank > consumer_phase_rank:
                    continue
                if producer_spec.order <= consumer_spec.order:
                    return True
        return False

    def _is_stage_local_consumption_valid(self, producer: PluginSpec, consumer: PluginSpec) -> bool:
        """Check if stage_local consumption is valid (same stage, producer first)."""
        for producer_stage in producer.stages:
            for consumer_stage in consumer.stages:
                if producer_stage != consumer_stage:
                    continue
                if SpecValidator.phase_rank(producer.phase) <= SpecValidator.phase_rank(consumer.phase):
                    return True
        return False

    def _topological_sort(self) -> list[str]:
        """Perform topological sort with cycle detection.

        Returns:
            List of plugin IDs in topological order

        Raises:
            PluginCycleError: If cycle detected
        """
        visited: set[str] = set()
        in_stack: set[str] = set()
        order: list[str] = []

        def visit(plugin_id: str, path: list[str]) -> None:
            if plugin_id in in_stack:
                cycle_start = path.index(plugin_id)
                raise PluginCycleError(path[cycle_start:] + [plugin_id])

            if plugin_id in visited:
                return

            in_stack.add(plugin_id)
            path.append(plugin_id)

            for dep_id in self._specs[plugin_id].depends_on:
                visit(dep_id, path)

            path.pop()
            in_stack.remove(plugin_id)
            visited.add(plugin_id)
            order.append(plugin_id)

        for plugin_id in self._specs:
            if plugin_id not in visited:
                visit(plugin_id, [])

        return order
