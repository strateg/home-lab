"""Operations/observability projection for docs generator (ADR0079 Phase E)."""

from __future__ import annotations

from typing import Any

from plugins.generators.projection_core import GROUP_SERVICES, ProjectionError, _group_rows, _instance_groups, _sorted_rows


def build_operations_projection(compiled_json: dict[str, Any]) -> dict[str, Any]:
    """Build deterministic operations documentation view."""
    groups = _instance_groups(compiled_json)
    observability_rows = groups.get("observability", [])
    operation_rows = groups.get("operations", [])
    service_rows = _group_rows(groups, canonical=GROUP_SERVICES)
    qos_rows = groups.get("qos", [])
    power_rows = groups.get("power", [])

    healthchecks: list[dict[str, Any]] = []
    alerts: list[dict[str, Any]] = []
    backup_policies: list[dict[str, Any]] = []
    vpn_services: list[dict[str, Any]] = []
    qos_policies: list[dict[str, Any]] = []
    ups_inventory: list[dict[str, Any]] = []

    for idx, row in enumerate(observability_rows):
        if not isinstance(row, dict):
            raise ProjectionError(f"compiled_json.instances.observability[{idx}] must be mapping/object")
        instance_id = row.get("instance_id")
        if not isinstance(instance_id, str) or not instance_id:
            raise ProjectionError(f"compiled_json.instances.observability[{idx}].instance_id must be non-empty string")
        class_ref = str(row.get("class_ref", ""))
        instance_data = row.get("instance_data")
        if not isinstance(instance_data, dict):
            instance_data = {}
        common = {
            "instance_id": instance_id,
            "object_ref": row.get("object_ref", ""),
            "class_ref": class_ref,
            "status": row.get("status", ""),
            "notes": row.get("notes", ""),
        }
        if "healthcheck" in class_ref:
            payload = dict(common)
            payload.update(
                {
                    "target_ref": instance_data.get("target_ref", ""),
                    "interval": instance_data.get("interval", ""),
                    "timeout": instance_data.get("timeout", ""),
                    "critical": instance_data.get("critical"),
                }
            )
            healthchecks.append(payload)
        elif "alert" in class_ref:
            payload = dict(common)
            payload.update(
                {
                    "severity": instance_data.get("severity", ""),
                    "channels": instance_data.get("channels", []),
                    "trigger": instance_data.get("trigger", {}),
                }
            )
            alerts.append(payload)

    for idx, row in enumerate(operation_rows):
        if not isinstance(row, dict):
            raise ProjectionError(f"compiled_json.instances.operations[{idx}] must be mapping/object")
        instance_id = row.get("instance_id")
        if not isinstance(instance_id, str) or not instance_id:
            raise ProjectionError(f"compiled_json.instances.operations[{idx}].instance_id must be non-empty string")
        instance_data = row.get("instance_data")
        if not isinstance(instance_data, dict):
            instance_data = {}
        backup_policies.append(
            {
                "instance_id": instance_id,
                "object_ref": row.get("object_ref", ""),
                "target_ref": instance_data.get("target_ref", ""),
                "data_asset_ref": instance_data.get("data_asset_ref", ""),
                "storage_ref": instance_data.get("storage_ref", ""),
                "schedule": instance_data.get("schedule", ""),
                "mode": instance_data.get("mode", ""),
                "status": row.get("status", ""),
                "notes": row.get("notes", ""),
            }
        )

    for idx, row in enumerate(service_rows):
        if not isinstance(row, dict):
            raise ProjectionError(f"compiled_json.instances.services[{idx}] must be mapping/object")
        instance_id = row.get("instance_id")
        if not isinstance(instance_id, str) or not instance_id:
            raise ProjectionError(f"compiled_json.instances.services[{idx}].instance_id must be non-empty string")
        class_ref = str(row.get("class_ref", ""))
        if "service.vpn" not in class_ref:
            continue
        instance_data = row.get("instance_data")
        if not isinstance(instance_data, dict):
            instance_data = {}
        vpn_services.append(
            {
                "instance_id": instance_id,
                "object_ref": row.get("object_ref", ""),
                "vpn_type": instance_data.get("vpn_type", ""),
                "trust_zone_ref": instance_data.get("trust_zone_ref", ""),
                "status": row.get("status", ""),
                "notes": row.get("notes", ""),
            }
        )

    for idx, row in enumerate(qos_rows):
        if not isinstance(row, dict):
            raise ProjectionError(f"compiled_json.instances.qos[{idx}] must be mapping/object")
        instance_id = row.get("instance_id")
        if not isinstance(instance_id, str) or not instance_id:
            raise ProjectionError(f"compiled_json.instances.qos[{idx}].instance_id must be non-empty string")
        instance_data = row.get("instance_data")
        if not isinstance(instance_data, dict):
            instance_data = {}
        qos_policies.append(
            {
                "instance_id": instance_id,
                "object_ref": row.get("object_ref", ""),
                "managed_by_ref": instance_data.get("managed_by_ref", ""),
                "interface": instance_data.get("interface", ""),
                "total_bandwidth": instance_data.get("total_bandwidth", {}),
                "device_limits": instance_data.get("device_limits", []),
                "status": row.get("status", ""),
                "notes": row.get("notes", ""),
            }
        )

    for idx, row in enumerate(power_rows):
        if not isinstance(row, dict):
            raise ProjectionError(f"compiled_json.instances.power[{idx}] must be mapping/object")
        instance_id = row.get("instance_id")
        if not isinstance(instance_id, str) or not instance_id:
            raise ProjectionError(f"compiled_json.instances.power[{idx}].instance_id must be non-empty string")
        class_ref = str(row.get("class_ref", ""))
        if "power.ups" not in class_ref:
            continue
        instance_data = row.get("instance_data")
        if not isinstance(instance_data, dict):
            instance_data = {}
        power_data = instance_data.get("power", {})
        if not isinstance(power_data, dict):
            power_data = {}
        ups_inventory.append(
            {
                "instance_id": instance_id,
                "object_ref": row.get("object_ref", ""),
                "external_source": power_data.get("external_source", ""),
                "max_watts": power_data.get("max_watts"),
                "status": row.get("status", ""),
                "notes": row.get("notes", ""),
            }
        )

    return {
        "healthchecks": _sorted_rows(healthchecks),
        "alerts": _sorted_rows(alerts),
        "backup_policies": _sorted_rows(backup_policies),
        "vpn_services": _sorted_rows(vpn_services),
        "qos_policies": _sorted_rows(qos_policies),
        "ups_inventory": _sorted_rows(ups_inventory),
        "counts": {
            "healthchecks": len(healthchecks),
            "alerts": len(alerts),
            "backup_policies": len(backup_policies),
            "vpn_services": len(vpn_services),
            "qos_policies": len(qos_policies),
            "ups_inventory": len(ups_inventory),
        },
    }
