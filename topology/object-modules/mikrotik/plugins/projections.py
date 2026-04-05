#!/usr/bin/env python3
"""MikroTik-owned projection helpers for object generators."""

from __future__ import annotations

from typing import Any

from plugins.generators.projection_core import (  # ADR0078 WP-006: Group canonical name constants
    GROUP_DEVICES,
    GROUP_NETWORK,
    GROUP_SERVICES,
    ProjectionError,
    _group_rows,
    _instance_groups,
    _require_object_ref,
    _require_non_empty_str,
    _resolved_object_ref,
    _sorted_rows,
)


def _extract_capabilities(row: dict[str, Any]) -> set[str]:
    """Extract capability IDs from instance row including object capabilities."""
    caps: set[str] = set()

    # Instance-level capabilities
    instance_data = row.get("instance", {}) or {}
    for field_name in ("capabilities", "derived_capabilities", "enabled_capabilities"):
        raw_caps = instance_data.get(field_name)
        if isinstance(raw_caps, list):
            for cap in raw_caps:
                if isinstance(cap, str) and cap:
                    caps.add(cap)

    # Object-level capabilities (from object definition)
    obj_data = row.get("object", {}) or {}
    for field_name in ("enabled_capabilities", "derived_capabilities", "vendor_capabilities"):
        raw_caps = obj_data.get(field_name)
        if isinstance(raw_caps, list):
            for cap in raw_caps:
                if isinstance(cap, str) and cap:
                    caps.add(cap)

    # Root-level capabilities (legacy compatibility)
    for field_name in ("capabilities", "derived_capabilities", "enabled_capabilities"):
        raw_caps = row.get(field_name)
        if isinstance(raw_caps, list):
            for cap in raw_caps:
                if isinstance(cap, str) and cap:
                    caps.add(cap)

    return caps


def _derive_mikrotik_capability_flags(routers: list[dict[str, Any]]) -> dict[str, bool]:
    """Derive boolean capability flags for conditional Terraform generation.

    ADR0078: Capabilities must come from object definitions, not hardcoded model checks.
    """
    all_caps: set[str] = set()
    for router in routers:
        all_caps.update(_extract_capabilities(router))

    return {
        "has_wireguard": any(cap.startswith("cap.net.overlay.vpn.wireguard") for cap in all_caps),
        "has_openvpn": any(cap.startswith("cap.net.overlay.vpn.openvpn") for cap in all_caps),
        "has_ipsec": "cap.net.overlay.vpn.ipsec" in all_caps,
        "has_containers": "cap.net.platform.containers" in all_caps,
        "has_qos_basic": "cap.net.l3.qos.basic" in all_caps,
        "has_qos_advanced": "cap.net.l3.qos.advanced" in all_caps,
        "has_lte": "cap.net.interface.lte" in all_caps,
        "has_wifi": "cap.net.interface.wifi" in all_caps,
        "has_vlan": "cap.net.l2.segmentation.vlan.8021q" in all_caps,
        "has_multi_wan": "cap.net.l3.uplink.multi_uplink" in all_caps,
        "has_failover": "cap.net.l3.uplink.failover" in all_caps,
    }


def _load_object_properties(object_ref: str) -> dict[str, Any]:
    """Load properties from object module YAML file."""
    from pathlib import Path
    import yaml

    # Determine repo root from this file's location
    this_file = Path(__file__).resolve()
    # This file is at topology/object-modules/mikrotik/plugins/projections.py
    # Object modules are at topology/object-modules/<domain>/obj.<domain>.<name>.yaml
    object_modules_root = this_file.parents[2]

    # Parse object_ref: obj.network.vlan.servers -> network/obj.network.vlan.servers.yaml
    parts = object_ref.split(".")
    if len(parts) < 3:
        return {}

    domain = parts[1]  # e.g., "network"
    object_file = object_modules_root / domain / f"{object_ref}.yaml"

    if not object_file.exists():
        return {}

    try:
        payload = yaml.safe_load(object_file.read_text(encoding="utf-8")) or {}
        return payload.get("properties", {}) or {}
    except Exception:
        return {}


def _build_vlan_entry(row: dict[str, Any]) -> dict[str, Any]:
    """Extract VLAN configuration from network row."""
    object_ref = _resolved_object_ref(row)
    inst_data = row.get("instance_data", {}) or {}

    # Load properties from object module file
    props = _load_object_properties(object_ref)

    return {
        "instance_id": row.get("instance_id", ""),
        "name": row.get("instance_id", "").replace("inst.vlan.", "").replace(".", "_"),
        "vlan_id": props.get("vlan_id"),
        "cidr": props.get("cidr"),
        "gateway": props.get("gateway"),
        "mtu": props.get("mtu", 1500),
        "dhcp_enabled": props.get("dhcp_enabled", False),
        "dhcp_range": inst_data.get("dhcp_range"),
        "dns_servers": props.get("dns_servers", []),
        "managed_by_ref": inst_data.get("managed_by_ref"),
    }


def _build_firewall_entry(row: dict[str, Any]) -> dict[str, Any]:
    """Extract firewall policy from network row."""
    obj = row.get("object", {}) or {}
    props = obj.get("properties", {}) or {}

    return {
        "instance_id": row.get("instance_id", ""),
        "name": row.get("instance_id", "").replace("inst.fw.", "").replace(".", "_"),
        "chain": props.get("chain", "forward"),
        "action": props.get("action", "drop"),
        "src_zone": props.get("src_zone"),
        "dst_zone": props.get("dst_zone"),
        "comment": row.get("notes", ""),
    }


def build_mikrotik_projection(compiled_json: dict[str, Any]) -> dict[str, Any]:
    """Build stable view for MikroTik Terraform generator."""
    groups = _instance_groups(compiled_json)
    devices = _group_rows(groups, canonical=GROUP_DEVICES)
    network = _group_rows(groups, canonical=GROUP_NETWORK)
    service_rows = _group_rows(groups, canonical=GROUP_SERVICES)

    routers: list[dict[str, Any]] = []
    router_ids: set[str] = set()
    for idx, row in enumerate(devices):
        object_ref = _require_object_ref(row, path=f"compiled_json.instances.devices[{idx}]")
        instance_id = _require_non_empty_str(row, field="instance_id", path=f"compiled_json.instances.devices[{idx}]")
        if object_ref.startswith("obj.mikrotik."):
            export_row = dict(row)
            export_row.pop("instance", None)
            routers.append(export_row)
            router_ids.add(instance_id)

    networks: list[dict[str, Any]] = []
    vlans: list[dict[str, Any]] = []
    firewall_policies: list[dict[str, Any]] = []

    for idx, row in enumerate(network):
        _require_non_empty_str(row, field="instance_id", path=f"compiled_json.instances.network[{idx}]")
        object_ref = _require_object_ref(row, path=f"compiled_json.instances.network[{idx}]")
        export_row = dict(row)
        export_row.pop("instance", None)
        networks.append(export_row)

        # Extract VLANs managed by MikroTik routers
        if "vlan" in object_ref:
            vlan_entry = _build_vlan_entry(row)
            if vlan_entry.get("managed_by_ref") in router_ids:
                vlans.append(vlan_entry)

        # Extract firewall policies
        if "firewall" in object_ref:
            fw_entry = _build_firewall_entry(row)
            firewall_policies.append(fw_entry)

    selected_services: list[dict[str, Any]] = []
    for idx, row in enumerate(service_rows):
        _require_non_empty_str(row, field="instance_id", path=f"compiled_json.instances.services[{idx}]")
        runtime = row.get("runtime")
        if runtime and not isinstance(runtime, dict):
            raise ProjectionError(f"compiled_json.instances.services[{idx}].runtime must be mapping/object")
        target_ref = runtime.get("target_ref") if isinstance(runtime, dict) else None
        if isinstance(target_ref, str) and target_ref in router_ids:
            export_row = dict(row)
            export_row.pop("instance", None)
            selected_services.append(export_row)

    capability_flags = _derive_mikrotik_capability_flags(routers)
    return {
        "routers": _sorted_rows(routers),
        "networks": _sorted_rows(networks),
        "vlans": sorted(vlans, key=lambda v: v.get("vlan_id") or 0),
        "firewall_policies": firewall_policies,
        "services": _sorted_rows(selected_services),
        "capabilities": capability_flags,
        "counts": {
            "routers": len(routers),
            "networks": len(networks),
            "vlans": len(vlans),
            "services": len(selected_services),
        },
    }
