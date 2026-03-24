#!/usr/bin/env python3
"""Shared (cross-object) projection helpers for generator plugins."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from plugins.generators.projection_core import (  # ADR0078 WP-006: Group canonical name constants
    GROUP_DEVICES,
    GROUP_LXC,
    GROUP_NETWORK,
    GROUP_SERVICES,
    GROUP_VMS,
    ProjectionError,
    _get_instance_data,
    _group_rows,
    _instance_groups,
    _is_ansible_host_candidate,
    _require_non_empty_str,
    _sorted_rows,
)


def build_ansible_projection(compiled_json: dict[str, Any]) -> dict[str, Any]:
    """Build stable view for Ansible inventory generator."""
    groups = _instance_groups(compiled_json)
    devices = _group_rows(groups, canonical=GROUP_DEVICES)
    lxc = _group_rows(groups, canonical=GROUP_LXC)

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


def build_docs_projection(compiled_json: dict[str, Any]) -> dict[str, Any]:
    """Build stable docs view from compiled model groups."""
    groups = _instance_groups(compiled_json)
    devices = _group_rows(groups, canonical=GROUP_DEVICES)
    services = _group_rows(groups, canonical=GROUP_SERVICES)
    lxc = _group_rows(groups, canonical=GROUP_LXC)
    vms = _group_rows(groups, canonical=GROUP_VMS)
    networks = _group_rows(groups, canonical=GROUP_NETWORK)

    docs_devices: list[dict[str, Any]] = []
    for idx, row in enumerate(devices):
        _require_non_empty_str(row, field="instance_id", path=f"compiled_json.instances.devices[{idx}]")
        _require_non_empty_str(row, field="object_ref", path=f"compiled_json.instances.devices[{idx}]")
        docs_devices.append(
            {
                "instance_id": row["instance_id"],
                "object_ref": row["object_ref"],
                "class_ref": row.get("class_ref"),
                "status": row.get("status"),
                "layer": row.get("layer"),
            }
        )

    docs_services: list[dict[str, Any]] = []
    for idx, row in enumerate(services):
        _require_non_empty_str(row, field="instance_id", path=f"compiled_json.instances.services[{idx}]")
        _require_non_empty_str(row, field="object_ref", path=f"compiled_json.instances.services[{idx}]")
        runtime = row.get("runtime")
        if not isinstance(runtime, dict):
            runtime = _get_instance_data(row, "instance_data.runtime", {})
        runtime_type = runtime.get("type") if isinstance(runtime, dict) else None
        runtime_target = runtime.get("target_ref") if isinstance(runtime, dict) else None
        runtime_network = runtime.get("network_binding_ref") if isinstance(runtime, dict) else None
        docs_services.append(
            {
                "instance_id": row["instance_id"],
                "object_ref": row["object_ref"],
                "class_ref": row.get("class_ref"),
                "status": row.get("status"),
                "runtime_type": runtime_type if isinstance(runtime_type, str) else "",
                "runtime_target_ref": runtime_target if isinstance(runtime_target, str) else "",
                "runtime_network_ref": runtime_network if isinstance(runtime_network, str) else "",
            }
        )

    counts = {
        "devices": len(devices),
        "services": len(services),
        "lxc": len(lxc),
        "vms": len(vms),
        "networks": len(networks),
        "groups": len(groups),
    }

    return {
        "counts": counts,
        "devices": _sorted_rows(docs_devices),
        "services": _sorted_rows(docs_services),
        "groups": {name: len(rows) for name, rows in sorted(groups.items(), key=lambda item: item[0])},
    }
