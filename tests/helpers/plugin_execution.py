"""Plugin execution helpers for ADR 0099 test migration."""

from __future__ import annotations

from typing import Any, Iterable


def _infer_stage_for_plugin_id(plugin_id: str):
    from kernel.plugin_base import Stage

    if ".discover" in plugin_id:
        return Stage.DISCOVER
    if ".compiler" in plugin_id:
        return Stage.COMPILE
    if ".validator" in plugin_id:
        return Stage.VALIDATE
    if ".generator" in plugin_id:
        return Stage.GENERATE
    if ".assembler" in plugin_id:
        return Stage.ASSEMBLE
    if ".builder" in plugin_id:
        return Stage.BUILD
    return None


def run_plugin_for_test(plugin, ctx, stage, *, consumes_keys: Iterable[str] | None = None) -> Any:
    """Execute plugin with scoped context wiring.

    Transitional helper for legacy integration tests while migrating to
    snapshot/envelope-native assertions.
    """

    keys = set(consumes_keys or ())
    ctx._set_execution_context(plugin.plugin_id, keys)
    try:
        return plugin.execute(ctx, stage)
    finally:
        ctx._clear_execution_context()


def publish_for_test(
    ctx,
    producer_plugin_id: str,
    key: str,
    value: Any,
    *,
    consumes_keys: Iterable[str] | None = None,
    stage: Any | None = None,
    infer_stage: bool = True,
) -> None:
    """Publish fixture payload under a producer plugin identity for tests."""

    effective_stage = (
        stage if stage is not None else (_infer_stage_for_plugin_id(producer_plugin_id) if infer_stage else None)
    )
    ctx._set_execution_context(producer_plugin_id, set(consumes_keys or ()), stage=effective_stage)
    try:
        ctx.publish(key, value)
    finally:
        ctx._clear_execution_context()


__all__ = ["run_plugin_for_test", "publish_for_test"]
