"""Legacy effective model/projection helpers extracted from compile-topology.py."""

from __future__ import annotations

from typing import Any, Callable


def compute_reference_projections(
    *,
    rows: list[dict[str, Any]],
    object_map: dict[str, dict[str, Any]],
    catalog_ids: set[str],
    derive_firmware_capabilities: Callable[..., tuple[set[str], dict[str, Any] | None]],
    derive_os_capabilities: Callable[..., tuple[set[str], dict[str, Any] | None]],
) -> tuple[dict[str, list[str]], dict[str, dict[str, Any]]]:
    row_by_id: dict[str, dict[str, Any]] = {}
    for row in rows:
        row_id = row.get("instance")
        if isinstance(row_id, str) and row_id:
            row_by_id[row_id] = row

    instance_derived_caps: dict[str, list[str]] = {}
    instance_software_refs: dict[str, dict[str, Any]] = {}

    for row in rows:
        class_ref = row.get("class_ref")
        object_ref = row.get("object_ref")
        row_id = row.get("instance")
        path = f"instance:{row.get('group')}:{row.get('instance')}"
        if not isinstance(class_ref, str) or not class_ref:
            continue
        if not isinstance(object_ref, str) or not object_ref:
            continue
        if not isinstance(row_id, str) or not row_id:
            continue

        firmware_ref = row.get("firmware_ref")
        os_refs = row.get("os_refs", []) or []
        if not isinstance(os_refs, list):
            os_refs = []

        firmware_row: dict[str, Any] | None = None
        if isinstance(firmware_ref, str):
            firmware_row = row_by_id.get(firmware_ref)

        resolved_os_rows: list[dict[str, Any]] = []
        for os_ref in os_refs:
            os_row = row_by_id.get(os_ref)
            if not isinstance(os_row, dict):
                continue
            if os_row.get("class_ref") != "class.os":
                continue
            resolved_os_rows.append(os_row)

        firmware_effective: dict[str, Any] | None = None
        derived_caps: set[str] = set()
        if isinstance(firmware_row, dict):
            firmware_object_ref = firmware_row.get("object_ref")
            if isinstance(firmware_object_ref, str):
                firmware_object_payload = object_map.get(firmware_object_ref, {}).get("payload", {})
                fw_caps, fw_effective = derive_firmware_capabilities(
                    object_id=firmware_object_ref,
                    object_payload=firmware_object_payload,
                    catalog_ids=catalog_ids,
                    path=path,
                    emit_diagnostics=False,
                )
                derived_caps.update(fw_caps)
                firmware_effective = fw_effective

        resolved_os_refs: list[str] = []
        resolved_os_effective: list[dict[str, Any]] = []
        for os_row in resolved_os_rows:
            os_instance_id = os_row.get("instance")
            os_object_ref = os_row.get("object_ref")
            if not isinstance(os_object_ref, str):
                continue
            os_object_payload = object_map.get(os_object_ref, {}).get("payload", {})
            os_caps, os_effective = derive_os_capabilities(
                object_id=os_object_ref,
                object_payload=os_object_payload,
                catalog_ids=catalog_ids,
                path=path,
                emit_diagnostics=False,
            )
            derived_caps.update(os_caps)
            if isinstance(os_effective, dict):
                resolved_os_effective.append(os_effective)
            if isinstance(os_instance_id, str):
                resolved_os_refs.append(os_instance_id)

        instance_derived_caps[row_id] = sorted(derived_caps)
        instance_software_refs[row_id] = {
            "firmware_ref": firmware_ref if isinstance(firmware_ref, str) else None,
            "os_refs": [ref for ref in resolved_os_refs if isinstance(ref, str)],
            "effective": {
                "firmware": firmware_effective,
                "os": resolved_os_effective,
            },
        }
    return instance_derived_caps, instance_software_refs


def compute_object_capability_projections(
    *,
    object_map: dict[str, dict[str, Any]],
    catalog_ids: set[str],
    derive_firmware_capabilities: Callable[..., tuple[set[str], dict[str, Any] | None]],
    derive_os_capabilities: Callable[..., tuple[set[str], dict[str, Any] | None]],
) -> tuple[dict[str, list[str]], dict[str, dict[str, Any]]]:
    object_derived_caps: dict[str, list[str]] = {}
    object_effective_os: dict[str, dict[str, Any]] = {}

    for object_id, object_item in object_map.items():
        object_payload = object_item.get("payload", {})
        if not isinstance(object_payload, dict):
            continue
        derived_os_caps, effective_os = derive_os_capabilities(
            object_id=object_id,
            object_payload=object_payload,
            catalog_ids=catalog_ids,
            path=f"object:{object_id}",
            emit_diagnostics=False,
        )
        _derived_firmware_caps, _ = derive_firmware_capabilities(
            object_id=object_id,
            object_payload=object_payload,
            catalog_ids=catalog_ids,
            path=f"object:{object_id}",
            emit_diagnostics=False,
        )
        object_derived_caps[object_id] = sorted(derived_os_caps)
        if effective_os:
            object_effective_os[object_id] = effective_os
    return object_derived_caps, object_effective_os


def build_effective(
    *,
    manifest: dict[str, Any],
    topology_manifest_path: str,
    generated_at: str,
    class_map: dict[str, dict[str, Any]],
    object_map: dict[str, dict[str, Any]],
    rows: list[dict[str, Any]],
    object_derived_caps: dict[str, list[str]],
    object_effective_os: dict[str, dict[str, Any]],
    instance_derived_caps: dict[str, list[str]],
    instance_software_refs: dict[str, dict[str, Any]],
    default_firmware_policy: Callable[[str], str],
    compiled_model_version: str,
    compiler_pipeline_version: str,
    source_manifest_digest: str,
) -> dict[str, Any]:
    by_group: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        group = row["group"]
        class_ref = row["class_ref"]
        object_ref = row["object_ref"]
        class_payload = class_map.get(class_ref, {}).get("payload", {})
        object_payload = object_map.get(object_ref, {}).get("payload", {})

        effective_item = {
            "instance": row["instance"],
            "source_id": row.get("source_id", row["instance"]),
            "layer": row.get("layer"),
            "class_ref": class_ref,
            "object_ref": object_ref,
            "status": row.get("status"),
            "notes": row.get("notes"),
            "runtime": row.get("runtime"),
            "class": {
                "version": class_payload.get("version"),
                "os_policy": class_payload.get("os_policy", "allowed"),
                "firmware_policy": class_payload.get("firmware_policy", default_firmware_policy(class_ref)),
                "os_cardinality": class_payload.get("os_cardinality"),
                "multi_boot": class_payload.get("multi_boot", False),
                "required_capabilities": class_payload.get("required_capabilities", []),
                "optional_capabilities": class_payload.get("optional_capabilities", []),
                "capability_packs": class_payload.get("capability_packs", []),
            },
            "object": {
                "version": object_payload.get("version"),
                "enabled_capabilities": object_payload.get("enabled_capabilities", []),
                "enabled_packs": object_payload.get("enabled_packs", []),
                "derived_capabilities": object_derived_caps.get(object_ref, []),
                "vendor_capabilities": object_payload.get("vendor_capabilities", []),
                "vendor": object_payload.get("vendor"),
                "model": object_payload.get("model"),
            },
        }

        software_refs = instance_software_refs.get(row["instance"], {})
        if software_refs:
            effective_item["instance"] = {
                "firmware_ref": software_refs.get("firmware_ref"),
                "os_refs": software_refs.get("os_refs", []),
                "derived_capabilities": instance_derived_caps.get(row["instance"], []),
                "effective_software": software_refs.get("effective", {}),
            }
        effective_os = object_effective_os.get(object_ref)
        if effective_os:
            effective_item["object"]["software"] = {"os": effective_os}
        prerequisites = object_payload.get("prerequisites")
        if isinstance(prerequisites, dict):
            os_ref = prerequisites.get("os_ref")
            if isinstance(os_ref, str) and os_ref:
                effective_item["object"]["prerequisites"] = {"os_ref": os_ref}
        by_group.setdefault(group, []).append(effective_item)

    for group_rows in by_group.values():
        group_rows.sort(key=lambda item: str(item.get("instance", "")))

    class_index = {
        class_id: class_item["payload"] for class_id, class_item in sorted(class_map.items(), key=lambda item: item[0])
    }
    object_index = {
        object_id: object_item["payload"]
        for object_id, object_item in sorted(object_map.items(), key=lambda item: item[0])
    }

    return {
        "version": manifest.get("version", "5.0.0"),
        "model": manifest.get("model", "class-object-instance"),
        "generated_at": generated_at,
        "compiled_model_version": compiled_model_version,
        "compiled_at": generated_at,
        "compiler_pipeline_version": compiler_pipeline_version,
        "source_manifest_digest": source_manifest_digest,
        "topology_manifest": topology_manifest_path,
        "classes": class_index,
        "objects": object_index,
        "instances": by_group,
    }
