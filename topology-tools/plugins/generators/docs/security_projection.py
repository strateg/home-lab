"""Security domain projection for docs generator (ADR0079 Phase C)."""

from __future__ import annotations

from typing import Any

from plugins.generators.projection_core import GROUP_NETWORK, ProjectionError, _group_rows, _instance_groups, _sorted_rows


def build_security_projection(compiled_json: dict[str, Any]) -> dict[str, Any]:
    """Build deterministic trust-zone/VLAN/firewall documentation view."""
    groups = _instance_groups(compiled_json)
    network_rows = _group_rows(groups, canonical=GROUP_NETWORK)
    firewall_rows = groups.get("firewall", [])

    trust_zones: list[dict[str, Any]] = []
    vlans: list[dict[str, Any]] = []
    zone_network_bindings: dict[str, list[str]] = {}

    for idx, row in enumerate(network_rows):
        instance_id = row.get("instance_id")
        if not isinstance(instance_id, str) or not instance_id:
            raise ProjectionError(f"compiled_json.instances.network[{idx}].instance_id must be non-empty string")
        class_ref = str(row.get("class_ref", ""))
        if "trust_zone" in class_ref:
            trust_zones.append(
                {
                    "instance_id": instance_id,
                    "object_ref": row.get("object_ref", ""),
                    "status": row.get("status", ""),
                    "notes": row.get("notes", ""),
                }
            )
            zone_network_bindings.setdefault(instance_id, [])
            continue
        if "vlan" not in class_ref:
            continue
        instance_data = row.get("instance_data")
        if not isinstance(instance_data, dict):
            instance_data = {}
        trust_zone_ref = str(instance_data.get("trust_zone_ref", "") or "")
        vlans.append(
            {
                "instance_id": instance_id,
                "object_ref": row.get("object_ref", ""),
                "trust_zone_ref": trust_zone_ref,
                "managed_by_ref": instance_data.get("managed_by_ref", ""),
                "dhcp_range": instance_data.get("dhcp_range", ""),
                "status": row.get("status", ""),
                "notes": row.get("notes", ""),
            }
        )
        if trust_zone_ref:
            zone_network_bindings.setdefault(trust_zone_ref, []).append(instance_id)

    firewall_policies: list[dict[str, Any]] = []
    for idx, row in enumerate(firewall_rows):
        if not isinstance(row, dict):
            raise ProjectionError(f"compiled_json.instances.firewall[{idx}] must be mapping/object")
        instance_id = row.get("instance_id")
        if not isinstance(instance_id, str) or not instance_id:
            raise ProjectionError(f"compiled_json.instances.firewall[{idx}].instance_id must be non-empty string")
        instance_data = row.get("instance_data")
        if not isinstance(instance_data, dict):
            instance_data = {}
        firewall_policies.append(
            {
                "instance_id": instance_id,
                "object_ref": row.get("object_ref", ""),
                "chain": instance_data.get("chain", ""),
                "managed_by_ref": instance_data.get("managed_by_ref", ""),
                "status": row.get("status", ""),
                "notes": row.get("notes", ""),
            }
        )

    normalized_bindings = {
        zone: sorted(values)
        for zone, values in sorted(zone_network_bindings.items(), key=lambda item: item[0])
    }
    return {
        "trust_zones": _sorted_rows(trust_zones),
        "vlans": _sorted_rows(vlans),
        "firewall_policies": _sorted_rows(firewall_policies),
        "zone_network_bindings": normalized_bindings,
        "counts": {
            "trust_zones": len(trust_zones),
            "vlans": len(vlans),
            "firewall_policies": len(firewall_policies),
        },
    }
