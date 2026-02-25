"""Shared Terraform resolver helpers."""

from __future__ import annotations

import copy
from typing import Any, Dict, Iterable, List


def _as_list(value: Any) -> List[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        return list(value.values())
    return []


def resolve_interface_names(topology: Dict[str, Any], bridges: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Resolve logical interface IDs to physical names for bridges."""
    interface_map: Dict[str, str] = {}
    for device in _as_list(topology.get("L1_foundation", {}).get("devices")):
        if device.get("type") == "hypervisor":
            for interface in _as_list(device.get("interfaces")):
                interface_id = interface.get("id")
                physical_name = interface.get("physical_name")
                if interface_id and physical_name:
                    interface_map[interface_id] = physical_name

    resolved_bridges: List[Dict[str, Any]] = []
    for bridge in _as_list(bridges):
        item = copy.deepcopy(bridge)
        if item.get("ports"):
            resolved_ports = []
            for port_id in item["ports"]:
                if port_id in interface_map:
                    resolved_ports.append(interface_map[port_id])
                else:
                    print(f"WARN  Warning: Cannot resolve interface '{port_id}' - using as-is")
                    resolved_ports.append(port_id)
            item["ports"] = resolved_ports
        resolved_bridges.append(item)

    return resolved_bridges


def resolve_lxc_resources(topology: Dict[str, Any], lxc_containers: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Resolve effective LXC resources for templates."""
    l4 = topology.get("L4_platform", {}) or {}
    profiles = _as_list(l4.get("resource_profiles"))
    profile_map = {
        profile.get("id"): profile for profile in profiles if isinstance(profile, dict) and profile.get("id")
    }
    resolved: List[Dict[str, Any]] = []

    for container in _as_list(lxc_containers):
        if not isinstance(container, dict):
            continue
        item = copy.deepcopy(container)
        resources = item.get("resources") if isinstance(item.get("resources"), dict) else None

        if not resources:
            profile_ref = item.get("resource_profile_ref")
            profile = profile_map.get(profile_ref, {}) if profile_ref else {}
            cpu = profile.get("cpu") or {}
            memory = profile.get("memory") or {}
            item["resources"] = {
                "cores": cpu.get("cores", 1),
                "memory_mb": memory.get("mb", 512),
                "swap_mb": memory.get("swap_mb", 0),
            }

        item.setdefault("type", item.get("platform_type", "lxc"))
        item.setdefault("role", item.get("resource_profile_ref", "resource-profile"))
        resolved.append(item)

    return resolved


def build_storage_map(topology: Dict[str, Any], platform: str = "proxmox") -> Dict[str, Dict[str, Any]]:
    """Build storage map from legacy pools and storage_endpoints."""
    l3 = topology.get("L3_data", {}) or {}
    storage_map: Dict[str, Dict[str, Any]] = {}

    for storage in _as_list(l3.get("storage")):
        if isinstance(storage, dict) and storage.get("id"):
            storage_map[storage["id"]] = storage

    for endpoint in _as_list(l3.get("storage_endpoints")):
        if not isinstance(endpoint, dict) or not endpoint.get("id"):
            continue
        endpoint_platform = str(endpoint.get("platform") or "").strip().lower()
        if endpoint_platform and endpoint_platform != platform:
            continue
        entry = copy.deepcopy(endpoint)
        entry.setdefault("name", endpoint.get("id"))
        storage_map[endpoint["id"]] = entry

    return storage_map
