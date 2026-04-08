"""Programmatic Terraform emitters for ADR0092 hybrid rendering."""

from __future__ import annotations


def render_backend_tf(*, backend_name: str, backend_items: list[tuple[str, str]]) -> str:
    """Render terraform backend block without Jinja templates."""
    lines = [
        "terraform {",
        f'  backend "{backend_name}" {{',
    ]
    for key, value in backend_items:
        lines.append(f"    {key} = {value}")
    lines.extend(
        [
            "  }",
            "}",
        ]
    )
    return "\n".join(lines) + "\n"
