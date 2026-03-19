#!/usr/bin/env python3
"""Projection helpers for v5 deployment generators.

Phase 2: Projections are deterministic, schema-aware, and independent from
template-specific naming quirks. Generators consume projections, not raw
compiled internals.

Each projection function returns a dict with stable, sorted keys suitable for
template rendering. Dataclasses provide typed access for generator implementations.
"""

from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any


class ProjectionError(ValueError):
    """Raised when compiled model does not satisfy projection contract."""


# -----------------------------------------------------------------------------
# Validation helpers
# -----------------------------------------------------------------------------


def _require_mapping(node: Any, *, path: str) -> dict[str, Any]:
    if not isinstance(node, dict):
        raise ProjectionError(f"{path} must be mapping/object")
    return node


def _require_rows(node: Any, *, path: str) -> list[dict[str, Any]]:
    if node is None:
        return []
    if not isinstance(node, list):
        raise ProjectionError(f"{path} must be list")
    rows: list[dict[str, Any]] = []
    for idx, row in enumerate(node):
        if not isinstance(row, dict):
            raise ProjectionError(f"{path}[{idx}] must be mapping/object")
        rows.append(deepcopy(row))
    return rows


def _row_sort_key(row: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(row.get("instance_id", "")),
        str(row.get("object_ref", "")),
        json.dumps(row, sort_keys=True, ensure_ascii=True),
    )


def _sorted_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(rows, key=_row_sort_key)


def _require_non_empty_str(row: dict[str, Any], *, field: str, path: str) -> str:
    value = row.get(field)
    if not isinstance(value, str) or not value:
        raise ProjectionError(f"{path}.{field} must be non-empty string")
    return value


def _instance_groups(compiled_json: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    root = _require_mapping(compiled_json, path="compiled_json")
    instances = _require_mapping(root.get("instances"), path="compiled_json.instances")
    groups: dict[str, list[dict[str, Any]]] = {}
    for group_name, node in instances.items():
        groups[group_name] = _require_rows(node, path=f"compiled_json.instances.{group_name}")
    return groups


def _get_instance_data(row: dict[str, Any], path: str, default: Any = None) -> Any:
    """Get a value from row by dot-separated path, checking both top-level and nested fields."""
    parts = path.split(".")
    current: Any = row
    for part in parts:
        if not isinstance(current, dict):
            return default
        current = current.get(part)
        if current is None:
            return default
    return current


# -----------------------------------------------------------------------------
# Proxmox Dataclasses
# -----------------------------------------------------------------------------


@dataclass
class ProxmoxBridge:
    """Typed bridge for Proxmox Terraform."""

    id: str
    name: str
    vlan_aware: bool = False
    comment: str = ""
    ports: list[str] = field(default_factory=list)


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


@dataclass
class ProxmoxVM:
    """Typed VM for Proxmox Terraform."""

    id: str
    instance_id: str
    vmid: int | None = None
    name: str = ""
    cores: int = 2
    memory: int = 2048
    disk_size: str = "32G"
    storage: str = "local-lvm"
    network_bridge: str = "vmbr0"
    ip_address: str = ""
    gateway: str = ""
    os_type: str = "l26"
    start_on_boot: bool = True
    description: str = ""
    tags: list[str] = field(default_factory=list)


# -----------------------------------------------------------------------------
# MikroTik Dataclasses
# -----------------------------------------------------------------------------


@dataclass
class MikroTikInterface:
    """Typed interface for MikroTik Terraform."""

    name: str
    type: str = "ether"
    disabled: bool = False
    comment: str = ""
    master_port: str | None = None
    vlan_id: int | None = None


@dataclass
class MikroTikAddress:
    """Typed IP address for MikroTik Terraform."""

    address: str
    interface: str
    comment: str = ""
    disabled: bool = False


@dataclass
class MikroTikFirewallRule:
    """Typed firewall rule for MikroTik Terraform."""

    chain: str
    action: str
    src_address: str = ""
    dst_address: str = ""
    protocol: str = ""
    dst_port: str = ""
    in_interface: str = ""
    out_interface: str = ""
    comment: str = ""
    disabled: bool = False


# -----------------------------------------------------------------------------
# Ansible Dataclasses
# -----------------------------------------------------------------------------


@dataclass
class AnsibleHost:
    """Typed host for Ansible inventory."""

    name: str
    ansible_host: str = ""
    ansible_user: str = "root"
    ansible_port: int = 22
    groups: list[str] = field(default_factory=list)
    vars: dict[str, Any] = field(default_factory=dict)


# -----------------------------------------------------------------------------
# Bootstrap Dataclasses
# -----------------------------------------------------------------------------


@dataclass
class BootstrapDevice:
    """Typed device for bootstrap generation."""

    instance_id: str
    device_type: str  # proxmox, mikrotik, orangepi
    hostname: str = ""
    ip_address: str = ""
    gateway: str = ""
    dns_servers: list[str] = field(default_factory=list)
    ssh_user: str = "root"
    ssh_port: int = 22
    disk_device: str = ""
    storage_config: dict[str, Any] = field(default_factory=dict)
    network_config: dict[str, Any] = field(default_factory=dict)


# -----------------------------------------------------------------------------
# Projection Builders (dict-based for template compatibility)
# -----------------------------------------------------------------------------


def build_proxmox_projection(compiled_json: dict[str, Any]) -> dict[str, Any]:
    """Build stable view for Proxmox Terraform generator."""
    groups = _instance_groups(compiled_json)
    l1_devices = groups.get("l1_devices", [])
    l4_lxc = groups.get("l4_lxc", [])
    l5_services = groups.get("l5_services", [])

    proxmox_nodes: list[dict[str, Any]] = []
    for idx, row in enumerate(l1_devices):
        object_ref = _require_non_empty_str(
            row,
            field="object_ref",
            path=f"compiled_json.instances.l1_devices[{idx}]",
        )
        if object_ref == "obj.proxmox.ve":
            _require_non_empty_str(row, field="instance_id", path=f"compiled_json.instances.l1_devices[{idx}]")
            proxmox_nodes.append(row)

    lxc_rows: list[dict[str, Any]] = []
    lxc_targets: set[str] = set()
    for idx, row in enumerate(l4_lxc):
        instance_id = _require_non_empty_str(row, field="instance_id", path=f"compiled_json.instances.l4_lxc[{idx}]")
        _require_non_empty_str(row, field="object_ref", path=f"compiled_json.instances.l4_lxc[{idx}]")
        lxc_rows.append(row)
        lxc_targets.add(instance_id)

    service_rows: list[dict[str, Any]] = []
    for idx, row in enumerate(l5_services):
        instance_id = _require_non_empty_str(row, field="instance_id", path=f"compiled_json.instances.l5_services[{idx}]")
        runtime = row.get("runtime")
        if runtime and not isinstance(runtime, dict):
            raise ProjectionError(f"compiled_json.instances.l5_services[{idx}].runtime must be mapping/object")
        target_ref = runtime.get("target_ref") if isinstance(runtime, dict) else None
        if isinstance(target_ref, str) and target_ref in lxc_targets:
            service_rows.append(row)

    return {
        "proxmox_nodes": _sorted_rows(proxmox_nodes),
        "lxc": _sorted_rows(lxc_rows),
        "services": _sorted_rows(service_rows),
        "counts": {
            "proxmox_nodes": len(proxmox_nodes),
            "lxc": len(lxc_rows),
            "services": len(service_rows),
        },
    }


def build_mikrotik_projection(compiled_json: dict[str, Any]) -> dict[str, Any]:
    """Build stable view for MikroTik Terraform generator."""
    groups = _instance_groups(compiled_json)
    l1_devices = groups.get("l1_devices", [])
    l2_network = groups.get("l2_network", [])
    l5_services = groups.get("l5_services", [])

    routers: list[dict[str, Any]] = []
    router_ids: set[str] = set()
    for idx, row in enumerate(l1_devices):
        object_ref = _require_non_empty_str(
            row,
            field="object_ref",
            path=f"compiled_json.instances.l1_devices[{idx}]",
        )
        instance_id = _require_non_empty_str(row, field="instance_id", path=f"compiled_json.instances.l1_devices[{idx}]")
        if object_ref.startswith("obj.mikrotik."):
            routers.append(row)
            router_ids.add(instance_id)

    networks: list[dict[str, Any]] = []
    for idx, row in enumerate(l2_network):
        _require_non_empty_str(row, field="instance_id", path=f"compiled_json.instances.l2_network[{idx}]")
        _require_non_empty_str(row, field="object_ref", path=f"compiled_json.instances.l2_network[{idx}]")
        networks.append(row)

    services: list[dict[str, Any]] = []
    for idx, row in enumerate(l5_services):
        _require_non_empty_str(row, field="instance_id", path=f"compiled_json.instances.l5_services[{idx}]")
        runtime = row.get("runtime")
        if runtime and not isinstance(runtime, dict):
            raise ProjectionError(f"compiled_json.instances.l5_services[{idx}].runtime must be mapping/object")
        target_ref = runtime.get("target_ref") if isinstance(runtime, dict) else None
        if isinstance(target_ref, str) and target_ref in router_ids:
            services.append(row)

    return {
        "routers": _sorted_rows(routers),
        "networks": _sorted_rows(networks),
        "services": _sorted_rows(services),
        "counts": {
            "routers": len(routers),
            "networks": len(networks),
            "services": len(services),
        },
    }


def build_ansible_projection(compiled_json: dict[str, Any]) -> dict[str, Any]:
    """Build stable view for Ansible inventory generator."""
    groups = _instance_groups(compiled_json)
    l1_devices = groups.get("l1_devices", [])
    l4_lxc = groups.get("l4_lxc", [])

    hosts: list[dict[str, Any]] = []
    for idx, row in enumerate(l1_devices):
        _require_non_empty_str(row, field="instance_id", path=f"compiled_json.instances.l1_devices[{idx}]")
        _require_non_empty_str(row, field="object_ref", path=f"compiled_json.instances.l1_devices[{idx}]")
        host = deepcopy(row)
        host["inventory_group"] = "l1_devices"
        hosts.append(host)
    for idx, row in enumerate(l4_lxc):
        _require_non_empty_str(row, field="instance_id", path=f"compiled_json.instances.l4_lxc[{idx}]")
        _require_non_empty_str(row, field="object_ref", path=f"compiled_json.instances.l4_lxc[{idx}]")
        host = deepcopy(row)
        host["inventory_group"] = "l4_lxc"
        hosts.append(host)

    return {
        "hosts": _sorted_rows(hosts),
        "counts": {
            "hosts": len(hosts),
        },
    }


def build_bootstrap_projection(compiled_json: dict[str, Any]) -> dict[str, Any]:
    """Build stable view for bootstrap generators."""
    groups = _instance_groups(compiled_json)
    l1_devices = groups.get("l1_devices", [])

    proxmox_nodes: list[dict[str, Any]] = []
    mikrotik_nodes: list[dict[str, Any]] = []
    orangepi_nodes: list[dict[str, Any]] = []

    for idx, row in enumerate(l1_devices):
        object_ref = _require_non_empty_str(
            row,
            field="object_ref",
            path=f"compiled_json.instances.l1_devices[{idx}]",
        )
        _require_non_empty_str(row, field="instance_id", path=f"compiled_json.instances.l1_devices[{idx}]")
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


# -----------------------------------------------------------------------------
# Typed Projection Builders (for Phase 3+ generators)
# -----------------------------------------------------------------------------


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
