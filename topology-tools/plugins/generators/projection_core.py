#!/usr/bin/env python3
"""Core projection helpers shared by generator projection modules.

ADR0078 WP-005: Exclusion patterns are extracted to module-level constants
to reduce hardcoding in core projection logic.
"""

from __future__ import annotations

import json
from copy import deepcopy
from typing import Any

# ADR0078 WP-005: Ansible host candidate exclusion patterns.
# These class/object refs represent infrastructure that cannot be managed by Ansible
# (physical cables, network links). Extracted from _is_ansible_host_candidate().
#
# TODO(ADR0078-evolution): Consider moving these to model schema as a class-level
# property (e.g., `ansible_managed: false`) for full declarative configuration.
ANSIBLE_HOST_EXCLUDED_CLASS_REFS: frozenset[str] = frozenset(
    {
        "class.network.physical_link",
    }
)

ANSIBLE_HOST_EXCLUDED_OBJECT_REFS: frozenset[str] = frozenset(
    {
        "obj.network.ethernet_cable",
    }
)

# ADR0078 WP-006: Canonical group names for instance collections.
# These correspond to layer directories in topology/instances/ and are used
# by projection builders to extract typed instance collections.
#
# TODO(ADR0078-evolution): Consider deriving these from topology layer schema
# or project manifest for full declarative configuration.
GROUP_DEVICES: str = "devices"
GROUP_LXC: str = "lxc"
GROUP_VMS: str = "vms"
GROUP_SERVICES: str = "services"
GROUP_NETWORK: str = "network"


class ProjectionError(ValueError):
    """Raised when compiled model does not satisfy projection contract."""


def _require_mapping(node: Any, *, path: str) -> dict[str, Any]:
    if not isinstance(node, dict):
        raise ProjectionError(f"{path} must be mapping/object")
    return node


def _require_rows(node: Any, *, path: str) -> list[dict[str, Any]]:
    if node is None:
        return []
    if not isinstance(node, list):
        raise ProjectionError(f"{path} must be list")
    rows: list[dict[str, Any]] = []
    for idx, row in enumerate(node):
        if not isinstance(row, dict):
            raise ProjectionError(f"{path}[{idx}] must be mapping/object")
        rows.append(deepcopy(row))
    return rows


def _row_sort_key(row: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(row.get("instance_id", "")),
        str(row.get("object_ref", "")),
        json.dumps(row, sort_keys=True, ensure_ascii=True),
    )


def _sorted_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(rows, key=_row_sort_key)


def _require_non_empty_str(row: dict[str, Any], *, field: str, path: str) -> str:
    value = row.get(field)
    if not isinstance(value, str) or not value:
        raise ProjectionError(f"{path}.{field} must be non-empty string")
    return value


def _instance_groups(compiled_json: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    root = _require_mapping(compiled_json, path="compiled_json")
    instances = _require_mapping(root.get("instances"), path="compiled_json.instances")
    groups: dict[str, list[dict[str, Any]]] = {}
    for group_name, node in instances.items():
        groups[group_name] = _require_rows(node, path=f"compiled_json.instances.{group_name}")
    return groups


def _group_rows(
    groups: dict[str, list[dict[str, Any]]],
    *,
    canonical: str,
) -> list[dict[str, Any]]:
    """Return rows for canonical group name only (strict model)."""
    return groups.get(canonical, [])


def _is_ansible_host_candidate(row: dict[str, Any]) -> bool:
    """Check if instance row represents a host manageable by Ansible.

    Excludes infrastructure objects (cables, physical links) that cannot
    be managed via SSH/Ansible.
    """
    class_ref = str(row.get("class_ref", ""))
    object_ref = str(row.get("object_ref", ""))
    # ADR0078 WP-005: Use module-level constants instead of inline literals
    if class_ref in ANSIBLE_HOST_EXCLUDED_CLASS_REFS:
        return False
    if object_ref in ANSIBLE_HOST_EXCLUDED_OBJECT_REFS:
        return False
    return True


def _get_instance_data(row: dict[str, Any], path: str, default: Any = None) -> Any:
    """Get a value from row by dot-separated path, checking nested fields."""
    parts = path.split(".")
    current: Any = row
    for part in parts:
        if not isinstance(current, dict):
            return default
        current = current.get(part)
        if current is None:
            return default
    return current
