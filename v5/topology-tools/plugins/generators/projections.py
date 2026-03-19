#!/usr/bin/env python3
"""Projection helpers for v5 deployment generators."""

from __future__ import annotations

import json
from copy import deepcopy
from typing import Any


class ProjectionError(ValueError):
    """Raised when compiled model does not satisfy projection contract."""


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
        str(row.get("instance", "")),
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
            _require_non_empty_str(row, field="instance", path=f"compiled_json.instances.l1_devices[{idx}]")
            proxmox_nodes.append(row)

    lxc_rows: list[dict[str, Any]] = []
    lxc_targets: set[str] = set()
    for idx, row in enumerate(l4_lxc):
        instance_id = _require_non_empty_str(row, field="instance", path=f"compiled_json.instances.l4_lxc[{idx}]")
        _require_non_empty_str(row, field="object_ref", path=f"compiled_json.instances.l4_lxc[{idx}]")
        lxc_rows.append(row)
        lxc_targets.add(instance_id)

    service_rows: list[dict[str, Any]] = []
    for idx, row in enumerate(l5_services):
        instance_id = _require_non_empty_str(row, field="instance", path=f"compiled_json.instances.l5_services[{idx}]")
        runtime = row.get("runtime")
        if runtime and not isinstance(runtime, dict):
            raise ProjectionError(f"compiled_json.instances.l5_services[{idx}].runtime must be mapping/object")
        target_ref = runtime.get("target_ref") if isinstance(runtime, dict) else None
        if isinstance(target_ref, str) and target_ref in lxc_targets:
            row["instance"] = instance_id
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
        instance_id = _require_non_empty_str(row, field="instance", path=f"compiled_json.instances.l1_devices[{idx}]")
        if object_ref.startswith("obj.mikrotik."):
            routers.append(row)
            router_ids.add(instance_id)

    networks: list[dict[str, Any]] = []
    for idx, row in enumerate(l2_network):
        _require_non_empty_str(row, field="instance", path=f"compiled_json.instances.l2_network[{idx}]")
        _require_non_empty_str(row, field="object_ref", path=f"compiled_json.instances.l2_network[{idx}]")
        networks.append(row)

    services: list[dict[str, Any]] = []
    for idx, row in enumerate(l5_services):
        _require_non_empty_str(row, field="instance", path=f"compiled_json.instances.l5_services[{idx}]")
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
        _require_non_empty_str(row, field="instance", path=f"compiled_json.instances.l1_devices[{idx}]")
        _require_non_empty_str(row, field="object_ref", path=f"compiled_json.instances.l1_devices[{idx}]")
        host = deepcopy(row)
        host["inventory_group"] = "l1_devices"
        hosts.append(host)
    for idx, row in enumerate(l4_lxc):
        _require_non_empty_str(row, field="instance", path=f"compiled_json.instances.l4_lxc[{idx}]")
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
        _require_non_empty_str(row, field="instance", path=f"compiled_json.instances.l1_devices[{idx}]")
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

