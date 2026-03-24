#!/usr/bin/env python3
"""Proxmox-owned projection helpers for object generators."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from plugins.generators.projection_core import (  # ADR0078 WP-006: Group canonical name constants
    GROUP_DEVICES,
    GROUP_LXC,
    GROUP_SERVICES,
    ProjectionError,
    _get_instance_data,
    _group_rows,
    _instance_groups,
    _require_non_empty_str,
    _sorted_rows,
)


def _extract_capabilities(row: dict[str, Any]) -> set[str]:
    """Extract capability ids from compiled row payload."""
    caps: set[str] = set()
    for field_name in ("capabilities", "derived_capabilities", "enabled_capabilities"):
        raw_caps = row.get(field_name)
        if isinstance(raw_caps, list):
            for cap in raw_caps:
                if isinstance(cap, str) and cap:
                    caps.add(cap)
    return caps


def _derive_proxmox_capability_flags(
    proxmox_nodes: list[dict[str, Any]],
    lxc_rows: list[dict[str, Any]],
    service_rows: list[dict[str, Any]],
) -> dict[str, bool]:
    """Derive boolean capability flags for optional Terraform templates."""
    all_caps: set[str] = set()
    for row in [*proxmox_nodes, *lxc_rows, *service_rows]:
        all_caps.update(_extract_capabilities(row))

    return {
        "has_ceph": "cap.storage.pool.ceph" in all_caps,
        "has_ha": len(proxmox_nodes) > 1 or any("ha" in cap.lower() for cap in all_caps),
        "has_cloud_init": any("cloud" in cap.lower() and "init" in cap.lower() for cap in all_caps),
    }


@dataclass
class ProxmoxLXC:
    """Typed LXC container for Proxmox Terraform."""

    id: str
    instance_id: str
    vmid: int | None = None
    hostname: str = ""
    cores: int = 1
    memory: int = 512
    swap: int = 0
    disk_size: str = "8G"
    storage: str = "local-lvm"
    network_bridge: str = "vmbr0"
    ip_address: str = ""
    gateway: str = ""
    os_template: str = ""
    unprivileged: bool = True
    start_on_boot: bool = True
    description: str = ""
    tags: list[str] = field(default_factory=list)


def build_proxmox_projection(compiled_json: dict[str, Any]) -> dict[str, Any]:
    """Build stable view for Proxmox Terraform generator."""
    groups = _instance_groups(compiled_json)
    devices = _group_rows(groups, canonical=GROUP_DEVICES)
    lxc = _group_rows(groups, canonical=GROUP_LXC)
    input_service_rows = _group_rows(groups, canonical=GROUP_SERVICES)

    proxmox_nodes: list[dict[str, Any]] = []
    for idx, row in enumerate(devices):
        object_ref = _require_non_empty_str(
            row,
            field="object_ref",
            path=f"compiled_json.instances.devices[{idx}]",
        )
        if object_ref == "obj.proxmox.ve":
            _require_non_empty_str(row, field="instance_id", path=f"compiled_json.instances.devices[{idx}]")
            proxmox_nodes.append(row)

    lxc_rows: list[dict[str, Any]] = []
    lxc_targets: set[str] = set()
    for idx, row in enumerate(lxc):
        instance_id = _require_non_empty_str(row, field="instance_id", path=f"compiled_json.instances.lxc[{idx}]")
        _require_non_empty_str(row, field="object_ref", path=f"compiled_json.instances.lxc[{idx}]")
        lxc_rows.append(row)
        lxc_targets.add(instance_id)

    service_rows: list[dict[str, Any]] = []
    for idx, row in enumerate(input_service_rows):
        _require_non_empty_str(row, field="instance_id", path=f"compiled_json.instances.services[{idx}]")
        runtime = row.get("runtime")
        if runtime and not isinstance(runtime, dict):
            raise ProjectionError(f"compiled_json.instances.services[{idx}].runtime must be mapping/object")
        target_ref = runtime.get("target_ref") if isinstance(runtime, dict) else None
        if isinstance(target_ref, str) and target_ref in lxc_targets:
            service_rows.append(row)

    capability_flags = _derive_proxmox_capability_flags(proxmox_nodes, lxc_rows, service_rows)

    return {
        "proxmox_nodes": _sorted_rows(proxmox_nodes),
        "lxc": _sorted_rows(lxc_rows),
        "services": _sorted_rows(service_rows),
        "capabilities": capability_flags,
        "counts": {
            "proxmox_nodes": len(proxmox_nodes),
            "lxc": len(lxc_rows),
            "services": len(service_rows),
        },
    }


def build_proxmox_lxc_typed(compiled_json: dict[str, Any]) -> list[ProxmoxLXC]:
    """Build typed LXC list for Proxmox generator."""
    projection = build_proxmox_projection(compiled_json)
    result: list[ProxmoxLXC] = []
    for row in projection["lxc"]:
        instance_id = row.get("instance_id", "")
        result.append(
            ProxmoxLXC(
                id=instance_id,
                instance_id=instance_id,
                vmid=_get_instance_data(row, "vmid"),
                hostname=_get_instance_data(row, "hostname", instance_id),
                cores=_get_instance_data(row, "resources.cores", 1),
                memory=_get_instance_data(row, "resources.memory", 512),
                swap=_get_instance_data(row, "resources.swap", 0),
                disk_size=_get_instance_data(row, "disk.size", "8G"),
                storage=_get_instance_data(row, "disk.storage", "local-lvm"),
                network_bridge=_get_instance_data(row, "network.bridge", "vmbr0"),
                ip_address=_get_instance_data(row, "network.ip_address", ""),
                gateway=_get_instance_data(row, "network.gateway", ""),
                os_template=_get_instance_data(row, "os_template", ""),
                unprivileged=_get_instance_data(row, "unprivileged", True),
                start_on_boot=_get_instance_data(row, "start_on_boot", True),
                description=row.get("notes", ""),
                tags=_get_instance_data(row, "tags", []) or [],
            )
        )
    return result
