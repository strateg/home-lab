"""Docs domain projection orchestrator (ADR 0079 Phases A-E, ADR 0112)."""

from __future__ import annotations

from typing import Any

from plugins.generators.projection_core import (
    GROUP_DEVICES,
    GROUP_LXC,
    GROUP_NETWORK,
    GROUP_SERVICES,
    GROUP_VM,
    _get_instance_data,
    _group_rows,
    _instance_groups,
    _require_non_empty_str,
    _require_object_ref,
    _resolved_class_ref,
    _sorted_rows,
)
from plugins.generators.projections.mermaid import _safe_id
from plugins.generators.projections.network import build_network_projection
from plugins.generators.projections.operations import build_operations_projection
from plugins.generators.projections.physical import build_physical_projection
from plugins.generators.projections.security import build_security_projection
from plugins.generators.projections.storage import build_storage_projection


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
                service_dependencies.append(
                    {
                        "service_id": instance_id,
                        "service_safe_id": _safe_id(instance_id),
                        "depends_on": target,
                        "depends_on_safe_id": _safe_id(target),
                    }
                )

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
