#!/usr/bin/env python3
"""MikroTik-owned projection helpers for object generators."""

from __future__ import annotations

from typing import Any

from plugins.generators.projection_core import (
    # ADR0078 WP-006: Group canonical name constants
    GROUP_DEVICES,
    GROUP_NETWORK,
    GROUP_SERVICES,
    ProjectionError,
    _group_rows,
    _instance_groups,
    _require_non_empty_str,
    _sorted_rows,
)


def _extract_capabilities(row: dict[str, Any]) -> set[str]:
    """Extract capability IDs from instance row."""
    caps: set[str] = set()
    # ADR0078: read all capability fields consistently with other projections
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


def build_mikrotik_projection(compiled_json: dict[str, Any]) -> dict[str, Any]:
    """Build stable view for MikroTik Terraform generator."""
    groups = _instance_groups(compiled_json)
    devices = _group_rows(groups, canonical=GROUP_DEVICES)
    network = _group_rows(groups, canonical=GROUP_NETWORK)
    service_rows = _group_rows(groups, canonical=GROUP_SERVICES)

    routers: list[dict[str, Any]] = []
    router_ids: set[str] = set()
    for idx, row in enumerate(devices):
        object_ref = _require_non_empty_str(
            row,
            field="object_ref",
            path=f"compiled_json.instances.devices[{idx}]",
        )
        instance_id = _require_non_empty_str(row, field="instance_id", path=f"compiled_json.instances.devices[{idx}]")
        if object_ref.startswith("obj.mikrotik."):
            routers.append(row)
            router_ids.add(instance_id)

    networks: list[dict[str, Any]] = []
    for idx, row in enumerate(network):
        _require_non_empty_str(row, field="instance_id", path=f"compiled_json.instances.network[{idx}]")
        _require_non_empty_str(row, field="object_ref", path=f"compiled_json.instances.network[{idx}]")
        networks.append(row)

    selected_services: list[dict[str, Any]] = []
    for idx, row in enumerate(service_rows):
        _require_non_empty_str(row, field="instance_id", path=f"compiled_json.instances.services[{idx}]")
        runtime = row.get("runtime")
        if runtime and not isinstance(runtime, dict):
            raise ProjectionError(f"compiled_json.instances.services[{idx}].runtime must be mapping/object")
        target_ref = runtime.get("target_ref") if isinstance(runtime, dict) else None
        if isinstance(target_ref, str) and target_ref in router_ids:
            selected_services.append(row)

    capability_flags = _derive_mikrotik_capability_flags(routers)
    return {
        "routers": _sorted_rows(routers),
        "networks": _sorted_rows(networks),
        "services": _sorted_rows(selected_services),
        "capabilities": capability_flags,
        "counts": {
            "routers": len(routers),
            "networks": len(networks),
            "services": len(selected_services),
        },
    }
