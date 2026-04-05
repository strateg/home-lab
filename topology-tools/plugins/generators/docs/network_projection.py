"""Network domain projection for docs generator (ADR0079 Phase A)."""

from __future__ import annotations

from typing import Any

from plugins.generators.projection_core import (
    GROUP_NETWORK,
    ProjectionError,
    _group_rows,
    _instance_groups,
    _require_object_ref,
    _resolved_class_ref,
    _sorted_rows,
)


def build_network_projection(compiled_json: dict[str, Any]) -> dict[str, Any]:
    """Build deterministic network documentation view."""
    groups = _instance_groups(compiled_json)
    network_rows = _group_rows(groups, canonical=GROUP_NETWORK)

    networks: list[dict[str, Any]] = []
    bridges: list[dict[str, Any]] = []
    allocations: list[dict[str, Any]] = []

    for idx, row in enumerate(network_rows):
        instance_id = row.get("instance_id")
        if not isinstance(instance_id, str) or not instance_id:
            raise ProjectionError(f"compiled_json.instances.network[{idx}].instance_id must be non-empty string")
        object_ref = _require_object_ref(row, path=f"compiled_json.instances.network[{idx}]")
        class_ref = _resolved_class_ref(row)
        instance_data = row.get("instance_data")
        if not isinstance(instance_data, dict):
            instance_data = {}

        if "bridge" in class_ref:
            bridges.append(
                {
                    "instance_id": instance_id,
                    "object_ref": object_ref,
                    "class_ref": class_ref,
                    "host_ref": instance_data.get("host_ref", ""),
                    "status": row.get("status", ""),
                    "notes": row.get("notes", ""),
                }
            )
            continue
        if "vlan" not in class_ref:
            continue

        network_row = {
            "instance_id": instance_id,
            "object_ref": object_ref,
            "class_ref": class_ref,
            "managed_by_ref": instance_data.get("managed_by_ref", ""),
            "trust_zone_ref": instance_data.get("trust_zone_ref", ""),
            "dhcp_range": instance_data.get("dhcp_range", ""),
            "reserved_ranges": instance_data.get("reserved_ranges", []),
            "status": row.get("status", ""),
            "notes": row.get("notes", ""),
        }
        networks.append(network_row)

        raw_allocations = instance_data.get("ip_allocations")
        if not isinstance(raw_allocations, list):
            continue
        for alloc in raw_allocations:
            if not isinstance(alloc, dict):
                continue
            ip = alloc.get("ip")
            if not isinstance(ip, str) or not ip:
                continue
            allocations.append(
                {
                    "network_id": instance_id,
                    "ip": ip,
                    "device_ref": alloc.get("device_ref", ""),
                    "interface": alloc.get("interface", ""),
                    "description": alloc.get("description", ""),
                }
            )

    allocations = sorted(allocations, key=lambda row: (str(row.get("network_id", "")), str(row.get("ip", ""))))
    return {
        "networks": _sorted_rows(networks),
        "bridges": _sorted_rows(bridges),
        "allocations": allocations,
        "counts": {
            "networks": len(networks),
            "bridges": len(bridges),
            "allocations": len(allocations),
        },
    }
