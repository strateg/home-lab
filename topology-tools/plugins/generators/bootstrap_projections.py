#!/usr/bin/env python3
"""Framework-shared bootstrap projection helpers for object-owned generators."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from plugins.generators.projection_core import (  # ADR0078 WP-006: Group canonical name constants
    GROUP_DEVICES,
    ProjectionError,
    _get_instance_data,
    _group_rows,
    _instance_groups,
    _require_non_empty_str,
    _sorted_rows,
)


@dataclass
class BootstrapDevice:
    """Typed device for bootstrap generation."""

    instance_id: str
    device_type: str
    hostname: str = ""
    ip_address: str = ""
    gateway: str = ""
    dns_servers: list[str] = field(default_factory=list)
    ssh_user: str = "root"
    ssh_port: int = 22
    disk_device: str = ""
    storage_config: dict[str, Any] = field(default_factory=dict)
    network_config: dict[str, Any] = field(default_factory=dict)


def build_bootstrap_projection(compiled_json: dict[str, Any]) -> dict[str, Any]:
    """Build stable view for bootstrap generators."""
    groups = _instance_groups(compiled_json)
    devices = _group_rows(groups, canonical=GROUP_DEVICES)

    proxmox_nodes: list[dict[str, Any]] = []
    mikrotik_nodes: list[dict[str, Any]] = []
    orangepi_nodes: list[dict[str, Any]] = []

    for idx, row in enumerate(devices):
        object_ref = _require_non_empty_str(
            row,
            field="object_ref",
            path=f"compiled_json.instances.devices[{idx}]",
        )
        _require_non_empty_str(row, field="instance_id", path=f"compiled_json.instances.devices[{idx}]")
        mechanism = _resolve_initialization_mechanism(row)
        if mechanism == "unattended_install":
            proxmox_nodes.append(row)
            continue
        if mechanism == "netinstall":
            mikrotik_nodes.append(row)
            continue
        if mechanism == "cloud_init":
            orangepi_nodes.append(row)
            continue

        # Legacy fallback until all bootstrap-capable objects declare initialization_contract.
        if object_ref == "obj.proxmox.ve":
            proxmox_nodes.append(row)
        if object_ref.startswith("obj.mikrotik."):
            mikrotik_nodes.append(row)
        if object_ref.startswith("obj.orangepi."):
            orangepi_nodes.append(row)

    return {
        "proxmox_nodes": _sorted_rows(proxmox_nodes),
        "mikrotik_nodes": _sorted_rows(mikrotik_nodes),
        "orangepi_nodes": _sorted_rows(orangepi_nodes),
        "counts": {
            "proxmox_nodes": len(proxmox_nodes),
            "mikrotik_nodes": len(mikrotik_nodes),
            "orangepi_nodes": len(orangepi_nodes),
        },
    }


def _resolve_initialization_mechanism(row: dict[str, Any]) -> str:
    obj = row.get("object")
    if not isinstance(obj, dict):
        return ""
    contract = obj.get("initialization_contract")
    if not isinstance(contract, dict):
        return ""
    mechanism = contract.get("mechanism")
    if not isinstance(mechanism, str):
        return ""
    return mechanism.strip().lower()


def build_bootstrap_typed(compiled_json: dict[str, Any]) -> list[BootstrapDevice]:
    """Build typed bootstrap device list."""
    projection = build_bootstrap_projection(compiled_json)
    result: list[BootstrapDevice] = []

    for row in projection["proxmox_nodes"]:
        instance_id = row.get("instance_id", "")
        result.append(
            BootstrapDevice(
                instance_id=instance_id,
                device_type="proxmox",
                hostname=_get_instance_data(row, "management.hostname", instance_id),
                ip_address=_get_instance_data(row, "management.ip_address", ""),
                gateway=_get_instance_data(row, "management.gateway", ""),
                dns_servers=_get_instance_data(row, "management.dns_servers", []),
                ssh_user=_get_instance_data(row, "management.ssh_user", "root"),
                disk_device=_get_instance_data(row, "bootstrap.disk_device", ""),
                storage_config=_get_instance_data(row, "storage", {}),
            )
        )

    for row in projection["mikrotik_nodes"]:
        instance_id = row.get("instance_id", "")
        result.append(
            BootstrapDevice(
                instance_id=instance_id,
                device_type="mikrotik",
                hostname=_get_instance_data(row, "management.hostname", instance_id),
                ip_address=_get_instance_data(row, "management.ip_address", ""),
            )
        )

    for row in projection["orangepi_nodes"]:
        instance_id = row.get("instance_id", "")
        result.append(
            BootstrapDevice(
                instance_id=instance_id,
                device_type="orangepi",
                hostname=_get_instance_data(row, "management.hostname", instance_id),
                ip_address=_get_instance_data(row, "management.ip_address", ""),
                ssh_user=_get_instance_data(row, "management.ssh_user", "opi"),
            )
        )

    return sorted(result, key=lambda d: d.instance_id)
