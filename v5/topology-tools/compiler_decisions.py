"""Decision helpers for compile-topology pipeline mode and parity behavior."""

from __future__ import annotations

from typing import Any, Callable


def select_effective_payload(
    *,
    mode: str,
    parity_gate: bool,
    enable_plugins: bool,
    legacy_payload: dict[str, Any],
    plugin_payload: dict[str, Any] | None,
    canonicalize_payload: Callable[[dict[str, Any]], str],
    add_diag: Callable[..., None],
) -> dict[str, Any]:
    if parity_gate and not enable_plugins:
        add_diag(
            code="E6902",
            severity="error",
            stage="validate",
            message="--parity-gate requires --enable-plugins to compare legacy and plugin outputs.",
            path="pipeline:parity",
        )

    if mode == "legacy":
        if plugin_payload is not None:
            legacy_digest = canonicalize_payload(legacy_payload)
            plugin_digest = canonicalize_payload(plugin_payload)
            if legacy_digest != plugin_digest:
                if parity_gate:
                    add_diag(
                        code="E6902",
                        severity="error",
                        stage="validate",
                        message="Parity gate failed: plugin effective model differs from legacy model.",
                        path="pipeline:parity",
                    )
                else:
                    add_diag(
                        code="W6901",
                        severity="warning",
                        stage="validate",
                        message="Plugin effective model differs from legacy effective model (parity drift).",
                        path="pipeline:mode",
                    )
        return legacy_payload

    # plugin-first mode
    if not enable_plugins:
        add_diag(
            code="E6901",
            severity="error",
            stage="validate",
            message="pipeline_mode=plugin-first requires --enable-plugins.",
            path="pipeline:mode",
        )
        return legacy_payload

    if plugin_payload is None:
        add_diag(
            code="E6901",
            severity="error",
            stage="validate",
            message="pipeline_mode=plugin-first requires compiler plugins to publish ctx.compiled_json.",
            path="pipeline:mode",
        )
        return legacy_payload

    if parity_gate:
        legacy_digest = canonicalize_payload(legacy_payload)
        plugin_digest = canonicalize_payload(plugin_payload)
        if legacy_digest != plugin_digest:
            add_diag(
                code="E6902",
                severity="error",
                stage="validate",
                message="Parity gate failed in plugin-first mode: plugin model is not parity-equivalent to legacy.",
                path="pipeline:parity",
            )

    add_diag(
        code="I6901",
        severity="info",
        stage="validate",
        message="Pipeline mode plugin-first is active; effective output source is plugin ctx.compiled_json.",
        path="pipeline:mode",
        confidence=1.0,
    )
    return plugin_payload
