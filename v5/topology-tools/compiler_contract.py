"""Compiled model contract helpers for compile-topology."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Callable


def canonicalize_payload(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":"), default=str)


def manifest_digest(manifest: dict[str, Any]) -> str:
    canonical = canonicalize_payload(manifest)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def validate_compiled_model_contract(
    *,
    payload: dict[str, Any],
    add_diag: Callable[..., None],
    supported_compiled_model_major: set[str],
) -> bool:
    if not isinstance(payload, dict):
        add_diag(
            code="E6903",
            severity="error",
            stage="validate",
            message="compiled_json payload must be an object.",
            path="compiled_json",
        )
        return False

    required_string_keys = (
        "compiled_model_version",
        "compiled_at",
        "compiler_pipeline_version",
        "source_manifest_digest",
    )
    has_errors = False
    for key in required_string_keys:
        value = payload.get(key)
        if not isinstance(value, str) or not value:
            has_errors = True
            add_diag(
                code="E6903",
                severity="error",
                stage="validate",
                message=f"compiled model contract requires non-empty string key '{key}'.",
                path=f"compiled_json.{key}",
            )

    version = payload.get("compiled_model_version")
    if isinstance(version, str) and version:
        major = version.split(".", 1)[0]
        if major not in supported_compiled_model_major:
            has_errors = True
            add_diag(
                code="E6903",
                severity="error",
                stage="validate",
                message=(
                    f"incompatible compiled_model_version '{version}'; "
                    f"supported majors: {sorted(supported_compiled_model_major)}."
                ),
                path="compiled_json.compiled_model_version",
            )

    return not has_errors
