#!/usr/bin/env python3
"""Refresh Phase 1 module-gap backlog from v4->v5 mapping."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
MAPPING_PATH = ROOT / "v5/topology/instances/_legacy-home-lab/v4-to-v5-mapping.yaml"
BACKLOG_PATH = ROOT / "v5/topology/instances/_legacy-home-lab/phase1-module-backlog.yaml"


def collect_existing_ids(root: Path, key: str) -> set[str]:
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


def main() -> int:
    if not MAPPING_PATH.exists():
        raise FileNotFoundError(f"Mapping file is missing: {MAPPING_PATH}")

    payload = yaml.safe_load(MAPPING_PATH.read_text(encoding="utf-8")) or {}
    entities = payload.get("entities") or {}

    existing_class_ids = collect_existing_ids(ROOT / "v5/topology/class-modules", "class")
    existing_object_ids = collect_existing_ids(ROOT / "v5/topology/object-modules/objects", "object")

    class_gaps: dict[str, set[str]] = defaultdict(set)
    object_gaps: dict[str, set[str]] = defaultdict(set)
    unassigned_refs: dict[str, set[str]] = {"class_ref": set(), "object_ref": set()}

    for group, rows in entities.items():
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, dict):
                continue
            if row.get("status") != "gap":
                continue
            instance_id = row.get("instance_id")
            class_ref = row.get("class_ref")
            object_ref = row.get("object_ref")
            if not isinstance(instance_id, str) or not instance_id:
                continue
            ref = f"{group}:{instance_id}"
            if isinstance(class_ref, str) and class_ref:
                if class_ref not in existing_class_ids:
                    class_gaps[class_ref].add(ref)
            else:
                unassigned_refs["class_ref"].add(ref)
            if isinstance(object_ref, str) and object_ref:
                if object_ref not in existing_object_ids:
                    object_gaps[object_ref].add(ref)
            else:
                unassigned_refs["object_ref"].add(ref)

    backlog = {
        "schema_version": 1,
        "phase": 1,
        "source_mapping": str(MAPPING_PATH.relative_to(ROOT).as_posix()),
        "gaps": {
            "classes": [
                {
                    "class_ref": class_ref,
                    "instances_count": len(refs),
                    "instance_refs": sorted(refs),
                }
                for class_ref, refs in sorted(class_gaps.items(), key=lambda item: (-len(item[1]), item[0]))
            ],
            "objects": [
                {
                    "object_ref": object_ref,
                    "instances_count": len(refs),
                    "instance_refs": sorted(refs),
                }
                for object_ref, refs in sorted(object_gaps.items(), key=lambda item: (-len(item[1]), item[0]))
            ],
            "unassigned": {
                "class_ref": sorted(unassigned_refs["class_ref"]),
                "object_ref": sorted(unassigned_refs["object_ref"]),
            },
        },
    }

    BACKLOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    BACKLOG_PATH.write_text(yaml.safe_dump(backlog, sort_keys=False, allow_unicode=False), encoding="utf-8")
    print(f"[phase1] Backlog refreshed: {BACKLOG_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
