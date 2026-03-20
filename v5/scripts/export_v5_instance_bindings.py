#!/usr/bin/env python3
"""Export normalized v5 instance bindings from Phase 1 mapping."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
MAPPING_PATH = ROOT / "v5/topology/instances/_legacy-home-lab/v4-to-v5-mapping.yaml"
OUTPUT_PATH = ROOT / "v5/topology/instances/_legacy-home-lab/instance-bindings.yaml"
GROUP_LAYER_MAP = {
    "l1_devices": "L1",
    "l1_firmware": "L1",
    "l1_os": "L1",
    "l2_network": "L2",
    "l3_storage": "L3",
    "l4_vms": "L4",
    "l4_lxc": "L4",
    "l5_services": "L5",
    "l6_observability": "L6",
    "l7_operations": "L7",
}


def _normalize_rows(rows: list[dict], *, group: str, include_runtime: bool = False) -> list[dict]:
    normalized: list[dict] = []
    layer = GROUP_LAYER_MAP[group]
    for row in rows:
        if not isinstance(row, dict):
            continue
        item = {
            "instance": row.get("instance_id"),
            "source_id": row.get("source_id", row.get("instance_id")),
            "layer": layer,
            "class_ref": row.get("class_ref"),
            "object_ref": row.get("object_ref"),
            "status": row.get("status", "pending"),
            "notes": row.get("notes", ""),
        }
        firmware_ref = row.get("firmware_ref")
        if isinstance(firmware_ref, str) and firmware_ref:
            item["firmware_ref"] = firmware_ref
        os_refs = row.get("os_refs")
        if isinstance(os_refs, list):
            item["os_refs"] = [value for value in os_refs if isinstance(value, str) and value]
        # ADR 0064: embedded_in for embedded OS instances
        embedded_in = row.get("embedded_in")
        if isinstance(embedded_in, str) and embedded_in:
            item["embedded_in"] = embedded_in
        # L2 network fields
        for ref_field in ("host_ref", "bridge_ref", "trust_zone_ref", "managed_by_ref"):
            ref_value = row.get(ref_field)
            if isinstance(ref_value, str) and ref_value:
                item[ref_field] = ref_value
        if include_runtime:
            item["runtime"] = {
                "type": row.get("runtime_type"),
                "target_ref": row.get("runtime_target_ref"),
            }
        normalized.append(item)
    return normalized


def main() -> int:
    if not MAPPING_PATH.exists():
        raise FileNotFoundError(f"Mapping file is missing: {MAPPING_PATH}")

    mapping = yaml.safe_load(MAPPING_PATH.read_text(encoding="utf-8")) or {}
    entities = mapping.get("entities") or {}

    payload = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "source_mapping": str(MAPPING_PATH.relative_to(ROOT).as_posix()),
        "instance_bindings": {
            "l1_devices": _normalize_rows(entities.get("l1_devices", []) or [], group="l1_devices"),
            "l1_firmware": _normalize_rows(
                entities.get("l1_firmware", []) or [], group="l1_firmware"
            ),
            "l1_os": _normalize_rows(entities.get("l1_os", []) or [], group="l1_os"),
            "l2_network": _normalize_rows(entities.get("l2_network", []) or [], group="l2_network"),
            "l3_storage": _normalize_rows(entities.get("l3_storage", []) or [], group="l3_storage"),
            "l4_vms": _normalize_rows(entities.get("l4_vms", []) or [], group="l4_vms"),
            "l4_lxc": _normalize_rows(entities.get("l4_lxc", []) or [], group="l4_lxc"),
            "l5_services": _normalize_rows(
                entities.get("l5_services", []) or [], group="l5_services", include_runtime=True
            ),
            "l6_observability": _normalize_rows(entities.get("l6_observability", []) or [], group="l6_observability"),
            "l7_operations": _normalize_rows(entities.get("l7_operations", []) or [], group="l7_operations"),
        },
    }

    OUTPUT_PATH.write_text(yaml.safe_dump(payload, sort_keys=False, allow_unicode=False), encoding="utf-8")
    print(f"[phase4] Instance bindings exported: {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
