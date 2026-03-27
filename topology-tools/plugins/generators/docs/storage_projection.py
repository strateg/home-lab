"""Storage domain projection for docs generator (ADR0079 Phase D)."""

from __future__ import annotations

from typing import Any

from plugins.generators.projection_core import ProjectionError, _instance_groups, _sorted_rows


def build_storage_projection(compiled_json: dict[str, Any]) -> dict[str, Any]:
    """Build deterministic storage/data-asset documentation view."""
    groups = _instance_groups(compiled_json)
    storage_rows = groups.get("storage", [])
    operation_rows = groups.get("operations", [])

    pools: list[dict[str, Any]] = []
    data_assets: list[dict[str, Any]] = []
    mount_chains: list[dict[str, Any]] = []

    for idx, row in enumerate(storage_rows):
        if not isinstance(row, dict):
            raise ProjectionError(f"compiled_json.instances.storage[{idx}] must be mapping/object")
        instance_id = row.get("instance_id")
        if not isinstance(instance_id, str) or not instance_id:
            raise ProjectionError(f"compiled_json.instances.storage[{idx}].instance_id must be non-empty string")
        class_ref = str(row.get("class_ref", ""))
        instance_data = row.get("instance_data")
        if not isinstance(instance_data, dict):
            instance_data = {}
        common = {
            "instance_id": instance_id,
            "object_ref": row.get("object_ref", ""),
            "class_ref": class_ref,
            "host_ref": instance_data.get("host_ref", ""),
            "status": row.get("status", ""),
            "notes": row.get("notes", ""),
        }
        if "storage.pool" in class_ref:
            pools.append(common)
        elif "storage.data_asset" in class_ref:
            asset = dict(common)
            asset.update(
                {
                    "engine": instance_data.get("engine", ""),
                    "criticality": instance_data.get("criticality", ""),
                    "backup_policy": instance_data.get("backup_policy", ""),
                }
            )
            data_assets.append(asset)

    for idx, row in enumerate(operation_rows):
        if not isinstance(row, dict):
            raise ProjectionError(f"compiled_json.instances.operations[{idx}] must be mapping/object")
        instance_id = row.get("instance_id")
        if not isinstance(instance_id, str) or not instance_id:
            raise ProjectionError(f"compiled_json.instances.operations[{idx}].instance_id must be non-empty string")
        instance_data = row.get("instance_data")
        if not isinstance(instance_data, dict):
            instance_data = {}
        mount_chains.append(
            {
                "operation_id": instance_id,
                "target_ref": instance_data.get("target_ref", ""),
                "storage_ref": instance_data.get("storage_ref", ""),
                "data_asset_ref": instance_data.get("data_asset_ref", ""),
                "schedule": instance_data.get("schedule", ""),
                "mode": instance_data.get("mode", ""),
            }
        )

    return {
        "storage_pools": _sorted_rows(pools),
        "data_assets": _sorted_rows(data_assets),
        "mount_chains": _sorted_rows(mount_chains),
        "counts": {
            "storage_pools": len(pools),
            "data_assets": len(data_assets),
            "mount_chains": len(mount_chains),
        },
    }
