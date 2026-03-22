#!/usr/bin/env python3
"""Shared (cross-object) projection helpers for generator plugins."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from plugins.generators.projection_core import (
    ProjectionError,
    _group_rows,
    _instance_groups,
    _is_ansible_host_candidate,
    _require_non_empty_str,
    _sorted_rows,
)


def build_ansible_projection(compiled_json: dict[str, Any]) -> dict[str, Any]:
    """Build stable view for Ansible inventory generator."""
    groups = _instance_groups(compiled_json)
    devices = _group_rows(groups, canonical="devices")
    lxc = _group_rows(groups, canonical="lxc")

    hosts: list[dict[str, Any]] = []
    for idx, row in enumerate(devices):
        _require_non_empty_str(row, field="instance_id", path=f"compiled_json.instances.devices[{idx}]")
        _require_non_empty_str(row, field="object_ref", path=f"compiled_json.instances.devices[{idx}]")
        if not _is_ansible_host_candidate(row):
            continue
        host = deepcopy(row)
        host["inventory_group"] = "devices"
        hosts.append(host)
    for idx, row in enumerate(lxc):
        _require_non_empty_str(row, field="instance_id", path=f"compiled_json.instances.lxc[{idx}]")
        _require_non_empty_str(row, field="object_ref", path=f"compiled_json.instances.lxc[{idx}]")
        host = deepcopy(row)
        host["inventory_group"] = "lxc"
        hosts.append(host)

    return {
        "hosts": _sorted_rows(hosts),
        "counts": {
            "hosts": len(hosts),
        },
    }
