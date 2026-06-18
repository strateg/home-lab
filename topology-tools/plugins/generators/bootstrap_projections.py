#!/usr/bin/env python3
"""Framework-shared bootstrap projection helpers for object-owned generators."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from plugins.generators.capability_helpers import has_capability
from plugins.generators.projection_core import (  # ADR0078 WP-006: Group canonical name constants
    GROUP_DEVICES,
    ProjectionError,
    _get_instance_data,
    _group_rows,
    _instance_groups,
    _require_non_empty_str,
    _require_object_ref,
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
    """Build stable view for bootstrap generators.

    ADR 0106: Uses capability-based grouping via cap.bootstrap.* capabilities.
    Output keys remain vendor-specific for backward compatibility.
    """
    groups = _instance_groups(compiled_json)
    devices = _group_rows(groups, canonical=GROUP_DEVICES)

    # ADR 0106: Group by bootstrap capability instead of mechanism string
    unattended_nodes: list[dict[str, Any]] = []  # cap.bootstrap.unattended → proxmox
    netinstall_nodes: list[dict[str, Any]] = []  # cap.bootstrap.netinstall → mikrotik
    cloud_init_nodes: list[dict[str, Any]] = []  # cap.bootstrap.cloud_init → orangepi/generic

    for idx, row in enumerate(devices):
        _require_object_ref(row, path=f"compiled_json.instances.devices[{idx}]")
        _require_non_empty_str(row, field="instance_id", path=f"compiled_json.instances.devices[{idx}]")
        export_row = dict(row)
        export_row.pop("instance", None)

        # ADR 0106: Use capability checks instead of mechanism string
        obj = row.get("object", {})
        if has_capability(obj, "cap.bootstrap.unattended"):
            unattended_nodes.append(export_row)
        elif has_capability(obj, "cap.bootstrap.netinstall"):
            netinstall_nodes.append(export_row)
        elif has_capability(obj, "cap.bootstrap.cloud_init"):
            cloud_init_nodes.append(export_row)
        # ADR 0106 ALL-IN: Objects without cap.bootstrap.* are excluded.
        # Strict error E8001 is emitted at compile time by capability_compiler.

    return {
        # Output keys remain vendor-specific for backward compatibility
        "proxmox_nodes": _sorted_rows(unattended_nodes),
        "mikrotik_nodes": _sorted_rows(netinstall_nodes),
        "orangepi_nodes": _sorted_rows(cloud_init_nodes),
        "counts": {
            "proxmox_nodes": len(unattended_nodes),
            "mikrotik_nodes": len(netinstall_nodes),
            "orangepi_nodes": len(cloud_init_nodes),
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
