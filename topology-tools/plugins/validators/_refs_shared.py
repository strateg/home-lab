"""Shared utilities for refs-validators.

This module consolidates common patterns used across multiple reference
validators (lxc_refs, vm_refs, host_os_refs, docker_refs, etc.) to eliminate
code duplication per H2.2 of ARCHITECTURE-IMPROVEMENT-PLAN-2026-07-07.

Not a plugin - internal utility module (underscore prefix).
"""

from __future__ import annotations

from typing import Any


# Architecture aliases for normalization across platforms
# Canonical forms: x86_64, i386, arm64, riscv64
ARCH_ALIASES: dict[str, str] = {
    "x86_64": "x86_64",
    "amd64": "x86_64",
    "x86": "i386",
    "i386": "i386",
    "arm64": "arm64",
    "aarch64": "arm64",
    "riscv64": "riscv64",
    "riscv": "riscv64",
}

# OS statuses considered "active" for reference validation
ACTIVE_OS_STATUSES: set[str] = {"active", "mapped", "modeled"}


def get_extensions(row: dict[str, Any]) -> dict[str, Any]:
    """Extract extensions dict from a row, returning empty dict if missing/invalid."""
    extensions = row.get("extensions")
    if isinstance(extensions, dict):
        return extensions
    return {}


def normalize_architecture(value: Any) -> str:
    """Normalize architecture string to canonical form.

    Returns empty string for invalid input.
    Uses ARCH_ALIASES for mapping, preserves unknown architectures as-is.
    """
    if not isinstance(value, str):
        return ""
    normalized = value.strip().lower()
    return ARCH_ALIASES.get(normalized, normalized)


def build_row_lookup(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Build instance ID → row lookup dict from rows list.

    Args:
        rows: List of row dicts, each expected to have "instance" key.

    Returns:
        Dict mapping instance IDs to their row dicts.
        Skips rows without valid string instance IDs.
    """
    row_by_id: dict[str, dict[str, Any]] = {}
    for row in rows:
        row_id = row.get("instance")
        if isinstance(row_id, str) and row_id:
            row_by_id[row_id] = row
    return row_by_id
