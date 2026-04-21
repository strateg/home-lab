"""Plugin execution helpers for ADR 0099 test migration."""

from __future__ import annotations

from typing import Any, Iterable


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
) -> None:
    """Publish fixture payload under a producer plugin identity for tests."""

    ctx._set_execution_context(producer_plugin_id, set(consumes_keys or ()))
    try:
        ctx.publish(key, value)
    finally:
        ctx._clear_execution_context()


__all__ = ["run_plugin_for_test", "publish_for_test"]
