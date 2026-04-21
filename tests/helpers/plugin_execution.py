"""Plugin execution helpers for envelope-based testing (ADR 0097/0099).

This module provides helpers that replace the legacy pattern:

    # LEGACY (do not use in new tests):
    ctx._set_execution_context(plugin.plugin_id, set())
    result = plugin.execute(ctx, stage)
    ctx._clear_execution_context()

    # MODERN (use this instead):
    from tests.helpers.plugin_execution import run_plugin_for_test
    result = run_plugin_for_test(plugin, ctx, stage)

The helpers encapsulate execution context management and provide a migration
path from legacy direct execution to envelope-based execution.

ADR References:
- ADR 0097: Actor-style dataflow execution model
- ADR 0099: Test architecture for snapshot/envelope/pipeline runtime
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Set

if TYPE_CHECKING:
    from kernel.plugin_base import BasePlugin, PluginContext, PluginResult, Stage


def run_plugin_for_test(
    plugin: BasePlugin,
    ctx: PluginContext,
    stage: Stage,
    *,
    consumes_keys: Set[str] | None = None,
) -> PluginResult:
    """Execute a plugin for testing with proper context setup.

    This helper encapsulates the execution context setup/teardown
    that tests previously did manually. It provides a migration path
    from legacy direct execution to envelope-based execution.

    Args:
        plugin: The plugin instance to execute
        ctx: The plugin context
        stage: The execution stage
        consumes_keys: Optional set of keys this plugin consumes

    Returns:
        PluginResult from plugin execution

    Example:
        >>> plugin = MyValidatorPlugin("my.validator")
        >>> ctx = PluginContext(topology_path="test.yaml", ...)
        >>> result = run_plugin_for_test(plugin, ctx, Stage.VALIDATE)
        >>> assert result.status == PluginStatus.SUCCESS

    Note:
        This helper uses the legacy _set_execution_context internally.
        For new tests, prefer run_plugin_isolated() when full envelope
        semantics are required.
    """
    keys = consumes_keys if consumes_keys is not None else set()
    ctx._set_execution_context(plugin.plugin_id, keys)  # noqa: SLF001
    try:
        return plugin.execute(ctx, stage)
    finally:
        ctx._clear_execution_context()  # noqa: SLF001


def run_plugin_isolated(
    plugin: BasePlugin,
    ctx: PluginContext,
    stage: Stage,
) -> PluginResult:
    """Execute a plugin in full isolation (envelope semantics).

    This is the target pattern for ADR 0099 compliance.
    Uses snapshot → execute → envelope flow.

    Args:
        plugin: The plugin instance to execute
        ctx: The plugin context (used to build snapshot)
        stage: The execution stage

    Returns:
        PluginResult from envelope

    Example:
        >>> plugin = MyValidatorPlugin("my.validator")
        >>> ctx = PluginContext(topology_path="test.yaml", ...)
        >>> result = run_plugin_isolated(plugin, ctx, Stage.VALIDATE)
        >>> assert result.status == PluginStatus.SUCCESS

    Note:
        This function provides full envelope isolation. The plugin
        receives a snapshot and returns an envelope, with no direct
        access to mutable context state.
    """
    from kernel.plugin_base import PluginInputSnapshot

    # Build input snapshot from context
    snapshot = PluginInputSnapshot(
        topology_path=ctx.topology_path,
        profile=ctx.profile,
        compiled_json=ctx.compiled_json,
        model_lock=ctx.model_lock,
        config=dict(ctx.config) if hasattr(ctx.config, "items") else ctx.config,
        output_dir=ctx.output_dir,
        classes=dict(ctx.classes) if ctx.classes else {},
        objects=dict(ctx.objects) if ctx.objects else {},
        available_data={},  # Populated from pipeline state in real execution
    )

    # Execute with envelope semantics
    envelope = plugin.execute_with_envelope(snapshot, stage)

    return envelope.result


def build_minimal_context(
    topology_path: str = "test.yaml",
    profile: str = "test",
    compiled_json: dict | None = None,
    **kwargs,
) -> PluginContext:
    """Build a minimal PluginContext for testing.

    Args:
        topology_path: Path to topology file
        profile: Profile name
        compiled_json: Compiled JSON data
        **kwargs: Additional context arguments

    Returns:
        PluginContext configured for testing
    """
    from kernel.plugin_base import PluginContext

    return PluginContext(
        topology_path=topology_path,
        profile=profile,
        model_lock=kwargs.pop("model_lock", {}),
        compiled_json=compiled_json or {},
        **kwargs,
    )
