"""Shared Terraform helper utilities for object-level generators (ADR0078 WP-001)."""

from __future__ import annotations

import json


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
