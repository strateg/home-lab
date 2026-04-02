"""Shared capability helper utilities for object-level generators (ADR0078 WP-002)."""

from __future__ import annotations

from typing import Any


def capability_expression_enabled(capabilities: dict[str, Any], enabled_by: str) -> bool:
    """Check if a capability expression evaluates to truthy value.

    Args:
        capabilities: Dict of capability flags (e.g., {"has_ceph": True}).
        enabled_by: Dot-separated expression, optionally prefixed with "capabilities.".

    Returns:
        True if the expression resolves to a truthy value.
    """
    expr = enabled_by.strip()
    if not expr:
        return False
    if expr.startswith("capabilities."):
        expr = expr[len("capabilities.") :]

    current: Any = capabilities
    for segment in expr.split("."):
        if not isinstance(current, dict):
            return False
        current = current.get(segment)
    return bool(current)


def get_capability_templates(
    capabilities: dict[str, Any],
    config: dict[str, Any],
) -> dict[str, str]:
    """Resolve capability-driven templates from plugin config.

    Args:
        capabilities: Dict of capability flags from projection.
        config: Plugin config containing capability_templates mapping.

    Returns:
        Dict mapping output_file -> template_path for enabled capabilities.
    """
    result: dict[str, str] = {}
    cap_templates = config.get("capability_templates")

    # Normalize cap_templates to list of mappings
    # ADR0078 specifies dict format, but support legacy list format for compatibility
    mappings: list[dict[str, Any]] = []
    if isinstance(cap_templates, dict):
        mappings = [m for m in cap_templates.values() if isinstance(m, dict)]
    elif isinstance(cap_templates, list):
        # Legacy list format: [{"capability_key": ..., "template": ..., "output_file": ...}]
        mappings = [m for m in cap_templates if isinstance(m, dict)]
    else:
        return result

    for mapping in mappings:
        enabled_by = mapping.get("enabled_by")
        # TODO(ADR0078-cleanup): Remove capability_key fallback after v5.1 migration
        if not isinstance(enabled_by, str) or not enabled_by.strip():
            cap_key = mapping.get("capability_key", "")
            if isinstance(cap_key, str) and cap_key.strip():
                enabled_by = f"capabilities.{cap_key.strip()}"

        template = mapping.get("template", "")
        output_file = mapping.get("output")
        # TODO(ADR0078-cleanup): Remove output_file fallback after v5.1 migration
        if not isinstance(output_file, str) or not output_file.strip():
            output_file = mapping.get("output_file", "")

        if not isinstance(enabled_by, str) or not enabled_by.strip() or not template or not output_file:
            continue

        if capability_expression_enabled(capabilities, enabled_by):
            result[str(output_file)] = str(template)

    return result
