"""Shared Terraform helper utilities for object-level generators (ADR0078 WP-001)."""

from __future__ import annotations

import json
from typing import Any


def render_string_list(items: list[str]) -> str:
    """Render a Python list of strings as a Terraform list expression.

    Args:
        items: List of string values to render.

    Returns:
        Terraform-compatible list literal, e.g., '["a", "b"]' or '[]'.
    """
    if not items:
        return "[]"
    joined = ", ".join(json.dumps(item, ensure_ascii=True) for item in items)
    return f"[{joined}]"


def render_hcl_literal(value: Any) -> str:
    """Render Python scalar/list/dict into Terraform HCL literal."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return str(value)
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=True)
    if isinstance(value, list):
        rendered = ", ".join(render_hcl_literal(item) for item in value)
        return f"[{rendered}]"
    if isinstance(value, dict):
        pairs = ", ".join(f"{key} = {render_hcl_literal(value[key])}" for key in sorted(value))
        return f"{{{pairs}}}"
    return json.dumps(str(value), ensure_ascii=True)


def resolve_remote_state_backend(config: Any) -> tuple[str, list[tuple[str, str]]] | None:
    """Normalize optional remote state backend config for templates.

    Expected shape:
    {
      "enabled": true,
      "backend": "s3",
      "config": {"bucket": "...", "key": "...", ...}
    }
    """
    if not isinstance(config, dict):
        return None
    if not bool(config.get("enabled", False)):
        return None
    backend = str(config.get("backend", "")).strip()
    if not backend:
        return None
    backend_cfg = config.get("config")
    if not isinstance(backend_cfg, dict) or not backend_cfg:
        return None

    items: list[tuple[str, str]] = []
    for key in sorted(backend_cfg):
        key_str = str(key).strip()
        if not key_str:
            continue
        items.append((key_str, render_hcl_literal(backend_cfg[key])))

    if not items:
        return None
    return backend, items
