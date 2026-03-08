#!/usr/bin/env python3
"""Export normalized v5 instance bindings from Phase 1 mapping."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
MAPPING_PATH = ROOT / "v5/topology/instances/home-lab/v4-to-v5-mapping.yaml"
OUTPUT_PATH = ROOT / "v5/topology/instances/home-lab/instance-bindings.yaml"
GROUP_LAYER_MAP = {
    "l1_devices": "L1",
    "l1_software_firmware": "L1",
    "l1_software_os": "L1",
    "l4_vms": "L4",
    "l4_lxc": "L4",
    "l5_services": "L5",
}


def _normalize_rows(rows: list[dict], *, group: str, include_runtime: bool = False) -> list[dict]:
    normalized: list[dict] = []
    layer = GROUP_LAYER_MAP[group]
    for row in rows:
        if not isinstance(row, dict):
            continue
        item = {
            "id": row.get("instance_id"),
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
            "l1_software_firmware": _normalize_rows(
                entities.get("l1_software_firmware", []) or [], group="l1_software_firmware"
            ),
            "l1_software_os": _normalize_rows(entities.get("l1_software_os", []) or [], group="l1_software_os"),
            "l4_vms": _normalize_rows(entities.get("l4_vms", []) or [], group="l4_vms"),
            "l4_lxc": _normalize_rows(entities.get("l4_lxc", []) or [], group="l4_lxc"),
            "l5_services": _normalize_rows(
                entities.get("l5_services", []) or [], group="l5_services", include_runtime=True
            ),
        },
    }

    OUTPUT_PATH.write_text(yaml.safe_dump(payload, sort_keys=False, allow_unicode=False), encoding="utf-8")
    print(f"[phase4] Instance bindings exported: {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
