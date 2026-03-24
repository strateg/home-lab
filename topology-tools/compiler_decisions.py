"""Decision helpers for plugin-first effective payload selection."""

from __future__ import annotations

from typing import Any, Callable


def select_effective_payload(
    *,
    plugin_payload: dict[str, Any] | None,
    add_diag: Callable[..., None],
) -> dict[str, Any]:
    if plugin_payload is None:
        add_diag(
            code="E6901",
            severity="error",
            stage="validate",
            message="pipeline_mode=plugin-first requires compiler plugins to publish ctx.compiled_json.",
            path="pipeline:mode",
        )
        return {}

    add_diag(
        code="I6901",
        severity="info",
        stage="validate",
        message="Pipeline mode plugin-first is active; effective output source is plugin ctx.compiled_json.",
        path="pipeline:mode",
        confidence=1.0,
    )
    return plugin_payload
