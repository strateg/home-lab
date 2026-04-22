#!/usr/bin/env python3
"""Shared (cross-object) projection helpers for generator plugins."""

from __future__ import annotations

from copy import deepcopy
from collections import Counter
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


def _append_topology_node(
    nodes: list[dict[str, Any]],
    *,
    instance_id: Any,
    node_type: str,
    domain: str,
    layer: str,
    label: str | None = None,
) -> None:
    if not isinstance(instance_id, str) or not instance_id:
        return
    nodes.append(
        {
            "instance_id": instance_id,
            "safe_id": _safe_id(instance_id),
            "node_type": node_type,
            "domain": domain,
            "layer": layer,
            "label": label or instance_id,
        }
    )


def _append_topology_edge(
    edges: list[dict[str, Any]],
    *,
    source_id: Any,
    target_id: Any,
    edge_type: str,
    domain: str,
    layer: str,
) -> None:
    if not isinstance(source_id, str) or not source_id:
        return
    if not isinstance(target_id, str) or not target_id:
        return
    edges.append(
        {
            "source_id": source_id,
            "target_id": target_id,
            "source_safe_id": _safe_id(source_id),
            "target_safe_id": _safe_id(target_id),
            "edge_type": edge_type,
            "domain": domain,
            "layer": layer,
        }
    )


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

    docs_vms: list[dict[str, Any]] = []
    for idx, row in enumerate(vm):
        _require_non_empty_str(row, field="instance_id", path=f"compiled_json.instances.vm[{idx}]")
        object_ref = _require_object_ref(row, path=f"compiled_json.instances.vm[{idx}]")
        docs_vms.append(
            {
                "instance_id": row["instance_id"],
                "object_ref": object_ref,
                "class_ref": _resolved_class_ref(row),
                "status": row.get("status"),
                "layer": row.get("layer"),
                "host_ref": _get_instance_data(row, "instance_data.host_ref"),
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
        "vms": _sorted_rows(docs_vms),
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


def _collect_topology_nodes(
    diagram_projection: dict[str, Any],
    docs_projection: dict[str, Any],
) -> list[dict[str, Any]]:
    nodes: list[dict[str, Any]] = []

    for row in diagram_projection.get("devices", []):
        if not isinstance(row, dict):
            continue
        _append_topology_node(
            nodes,
            instance_id=row.get("instance_id"),
            node_type="device",
            domain="physical",
            layer=str(row.get("layer") or "L1"),
        )

    for row in diagram_projection.get("lxc", []):
        if not isinstance(row, dict):
            continue
        _append_topology_node(
            nodes,
            instance_id=row.get("instance_id"),
            node_type="lxc",
            domain="physical",
            layer=str(row.get("layer") or "L1"),
        )

    for row in docs_projection.get("vms", []):
        if not isinstance(row, dict):
            continue
        _append_topology_node(
            nodes,
            instance_id=row.get("instance_id"),
            node_type="vm",
            domain="physical",
            layer=str(row.get("layer") or "L1"),
        )

    for row in docs_projection.get("services", []):
        if not isinstance(row, dict):
            continue
        _append_topology_node(
            nodes,
            instance_id=row.get("instance_id"),
            node_type="service",
            domain="services",
            layer=str(row.get("layer") or "L4"),
        )

    for collection, node_type in (
        ("trust_zones", "trust_zone"),
        ("vlans", "vlan"),
        ("bridges", "bridge"),
    ):
        for row in diagram_projection.get(collection, []):
            if not isinstance(row, dict):
                continue
            _append_topology_node(
                nodes,
                instance_id=row.get("instance_id"),
                node_type=node_type,
                domain="network",
                layer="L2",
            )

    storage_projection = docs_projection.get("storage", {})
    if not isinstance(storage_projection, dict):
        storage_projection = {}
    for row in storage_projection.get("storage_pools", []):
        if not isinstance(row, dict):
            continue
        _append_topology_node(
            nodes,
            instance_id=row.get("instance_id"),
            node_type="storage_pool",
            domain="storage",
            layer="L3",
        )
    for row in storage_projection.get("data_assets", []):
        if not isinstance(row, dict):
            continue
        _append_topology_node(
            nodes,
            instance_id=row.get("instance_id"),
            node_type="data_asset",
            domain="storage",
            layer="L3",
        )

    operations_projection = docs_projection.get("operations", {})
    if not isinstance(operations_projection, dict):
        operations_projection = {}
    for collection, node_type in (
        ("backup_policies", "backup_policy"),
        ("healthchecks", "healthcheck"),
        ("alerts", "alert"),
        ("vpn_services", "vpn_service"),
        ("qos_policies", "qos_policy"),
        ("ups_inventory", "ups_device"),
    ):
        for row in operations_projection.get(collection, []):
            if not isinstance(row, dict):
                continue
            _append_topology_node(
                nodes,
                instance_id=row.get("instance_id"),
                node_type=node_type,
                domain="operations",
                layer="L6",
            )
    return nodes


def _extract_host_dependencies(
    diagram_projection: dict[str, Any],
    docs_projection: dict[str, Any],
) -> list[dict[str, Any]]:
    edges: list[dict[str, Any]] = []
    for row in diagram_projection.get("lxc", []):
        if not isinstance(row, dict):
            continue
        _append_topology_edge(
            edges,
            source_id=row.get("instance_id"),
            target_id=row.get("host_ref"),
            edge_type="hosted_on",
            domain="physical",
            layer="L1",
        )

    for row in docs_projection.get("vms", []):
        if not isinstance(row, dict):
            continue
        _append_topology_edge(
            edges,
            source_id=row.get("instance_id"),
            target_id=row.get("host_ref"),
            edge_type="hosted_on",
            domain="physical",
            layer="L1",
        )

    network_projection = docs_projection.get("network", {})
    if not isinstance(network_projection, dict):
        network_projection = {}
    for row in network_projection.get("bridges", []):
        if not isinstance(row, dict):
            continue
        _append_topology_edge(
            edges,
            source_id=row.get("instance_id"),
            target_id=row.get("host_ref"),
            edge_type="hosted_on",
            domain="network",
            layer="L2",
        )

    storage_projection = docs_projection.get("storage", {})
    if not isinstance(storage_projection, dict):
        storage_projection = {}
    for collection in ("storage_pools", "data_assets"):
        for row in storage_projection.get(collection, []):
            if not isinstance(row, dict):
                continue
            _append_topology_edge(
                edges,
                source_id=row.get("instance_id"),
                target_id=row.get("host_ref"),
                edge_type="hosted_on",
                domain="storage",
                layer="L3",
            )
    return edges


def _extract_service_dependencies(docs_projection: dict[str, Any]) -> list[dict[str, Any]]:
    edges: list[dict[str, Any]] = []
    for row in docs_projection.get("services", []):
        if not isinstance(row, dict):
            continue
        service_id = row.get("instance_id")
        _append_topology_edge(
            edges,
            source_id=service_id,
            target_id=row.get("runtime_target_ref"),
            edge_type="runtime_target",
            domain="services",
            layer="L4",
        )
        _append_topology_edge(
            edges,
            source_id=service_id,
            target_id=row.get("runtime_network_ref"),
            edge_type="runtime_network_binding",
            domain="services",
            layer="L4",
        )

    for row in docs_projection.get("service_dependencies", []):
        if not isinstance(row, dict):
            continue
        _append_topology_edge(
            edges,
            source_id=row.get("service_id"),
            target_id=row.get("depends_on"),
            edge_type="service_dependency",
            domain="services",
            layer="L7",
        )
    return edges


def _extract_network_dependencies(docs_projection: dict[str, Any]) -> list[dict[str, Any]]:
    edges: list[dict[str, Any]] = []
    network_projection = docs_projection.get("network", {})
    if not isinstance(network_projection, dict):
        network_projection = {}
    for row in network_projection.get("networks", []):
        if not isinstance(row, dict):
            continue
        _append_topology_edge(
            edges,
            source_id=row.get("instance_id"),
            target_id=row.get("managed_by_ref"),
            edge_type="managed_by",
            domain="network",
            layer="L2",
        )
        _append_topology_edge(
            edges,
            source_id=row.get("instance_id"),
            target_id=row.get("trust_zone_ref"),
            edge_type="trust_zone_member",
            domain="network",
            layer="L2",
        )
    return edges


def _extract_data_link_dependencies(diagram_projection: dict[str, Any]) -> list[dict[str, Any]]:
    edges: list[dict[str, Any]] = []
    for row in diagram_projection.get("data_links", []):
        if not isinstance(row, dict):
            continue
        endpoint_a = row.get("endpoint_a")
        endpoint_b = row.get("endpoint_b")
        source_id = endpoint_a.get("device_ref") if isinstance(endpoint_a, dict) else None
        target_id = endpoint_b.get("device_ref") if isinstance(endpoint_b, dict) else None
        if not isinstance(source_id, str) or not source_id:
            source_id = endpoint_a.get("external_ref") if isinstance(endpoint_a, dict) else None
        if not isinstance(target_id, str) or not target_id:
            target_id = endpoint_b.get("external_ref") if isinstance(endpoint_b, dict) else None
        _append_topology_edge(
            edges,
            source_id=source_id,
            target_id=target_id,
            edge_type="data_link",
            domain="physical",
            layer="L1",
        )
    return edges


def _extract_storage_dependencies(docs_projection: dict[str, Any]) -> list[dict[str, Any]]:
    edges: list[dict[str, Any]] = []
    storage_projection = docs_projection.get("storage", {})
    if not isinstance(storage_projection, dict):
        storage_projection = {}
    for row in storage_projection.get("mount_chains", []):
        if not isinstance(row, dict):
            continue
        _append_topology_edge(
            edges,
            source_id=row.get("target_ref"),
            target_id=row.get("storage_ref"),
            edge_type="uses_storage",
            domain="storage",
            layer="L3",
        )
        _append_topology_edge(
            edges,
            source_id=row.get("data_asset_ref"),
            target_id=row.get("storage_ref"),
            edge_type="stored_in",
            domain="storage",
            layer="L3",
        )
    return edges


def _extract_operations_dependencies(docs_projection: dict[str, Any]) -> list[dict[str, Any]]:
    edges: list[dict[str, Any]] = []
    operations_projection = docs_projection.get("operations", {})
    if not isinstance(operations_projection, dict):
        operations_projection = {}
    for row in operations_projection.get("backup_policies", []):
        if not isinstance(row, dict):
            continue
        policy_id = row.get("instance_id")
        _append_topology_edge(
            edges,
            source_id=policy_id,
            target_id=row.get("target_ref"),
            edge_type="backs_up_target",
            domain="operations",
            layer="L6",
        )
        _append_topology_edge(
            edges,
            source_id=policy_id,
            target_id=row.get("data_asset_ref"),
            edge_type="backs_up_data_asset",
            domain="operations",
            layer="L6",
        )
        _append_topology_edge(
            edges,
            source_id=policy_id,
            target_id=row.get("storage_ref"),
            edge_type="writes_to_storage",
            domain="operations",
            layer="L6",
        )
    return edges


def _materialize_missing_edge_endpoint_nodes(
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
) -> None:
    """Ensure edge endpoints always exist as nodes (external refs become synthetic nodes)."""
    known_ids = {
        row.get("instance_id")
        for row in nodes
        if isinstance(row, dict) and isinstance(row.get("instance_id"), str) and row.get("instance_id")
    }
    for edge in edges:
        if not isinstance(edge, dict):
            continue
        for endpoint_key in ("source_id", "target_id"):
            endpoint_id = edge.get(endpoint_key)
            if not isinstance(endpoint_id, str) or not endpoint_id or endpoint_id in known_ids:
                continue
            nodes.append(
                {
                    "instance_id": endpoint_id,
                    "safe_id": _safe_id(endpoint_id),
                    "node_type": "external_ref",
                    "domain": str(edge.get("domain") or "physical"),
                    "layer": str(edge.get("layer") or "L1"),
                    "label": endpoint_id,
                }
            )
            known_ids.add(endpoint_id)


def build_topology_projection(compiled_json: dict[str, Any]) -> dict[str, Any]:
    """Build unified topology graph projection with cross-domain nodes and dependencies."""
    diagram_projection = build_diagram_projection(compiled_json)
    docs_projection = build_docs_projection(compiled_json)
    nodes = _collect_topology_nodes(diagram_projection, docs_projection)
    edges: list[dict[str, Any]] = []
    edges.extend(_extract_host_dependencies(diagram_projection, docs_projection))
    edges.extend(_extract_service_dependencies(docs_projection))
    edges.extend(_extract_network_dependencies(docs_projection))
    edges.extend(_extract_data_link_dependencies(diagram_projection))
    edges.extend(_extract_storage_dependencies(docs_projection))
    edges.extend(_extract_operations_dependencies(docs_projection))
    _materialize_missing_edge_endpoint_nodes(nodes, edges)

    unique_nodes: dict[str, dict[str, Any]] = {}
    for row in nodes:
        instance_id = row.get("instance_id")
        if isinstance(instance_id, str) and instance_id and instance_id not in unique_nodes:
            unique_nodes[instance_id] = row

    deduped_edges: dict[tuple[str, str, str], dict[str, Any]] = {}
    for row in edges:
        source_id = row.get("source_id")
        target_id = row.get("target_id")
        edge_type = row.get("edge_type")
        if not isinstance(source_id, str) or not isinstance(target_id, str) or not isinstance(edge_type, str):
            continue
        key = (source_id, target_id, edge_type)
        if key not in deduped_edges:
            deduped_edges[key] = row

    sorted_nodes = sorted(
        unique_nodes.values(),
        key=lambda row: (str(row.get("domain", "")), str(row.get("layer", "")), str(row.get("instance_id", ""))),
    )
    sorted_edges = sorted(
        deduped_edges.values(),
        key=lambda row: (
            str(row.get("domain", "")),
            str(row.get("layer", "")),
            str(row.get("source_id", "")),
            str(row.get("target_id", "")),
            str(row.get("edge_type", "")),
        ),
    )

    node_domains = sorted({str(row.get("domain", "")) for row in sorted_nodes if row.get("domain")})
    node_layers = sorted({str(row.get("layer", "")) for row in sorted_nodes if row.get("layer")})
    node_type_counts = dict(
        sorted(
            Counter(str(row.get("node_type", "")) for row in sorted_nodes if row.get("node_type")).items(),
            key=lambda item: item[0],
        )
    )
    edge_type_counts = dict(
        sorted(
            Counter(str(row.get("edge_type", "")) for row in sorted_edges if row.get("edge_type")).items(),
            key=lambda item: item[0],
        )
    )
    domain_counts = dict(
        sorted(
            Counter(str(row.get("domain", "")) for row in sorted_nodes if row.get("domain")).items(),
            key=lambda item: item[0],
        )
    )
    layer_counts = dict(
        sorted(
            Counter(str(row.get("layer", "")) for row in sorted_nodes if row.get("layer")).items(),
            key=lambda item: item[0],
        )
    )

    return {
        "nodes": sorted_nodes,
        "edges": sorted_edges,
        "metadata": {
            "total_nodes": len(sorted_nodes),
            "total_edges": len(sorted_edges),
            "available_domains": node_domains,
            "available_layers": node_layers,
            "node_type_counts": node_type_counts,
            "edge_type_counts": edge_type_counts,
            "domain_counts": domain_counts,
            "layer_counts": layer_counts,
        },
        "counts": {
            "nodes": len(sorted_nodes),
            "edges": len(sorted_edges),
        },
    }
