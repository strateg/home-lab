"""Diagram domain projection for the Mermaid diagram generator (ADR 0005 / ADR 0027 / ADR 0112)."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from plugins.generators.projection_core import (
    GROUP_DEVICES,
    GROUP_LXC,
    GROUP_NETWORK,
    GROUP_SERVICES,
    _get_instance_data,
    _group_rows,
    _instance_groups,
    _resolved_class_ref,
    _resolved_object_ref,
    _sorted_rows,
)
from plugins.generators.projections.mermaid import (
    _ICONS,
    _ZONE_CLASS_COLOUR,
    _ZONE_CLASS_DEFAULT,
    _icon_for_class,
    _safe_id,
    _zone_label,
)


def build_diagram_projection(compiled_json: dict[str, Any]) -> dict[str, Any]:
    """Build stable projection for diagram generator (ADR 0005 / ADR 0027).

    Returns:
        devices: L1 device rows with icon and safe_id fields added.
        trust_zones: L2 trust zone rows with icon, colour, label.
        vlans: L2 VLAN rows.
        bridges: L2 bridge rows.
        data_links: L1 physical/data link rows.
        services: L4/L5 service rows.
        lxc: LXC container rows.
        counts: summary counts.
    """
    groups = _instance_groups(compiled_json)
    raw_devices = _group_rows(groups, canonical=GROUP_DEVICES)
    raw_network = _group_rows(groups, canonical=GROUP_NETWORK)
    raw_data_channels = _group_rows(groups, canonical="data-channels")
    raw_physical_links = _group_rows(groups, canonical="physical-links")
    raw_services = _group_rows(groups, canonical=GROUP_SERVICES)
    raw_lxc = _group_rows(groups, canonical=GROUP_LXC)

    # --- Devices (L1) ---
    devices: list[dict[str, Any]] = []
    for row in raw_devices:
        inst_id = row.get("instance_id", "")
        class_ref = _resolved_class_ref(row)
        obj_ref = _resolved_object_ref(row)
        # Derive short label from instance_id: "rtr-slate" → "rtr-slate"
        # Remove common "inst." prefix if present
        label = inst_id.removeprefix("inst.").replace(".", " ")
        entry = {
            "instance_id": inst_id,
            "safe_id": _safe_id(inst_id),
            "class_ref": class_ref,
            "object_ref": obj_ref,
            "layer": row.get("layer", ""),
            "status": row.get("status", ""),
            "notes": row.get("notes", ""),
            "label": label,
            "icon": _icon_for_class(class_ref, fallback="mdi:devices"),
            "host_ref": _get_instance_data(row, "instance_data.host_ref"),
            "instance_data": deepcopy(row.get("instance_data") or {}),
        }
        devices.append(entry)

    # --- Network layer: split by class_ref ---
    trust_zones: list[dict[str, Any]] = []
    vlans: list[dict[str, Any]] = []
    bridges: list[dict[str, Any]] = []
    data_links: list[dict[str, Any]] = []

    for row in raw_network:
        inst_id = row.get("instance_id", "")
        class_ref = _resolved_class_ref(row)

        if "trust_zone" in class_ref:
            idata = row.get("instance_data") or {}
            fw_refs = idata.get("firewall_policy_refs", [])
            if not isinstance(fw_refs, list):
                fw_refs = []
            zone_name = _zone_label(inst_id)
            zone_key = zone_name.lower()
            trust_zones.append(
                {
                    "instance_id": inst_id,
                    "safe_id": _safe_id(inst_id),
                    "class_ref": class_ref,
                    "object_ref": _resolved_object_ref(row),
                    "label": zone_name,
                    "icon": _ICONS.icon_for_zone(inst_id),
                    "colour": _ZONE_CLASS_COLOUR.get(zone_key, _ZONE_CLASS_DEFAULT),
                    "notes": row.get("notes", ""),
                    "status": row.get("status", ""),
                    "firewall_policy_refs": [str(item) for item in fw_refs if isinstance(item, str)],
                }
            )
        elif "vlan" in class_ref:
            idata = row.get("instance_data") or {}
            fw_refs = idata.get("firewall_policy_refs", [])
            if not isinstance(fw_refs, list):
                fw_refs = []
            vlans.append(
                {
                    "instance_id": inst_id,
                    "safe_id": _safe_id(inst_id),
                    "class_ref": class_ref,
                    "object_ref": _resolved_object_ref(row),
                    "label": inst_id.removeprefix("inst.").replace(".", " "),
                    "vlan_id": idata.get("vlan_id"),
                    "cidr": idata.get("cidr", ""),
                    "gateway": idata.get("gateway", ""),
                    "trust_zone_ref": idata.get("trust_zone_ref", ""),
                    "firewall_policy_refs": [str(item) for item in fw_refs if isinstance(item, str)],
                    "notes": row.get("notes", ""),
                    "icon": "mdi:lan",
                    "status": row.get("status", ""),
                }
            )
        elif "bridge" in class_ref:
            idata = row.get("instance_data") or {}
            bridges.append(
                {
                    "instance_id": inst_id,
                    "safe_id": _safe_id(inst_id),
                    "class_ref": class_ref,
                    "label": inst_id.removeprefix("inst.").replace(".", " "),
                    "host_ref": idata.get("host_ref", ""),
                    "notes": row.get("notes", ""),
                    "icon": "mdi:bridge",
                    "status": row.get("status", ""),
                }
            )
        elif "physical_link" in class_ref or "data_link" in class_ref or "ethernet" in class_ref:
            idata = row.get("instance_data") or {}
            data_links.append(
                {
                    "instance_id": inst_id,
                    "safe_id": _safe_id(inst_id),
                    "class_ref": class_ref,
                    "endpoint_a": idata.get("endpoint_a", {}),
                    "endpoint_b": idata.get("endpoint_b", {}),
                    "medium": idata.get("medium", "ethernet"),
                    "speed_mbps": idata.get("speed_mbps"),
                    "notes": row.get("notes", ""),
                    "status": row.get("status", ""),
                }
            )

    # Data channels / physical links may be modeled in dedicated groups.
    for row in [*raw_data_channels, *raw_physical_links]:
        inst_id = row.get("instance_id", "")
        class_ref = _resolved_class_ref(row)
        object_ref = _resolved_object_ref(row)
        idata = row.get("instance_data") or {}
        if not isinstance(idata, dict):
            idata = {}

        medium = idata.get("medium")
        if not isinstance(medium, str) or not medium:
            medium_source = f"{class_ref} {object_ref}".lower()
            if "wifi" in medium_source:
                medium = "wifi"
            elif "lte" in medium_source:
                medium = "lte"
            elif "ethernet" in medium_source or "physical_link" in medium_source:
                medium = "ethernet"
            elif "wan_uplink" in medium_source or ".wan" in medium_source:
                medium = "wan"
            else:
                medium = "link"

        speed_mbps = idata.get("speed_mbps")
        if not isinstance(speed_mbps, (int, float)):
            speed_mbps = idata.get("negotiated_speed_mbps")
        if not isinstance(speed_mbps, (int, float)):
            speed_mbps = idata.get("max_speed_mbps")

        data_links.append(
            {
                "instance_id": inst_id,
                "safe_id": _safe_id(inst_id),
                "class_ref": class_ref,
                "endpoint_a": idata.get("endpoint_a", {}),
                "endpoint_b": idata.get("endpoint_b", {}),
                "medium": medium,
                "speed_mbps": speed_mbps,
                "notes": row.get("notes", ""),
                "status": row.get("status", ""),
            }
        )

    # --- Services (L4/L5) ---
    services: list[dict[str, Any]] = []
    for row in raw_services:
        inst_id = row.get("instance_id", "")
        class_ref = _resolved_class_ref(row)
        runtime = row.get("runtime")
        if not isinstance(runtime, dict):
            runtime = _get_instance_data(row, "instance_data.runtime", {})
        services.append(
            {
                "instance_id": inst_id,
                "safe_id": _safe_id(inst_id),
                "class_ref": class_ref,
                "object_ref": _resolved_object_ref(row),
                "label": inst_id.removeprefix("inst.").replace(".", " "),
                "layer": row.get("layer", ""),
                "status": row.get("status", ""),
                "icon": _ICONS.icon_for_service(class_ref, fallback="mdi:cog"),
                "host_ref": _get_instance_data(row, "instance_data.host_ref"),
                "runtime_type": runtime.get("type", "") if isinstance(runtime, dict) else "",
                "runtime_target_ref": runtime.get("target_ref", "") if isinstance(runtime, dict) else "",
            }
        )

    # --- LXC ---
    lxc: list[dict[str, Any]] = []
    for row in raw_lxc:
        inst_id = row.get("instance_id", "")
        class_ref = _resolved_class_ref(row)
        idata = row.get("instance_data") or {}
        lxc.append(
            {
                "instance_id": inst_id,
                "safe_id": _safe_id(inst_id),
                "class_ref": class_ref,
                "object_ref": _resolved_object_ref(row),
                "label": idata.get("hostname", inst_id.removeprefix("inst.lxc.").replace(".", "-")),
                "layer": row.get("layer", ""),
                "status": row.get("status", ""),
                "icon": "mdi:cube-outline",
                "host_ref": idata.get("host_ref", ""),
                "trust_zone_ref": idata.get("trust_zone_ref", ""),
            }
        )

    counts = {
        "devices": len(devices),
        "trust_zones": len(trust_zones),
        "vlans": len(vlans),
        "bridges": len(bridges),
        "data_links": len(data_links),
        "services": len(services),
        "lxc": len(lxc),
    }

    return {
        "devices": _sorted_rows(devices),
        "trust_zones": sorted(trust_zones, key=lambda r: r["instance_id"]),
        "vlans": sorted(vlans, key=lambda r: (r.get("vlan_id") or 0, r["instance_id"])),
        "bridges": sorted(bridges, key=lambda r: r["instance_id"]),
        "data_links": sorted(data_links, key=lambda r: r["instance_id"]),
        "services": _sorted_rows(services),
        "lxc": _sorted_rows(lxc),
        "counts": counts,
    }
