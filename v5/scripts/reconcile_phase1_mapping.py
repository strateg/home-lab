#!/usr/bin/env python3
"""Reconcile Phase 1 mapping status from available class/object modules."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
MAPPING_PATH = ROOT / "v5/projects/home-lab/_legacy/v4-to-v5-mapping.yaml"
CLASS_ROOT = ROOT / "v5/topology/class-modules"
OBJECT_ROOT = ROOT / "v5/topology/object-modules"


def collect_ids(root: Path, key: str) -> set[str]:
    ids: set[str] = set()
    for path in sorted(root.rglob("*.yaml")):
        try:
            payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError:
            continue
        if isinstance(payload, dict):
            item_id = payload.get(key)
            if isinstance(item_id, str) and item_id:
                ids.add(item_id)
    return ids


def count(rows: list[dict]) -> dict[str, int]:
    counters = {"mapped": 0, "pending": 0, "gap": 0}
    for row in rows:
        status = row.get("status")
        if status in counters:
            counters[status] += 1
        else:
            counters["pending"] += 1
    return counters


def main() -> int:
    if not MAPPING_PATH.exists():
        raise FileNotFoundError(f"Mapping file is missing: {MAPPING_PATH}")

    payload = yaml.safe_load(MAPPING_PATH.read_text(encoding="utf-8")) or {}
    entities = payload.get("entities") or {}

    class_ids = collect_ids(CLASS_ROOT, "class")
    object_ids = collect_ids(OBJECT_ROOT, "object")

    for _, rows in entities.items():
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, dict):
                continue
            class_ref = row.get("class_ref")
            object_ref = row.get("object_ref")

            if not class_ref or not object_ref:
                row["status"] = "pending"
                continue

            class_exists = class_ref in class_ids
            object_exists = object_ref in object_ids
            if class_exists and object_exists:
                row["status"] = "mapped"
            else:
                row["status"] = "gap"

    summary = payload.setdefault("summary", {})
    summary["l1_devices_status"] = count(entities.get("l1_devices", []))
    summary["l4_vms_status"] = count(entities.get("l4_vms", []))
    summary["l4_lxc_status"] = count(entities.get("l4_lxc", []))
    summary["l5_services_status"] = count(entities.get("l5_services", []))

    MAPPING_PATH.write_text(yaml.safe_dump(payload, sort_keys=False, allow_unicode=False), encoding="utf-8")
    print(f"[phase1] Mapping reconciled: {MAPPING_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
