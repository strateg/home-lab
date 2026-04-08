#!/usr/bin/env python3
"""MikroTik-owned projection helpers for object generators."""

from __future__ import annotations

from ipaddress import ip_interface
from typing import Any

from plugins.generators.projection_core import (  # ADR0078 WP-006: Group canonical name constants
    GROUP_DEVICES,
    GROUP_NETWORK,
    GROUP_SERVICES,
    ProjectionError,
    _group_rows,
    _instance_groups,
    _require_non_empty_str,
    _require_object_ref,
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
        raw = object_file.read_text(encoding="utf-8")
        # Topology object modules use @-prefixed metadata keys; plain PyYAML can reject
        # some unquoted forms, so normalize only metadata keys before parsing.
        normalized_lines: list[str] = []
        for line in raw.splitlines():
            stripped = line.lstrip()
            indent = line[: len(line) - len(stripped)]
            if stripped.startswith("@") and ":" in stripped:
                key, rest = stripped.split(":", 1)
                normalized_lines.append(f'{indent}"{key}":{rest}')
            else:
                normalized_lines.append(line)
        payload = yaml.safe_load("\n".join(normalized_lines)) or {}
        if isinstance(payload, dict):
            props = payload.get("properties", {})
            if isinstance(props, dict):
                return props
        return {}
    except Exception:
        return {}


def _is_staged_row(row: dict[str, Any]) -> bool:
    status = str(row.get("status", "")).strip().lower()
    notes = str(row.get("notes", "")).strip().lower()
    return status == "modeled" or "currently not configured" in notes


def _build_vlan_entry(row: dict[str, Any], *, managed_by_ref: str) -> dict[str, Any]:
    """Extract VLAN configuration from network row."""
    object_ref = _resolved_object_ref(row)
    inst_data = row.get("instance_data", {}) or {}

    # Load properties from object module file
    props = _load_object_properties(object_ref)

    vlan_id = props.get("vlan_id")
    is_native_lan = int(vlan_id or 0) == 1
    interface_name = "bridge" if is_native_lan else f"vlan{vlan_id}"

    return {
        "instance_id": row.get("instance_id", ""),
        "name": row.get("instance_id", "").replace("inst.vlan.", "").replace(".", "_"),
        "vlan_id": vlan_id,
        "cidr": props.get("cidr"),
        "gateway": props.get("gateway"),
        "mtu": props.get("mtu", 1500),
        "dhcp_enabled": props.get("dhcp_enabled", False),
        "dhcp_range": inst_data.get("dhcp_range"),
        "dns_servers": props.get("dns_servers", []),
        "managed_by_ref": managed_by_ref,
        "trust_zone_ref": inst_data.get("trust_zone_ref"),
        "staged": _is_staged_row(row),
        "is_native_lan": is_native_lan,
        "interface_name": interface_name,
        "interface_is_resource": not is_native_lan,
    }


def _build_bridge_entry(row: dict[str, Any], *, managed_by_ref: str) -> dict[str, Any]:
    """Extract bridge configuration from network row."""
    object_ref = _resolved_object_ref(row)
    inst_data = row.get("instance_data", {}) or {}
    props = _load_object_properties(object_ref)
    ip_addr = str(inst_data.get("ip") or "").strip()
    cidr = str(inst_data.get("cidr") or "").strip()
    if not cidr and ip_addr:
        try:
            cidr = str(ip_interface(ip_addr).network)
        except ValueError:
            cidr = ""
    name = str(props.get("name") or row.get("instance_id", "").replace("inst.bridge.", "")).strip() or "bridge"
    return {
        "instance_id": row.get("instance_id", ""),
        "name": name.replace(".", "_"),
        "bridge_name": name,
        "ip": ip_addr,
        "cidr": cidr,
        "managed_by_ref": managed_by_ref,
        "staged": _is_staged_row(row),
    }


def _build_firewall_entry(row: dict[str, Any], *, managed_by_ref: str) -> dict[str, Any]:
    """Extract firewall policy from network row."""
    object_ref = _resolved_object_ref(row)
    props = _load_object_properties(object_ref)
    inst_data = row.get("instance_data", {}) or {}

    return {
        "instance_id": row.get("instance_id", ""),
        "name": row.get("instance_id", "").replace("inst.fw.", "").replace(".", "_"),
        "chain": str(inst_data.get("chain") or "forward"),
        "managed_by_ref": managed_by_ref,
        "priority": int(props.get("priority", 1000)),
        "default_action": str(props.get("default_action", "drop")),
        "rules": props.get("rules", []) if isinstance(props.get("rules"), list) else [],
        "comment": str(row.get("notes", "")),
        "staged": _is_staged_row(row),
    }


def build_mikrotik_projection(compiled_json: dict[str, Any]) -> dict[str, Any]:
    """Build stable view for MikroTik Terraform generator."""
    groups = _instance_groups(compiled_json)
    devices = _group_rows(groups, canonical=GROUP_DEVICES)
    network = _group_rows(groups, canonical=GROUP_NETWORK)
    service_rows = _group_rows(groups, canonical=GROUP_SERVICES)
    firewall_rows = groups.get("firewall", [])

    routers: list[dict[str, Any]] = []
    router_ids: set[str] = set()
    for idx, row in enumerate(devices):
        object_ref = _require_object_ref(row, path=f"compiled_json.instances.devices[{idx}]")
        instance_id = _require_non_empty_str(row, field="instance_id", path=f"compiled_json.instances.devices[{idx}]")
        if object_ref.startswith("obj.mikrotik."):
            export_row = dict(row)
            export_row.pop("instance", None)
            instance_data = export_row.get("instance_data")
            if not isinstance(instance_data, dict):
                instance_data = {}
            routers.append(export_row)
            router_ids.add(instance_id)

    networks: list[dict[str, Any]] = []
    bridges: list[dict[str, Any]] = []
    vlans: list[dict[str, Any]] = []
    firewall_policies: list[dict[str, Any]] = []

    default_router_id = next(iter(sorted(router_ids)), "")

    for idx, row in enumerate(network):
        _require_non_empty_str(row, field="instance_id", path=f"compiled_json.instances.network[{idx}]")
        object_ref = _require_object_ref(row, path=f"compiled_json.instances.network[{idx}]")
        export_row = dict(row)
        export_row.pop("instance", None)
        networks.append(export_row)
        inst_data = row.get("instance_data", {}) if isinstance(row.get("instance_data"), dict) else {}
        managed_by_ref = str(inst_data.get("managed_by_ref") or "").strip()

        if "bridge" in object_ref:
            host_ref = str(inst_data.get("host_ref") or "").strip()
            if not managed_by_ref and host_ref in router_ids:
                managed_by_ref = host_ref
            if managed_by_ref in router_ids:
                bridges.append(_build_bridge_entry(row, managed_by_ref=managed_by_ref))

        # Extract VLANs managed by MikroTik routers.
        if "vlan" in object_ref:
            if not managed_by_ref and len(router_ids) == 1:
                # VLAN instances are treated as router-owned in single-router topology.
                managed_by_ref = default_router_id
            if not managed_by_ref:
                allocations = inst_data.get("ip_allocations")
                if isinstance(allocations, list):
                    for item in allocations:
                        if not isinstance(item, dict):
                            continue
                        device_ref = str(item.get("device_ref") or "").strip()
                        if device_ref in router_ids:
                            managed_by_ref = device_ref
                            break
            if managed_by_ref in router_ids:
                vlan_entry = _build_vlan_entry(row, managed_by_ref=managed_by_ref)
                vlans.append(vlan_entry)

    # Extract firewall policies from dedicated firewall group.
    for idx, row in enumerate(firewall_rows):
        _require_non_empty_str(row, field="instance_id", path=f"compiled_json.instances.firewall[{idx}]")
        object_ref = _require_object_ref(row, path=f"compiled_json.instances.firewall[{idx}]")
        if "firewall_policy" not in object_ref:
            continue
        inst_data = row.get("instance_data", {}) if isinstance(row.get("instance_data"), dict) else {}
        managed_by_ref = str(inst_data.get("managed_by_ref") or "").strip()
        if not managed_by_ref and len(router_ids) == 1:
            managed_by_ref = default_router_id
        if managed_by_ref in router_ids:
            firewall_policies.append(_build_firewall_entry(row, managed_by_ref=managed_by_ref))

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

    # Build trust-zone to CIDR map from VLANs for firewall zone matching.
    trust_zone_cidrs: dict[str, str] = {}
    for vlan in vlans:
        zone_ref = str(vlan.get("trust_zone_ref") or "").strip()
        cidr = str(vlan.get("cidr") or "").strip()
        if zone_ref and cidr:
            trust_zone_cidrs[zone_ref] = cidr

    # Normalize firewall rules with CIDR resolution.
    normalized_firewall: list[dict[str, Any]] = []
    for policy in firewall_policies:
        rules = policy.get("rules", [])
        normalized_rules: list[dict[str, Any]] = []
        if isinstance(rules, list):
            for rule in rules:
                if not isinstance(rule, dict):
                    continue
                src_zone_ref = str(rule.get("src_zone_ref") or "").strip()
                dst_zone_ref = str(rule.get("dst_zone_ref") or "").strip()
                normalized_rules.append(
                    {
                        "action": str(rule.get("action") or policy.get("default_action") or "drop"),
                        "protocol": str(rule.get("protocol") or "any"),
                        "comment": str(rule.get("comment") or policy.get("comment") or ""),
                        "src_zone_ref": src_zone_ref,
                        "dst_zone_ref": dst_zone_ref,
                        "src_cidr": trust_zone_cidrs.get(f"inst.trust_zone.{src_zone_ref}", ""),
                        "dst_cidr": trust_zone_cidrs.get(f"inst.trust_zone.{dst_zone_ref}", ""),
                    }
                )
        normalized = dict(policy)
        normalized["rules"] = normalized_rules
        normalized_firewall.append(normalized)

    # Runtime-derived baseline (single-router case) for NAT/DHCP/addresses.
    runtime_baseline: dict[str, Any] = {
        "nat": [],
        "dns_servers": [],
        "dhcp": {
            "enabled": False,
            "pool_range": "",
            "server_name": "",
            "lease_time": "",
            "network_cidr": "",
            "gateway": "",
            "interface": "",
        },
        "addresses": [],
    }
    if len(routers) == 1:
        router_data = routers[0].get("instance_data") if isinstance(routers[0].get("instance_data"), dict) else {}
        observed = router_data.get("observed_runtime") if isinstance(router_data, dict) else {}
        if isinstance(observed, dict):
            nat_items = observed.get("nat")
            if isinstance(nat_items, list):
                runtime_baseline["nat"] = [item for item in nat_items if isinstance(item, dict)]
            dns = observed.get("dns")
            if isinstance(dns, dict):
                servers = dns.get("servers")
                if isinstance(servers, list):
                    runtime_baseline["dns_servers"] = [str(v) for v in servers if isinstance(v, str) and v]
            lan = observed.get("lan")
            if isinstance(lan, dict):
                gateway_ref = str(lan.get("gateway_ref") or "").strip()
                dhcp_pool = str(lan.get("dhcp_pool") or "").strip()
                dhcp_server = str(lan.get("dhcp_server") or "").strip()
                dhcp_lease_time = str(lan.get("dhcp_lease_time") or "").strip()
                bridge_if = str(lan.get("bridge_interface") or "bridge").strip() or "bridge"
                lan_cidr = ""
                lan_gateway = ""
                for vlan in vlans:
                    if str(vlan.get("instance_id", "")).strip() == gateway_ref:
                        lan_cidr = str(vlan.get("cidr") or "").strip()
                        lan_gateway = str(vlan.get("gateway") or "").strip()
                        break
                runtime_baseline["dhcp"] = {
                    "enabled": bool(dhcp_pool and lan_cidr and lan_gateway),
                    "pool_range": dhcp_pool,
                    "server_name": dhcp_server or "defconf",
                    "lease_time": dhcp_lease_time or "30m",
                    "network_cidr": lan_cidr,
                    "gateway": lan_gateway,
                    "interface": bridge_if,
                }
            containers = observed.get("containers")
            if isinstance(containers, dict):
                bridge_ip = str(containers.get("bridge_ip") or "").strip()
                bridge_if = str(containers.get("bridge_interface") or "containers").strip() or "containers"
                if bridge_ip:
                    runtime_baseline["addresses"].append({"address": bridge_ip, "interface": bridge_if})

    capability_flags = _derive_mikrotik_capability_flags(routers)
    return {
        "routers": _sorted_rows(routers),
        "networks": _sorted_rows(networks),
        "bridges": sorted(bridges, key=lambda b: str(b.get("instance_id", ""))),
        "vlans": sorted(vlans, key=lambda v: (int(v.get("vlan_id") or 0), str(v.get("instance_id", "")))),
        "firewall_policies": sorted(
            normalized_firewall,
            key=lambda p: (int(p.get("priority") or 1000), str(p.get("instance_id", ""))),
        ),
        "trust_zone_cidrs": trust_zone_cidrs,
        "runtime_baseline": runtime_baseline,
        "services": _sorted_rows(selected_services),
        "capabilities": capability_flags,
        "counts": {
            "routers": len(routers),
            "networks": len(networks),
            "bridges": len(bridges),
            "vlans": len(vlans),
            "firewall_policies": len(firewall_policies),
            "services": len(selected_services),
        },
    }
