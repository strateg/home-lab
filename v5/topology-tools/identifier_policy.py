"""Shared identifier policy for class/object/instance ids."""

from __future__ import annotations

import re

# Cross-platform filename-unsafe characters.
UNSAFE_IDENTIFIER_RE = re.compile(r'[<>:"/\\|?*]')


def contains_unsafe_identifier_chars(value: str) -> bool:
    """Return True when identifier contains cross-platform unsafe characters."""
    return bool(UNSAFE_IDENTIFIER_RE.search(value))


def normalize_identifier_for_filename(value: str) -> str:
    """Replace unsafe chars with dots for migration tooling."""
    return UNSAFE_IDENTIFIER_RE.sub(".", value).strip(" .")
