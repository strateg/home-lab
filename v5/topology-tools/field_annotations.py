"""Centralized field annotation registry and parser."""

from __future__ import annotations

import re
from dataclasses import dataclass

ANNOTATION_DEFINITIONS: dict[str, dict[str, bool]] = {
    # Legacy ADR0068 markers.
    "required": {"required": True, "optional": False, "secret": False, "requires_format": True},
    "optional": {"required": False, "optional": True, "secret": False, "requires_format": True},
    # Secret marker without explicit type.
    "secret": {"required": False, "optional": False, "secret": True, "requires_format": False},
    # Combined markers (single annotation token with merged semantics).
    "required_secret": {"required": True, "optional": False, "secret": True, "requires_format": True},
    "optional_secret": {"required": False, "optional": True, "secret": True, "requires_format": True},
}

_ANNOTATION_RE = re.compile(r"^@([a-z][a-z0-9_]*)(?::([a-z][a-z0-9_]*))?$")


@dataclass(frozen=True)
class FieldAnnotation:
    name: str
    value_type: str | None
    required: bool
    optional: bool
    secret: bool


def parse_field_annotation(value: str) -> tuple[FieldAnnotation | None, str | None]:
    """Parse annotation token.

    Returns:
    - (None, None): value is not an annotation
    - (FieldAnnotation, None): parsed successfully
    - (None, <error>): value looks like annotation but is invalid
    """
    if not isinstance(value, str) or not value.startswith("@"):
        return None, None

    match = _ANNOTATION_RE.fullmatch(value)
    if match is None:
        return None, "invalid annotation syntax"

    name, value_type = match.groups()
    definition = ANNOTATION_DEFINITIONS.get(name)
    if definition is None:
        supported = ", ".join(sorted(ANNOTATION_DEFINITIONS))
        return None, f"unknown annotation '{name}' (supported: {supported})"

    requires_format = bool(definition.get("requires_format"))
    if requires_format and not value_type:
        return None, f"annotation '{name}' requires type suffix ':<type>'"
    if not requires_format and value_type:
        return None, f"annotation '{name}' must not have type suffix"

    return (
        FieldAnnotation(
            name=name,
            value_type=value_type,
            required=bool(definition.get("required")),
            optional=bool(definition.get("optional")),
            secret=bool(definition.get("secret")),
        ),
        None,
    )

