#!/usr/bin/env python3
"""Shared (cross-object) projection helpers for generator plugins."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from plugins.generators.docs.network_projection import build_network_projection
from plugins.generators.docs.operations_projection import build_operations_projection
from plugins.generators.docs.physical_projection import build_physical_projection
from plugins.generators.docs.security_projection import build_security_projection
from plugins.generators.docs.storage_projection import build_storage_projection
from plugins.generators.projection_core import (  # ADR0078 WP-006: Group canonical name constants
    GROUP_DEVICES,
    GROUP_LXC,
    GROUP_NETWORK,
    GROUP_SERVICES,
    GROUP_VM,
    ProjectionError,
    _get_instance_data,
    _group_rows,
    _instance_groups,
    _is_ansible_host_candidate,
    _require_non_empty_str,
    _require_object_ref,
    _resolved_class_ref,
    _resolved_object_ref,
    _sorted_rows,
)
from plugins.icons.icon_manager import IconManager

_ICONS = IconManager()

# Trust zone colour palette for Mermaid classDef
_ZONE_CLASS_COLOUR: dict[str, str] = {
    "untrusted": "fill:#ff6b6b,stroke:#c92a2a,color:#fff",
    "user": "fill:#74c0fc,stroke:#1864ab,color:#000",
    "servers": "fill:#51cf66,stroke:#2b8a3e,color:#000",
    "management": "fill:#da77f2,stroke:#9c36b5,color:#fff",
    "guest": "fill:#ffd43b,stroke:#fab005,color:#000",
    "iot": "fill:#ffd43b,stroke:#fab005,color:#000",
}
_ZONE_CLASS_DEFAULT = "fill:#e9ecef,stroke:#868e96,color:#000"


def _icon_for_class(class_ref: str, *, fallback: str = "mdi:devices") -> str:
    """Return the best matching Mermaid icon for a class_ref."""
    return _ICONS.icon_for_class(class_ref, fallback=fallback)


def _zone_label(instance_id: str) -> str:
    """Extract human-readable zone name from instance_id like inst.trust_zone.servers."""
    parts = instance_id.rsplit(".", 1)
    return parts[-1].replace("_", " ").title() if parts else instance_id


def _safe_id(value: str) -> str:
    """Make a string safe for use as a Mermaid node ID.

    Replaces characters that are not alphanumeric or underscore.
    Mermaid node IDs should contain only: a-z A-Z 0-9 _

    Transformations:
    - '.' → '_'  (dot to underscore)
    - '-' → '_'  (dash to underscore)
    - '@' → '_'  (at-sign to underscore, for service@host notation)
    """
    return value.replace(".", "_").replace("-", "_").replace("@", "_")


def build_ansible_projection(compiled_json: dict[str, Any]) -> dict[str, Any]:
    """Build stable view for Ansible inventory generator."""
    groups = _instance_groups(compiled_json)
    devices = _group_rows(groups, canonical=GROUP_DEVICES)
    lxc = _group_rows(groups, canonical=GROUP_LXC)

    hosts: list[dict[str, Any]] = []
    for idx, row in enumerate(devices):
        _require_non_empty_str(row, field="instance_id", path=f"compiled_json.instances.devices[{idx}]")
        _require_object_ref(row, path=f"compiled_json.instances.devices[{idx}]")
        if not _is_ansible_host_candidate(row):
            continue
        host = deepcopy(row)
        host.pop("instance", None)
        host["inventory_group"] = "devices"
        hosts.append(host)
    for idx, row in enumerate(lxc):
        _require_non_empty_str(row, field="instance_id", path=f"compiled_json.instances.lxc[{idx}]")
        _require_object_ref(row, path=f"compiled_json.instances.lxc[{idx}]")
        host = deepcopy(row)
        host.pop("instance", None)
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
    vm = _group_rows(groups, canonical=GROUP_VM)
    networks = _group_rows(groups, canonical=GROUP_NETWORK)

    docs_devices: list[dict[str, Any]] = []
    for idx, row in enumerate(devices):
        _require_non_empty_str(row, field="instance_id", path=f"compiled_json.instances.devices[{idx}]")
        object_ref = _require_object_ref(row, path=f"compiled_json.instances.devices[{idx}]")
        docs_devices.append(
            {
                "instance_id": row["instance_id"],
                "object_ref": object_ref,
                "class_ref": _resolved_class_ref(row),
                "status": row.get("status"),
                "layer": row.get("layer"),
            }
        )

    docs_services: list[dict[str, Any]] = []
    for idx, row in enumerate(services):
        _require_non_empty_str(row, field="instance_id", path=f"compiled_json.instances.services[{idx}]")
        object_ref = _require_object_ref(row, path=f"compiled_json.instances.services[{idx}]")
        runtime = row.get("runtime")
        if not isinstance(runtime, dict):
            runtime = _get_instance_data(row, "instance_data.runtime", {})
        runtime_type = runtime.get("type") if isinstance(runtime, dict) else None
        runtime_target = runtime.get("target_ref") if isinstance(runtime, dict) else None
        runtime_network = runtime.get("network_binding_ref") if isinstance(runtime, dict) else None
        docs_services.append(
            {
                "instance_id": row["instance_id"],
                "object_ref": object_ref,
                "class_ref": _resolved_class_ref(row),
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
        "vms": len(vm),
        "networks": len(networks),
        "groups": len(groups),
    }

    service_dependencies: list[dict[str, Any]] = []
    for row in services:
        instance_id = row.get("instance_id")
        if not isinstance(instance_id, str) or not instance_id:
            continue
        instance_data = row.get("instance_data")
        if not isinstance(instance_data, dict):
            instance_data = {}
        raw_dependencies = instance_data.get("dependencies")
        if not isinstance(raw_dependencies, list):
            continue
        for dep in raw_dependencies:
            if isinstance(dep, dict):
                target = dep.get("service_ref")
            elif isinstance(dep, str):
                target = dep
            else:
                target = None
            if isinstance(target, str) and target:
                service_dependencies.append({
                    "service_id": instance_id,
                    "service_safe_id": _safe_id(instance_id),
                    "depends_on": target,
                    "depends_on_safe_id": _safe_id(target),
                })

    service_dependencies = sorted(
        service_dependencies,
        key=lambda row: (str(row.get("service_id", "")), str(row.get("depends_on", ""))),
    )

    network_projection = build_network_projection(compiled_json)
    physical_projection = build_physical_projection(compiled_json)
    security_projection = build_security_projection(compiled_json)
    storage_projection = build_storage_projection(compiled_json)
    operations_projection = build_operations_projection(compiled_json)

    return {
        "counts": counts,
        "devices": _sorted_rows(docs_devices),
        "services": _sorted_rows(docs_services),
        "groups": {name: len(rows) for name, rows in sorted(groups.items(), key=lambda item: item[0])},
        "service_dependencies": service_dependencies,
        "network": network_projection,
        "physical": physical_projection,
        "security": security_projection,
        "storage": storage_projection,
        "operations": operations_projection,
    }


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
