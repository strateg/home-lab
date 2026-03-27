"""Physical domain projection for docs generator (ADR0079 Phase B)."""

from __future__ import annotations

from typing import Any

from plugins.generators.projection_core import GROUP_DEVICES, ProjectionError, _group_rows, _instance_groups, _sorted_rows


def build_physical_projection(compiled_json: dict[str, Any]) -> dict[str, Any]:
    """Build deterministic physical topology view from compiled model."""
    groups = _instance_groups(compiled_json)
    device_rows = _group_rows(groups, canonical=GROUP_DEVICES)
    data_channel_rows = groups.get("data-channels", [])
    physical_link_rows = groups.get("physical-links", [])
    power_rows = groups.get("power", [])

    devices: list[dict[str, Any]] = []
    for idx, row in enumerate(device_rows):
        instance_id = row.get("instance_id")
        if not isinstance(instance_id, str) or not instance_id:
            raise ProjectionError(f"compiled_json.instances.devices[{idx}].instance_id must be non-empty string")
        object_ref = row.get("object_ref")
        if not isinstance(object_ref, str) or not object_ref:
            raise ProjectionError(f"compiled_json.instances.devices[{idx}].object_ref must be non-empty string")
        devices.append(
            {
                "instance_id": instance_id,
                "object_ref": object_ref,
                "class_ref": row.get("class_ref", ""),
                "status": row.get("status", ""),
                "layer": row.get("layer", ""),
                "notes": row.get("notes", ""),
            }
        )

    data_links: list[dict[str, Any]] = []
    for row in data_channel_rows:
        if not isinstance(row, dict):
            continue
        instance_data = row.get("instance_data")
        if not isinstance(instance_data, dict):
            instance_data = {}
        data_links.append(
            {
                "instance_id": row.get("instance_id", ""),
                "class_ref": row.get("class_ref", ""),
                "endpoint_a": instance_data.get("endpoint_a", {}),
                "endpoint_b": instance_data.get("endpoint_b", {}),
                "link_ref": instance_data.get("link_ref", ""),
                "negotiated_speed_mbps": instance_data.get("negotiated_speed_mbps"),
                "status": row.get("status", ""),
                "notes": row.get("notes", ""),
            }
        )

    physical_links: list[dict[str, Any]] = []
    for row in physical_link_rows:
        if not isinstance(row, dict):
            continue
        instance_data = row.get("instance_data")
        if not isinstance(instance_data, dict):
            instance_data = {}
        physical_links.append(
            {
                "instance_id": row.get("instance_id", ""),
                "class_ref": row.get("class_ref", ""),
                "endpoint_a": instance_data.get("endpoint_a", {}),
                "endpoint_b": instance_data.get("endpoint_b", {}),
                "category": instance_data.get("category", ""),
                "length_m": instance_data.get("length_m"),
                "creates_channel_ref": instance_data.get("creates_channel_ref", ""),
                "status": row.get("status", ""),
                "notes": row.get("notes", ""),
            }
        )

    power_inventory: list[dict[str, Any]] = []
    for row in power_rows:
        if not isinstance(row, dict):
            continue
        instance_data = row.get("instance_data")
        if not isinstance(instance_data, dict):
            instance_data = {}
        power_inventory.append(
            {
                "instance_id": row.get("instance_id", ""),
                "class_ref": row.get("class_ref", ""),
                "power": instance_data.get("power", {}),
                "status": row.get("status", ""),
                "notes": row.get("notes", ""),
            }
        )

    return {
        "devices": _sorted_rows(devices),
        "data_links": _sorted_rows(data_links),
        "physical_links": _sorted_rows(physical_links),
        "power_inventory": _sorted_rows(power_inventory),
        "counts": {
            "devices": len(devices),
            "data_links": len(data_links),
            "physical_links": len(physical_links),
            "power_inventory": len(power_inventory),
        },
    }
