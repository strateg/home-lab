#!/usr/bin/env python3
"""Sync v5 model.lock.yaml from current class/object module files."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
LOCK_PATH = ROOT / "v5/topology/model.lock.yaml"
CLASS_ROOT = ROOT / "v5/topology/class-modules/classes"
OBJECT_ROOT = ROOT / "v5/topology/object-modules"


def _collect_modules(root: Path) -> list[dict]:
    items: list[dict] = []
    for path in sorted(root.rglob("*.yaml")):
        try:
            payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError:
            continue
        if isinstance(payload, dict):
            module_id = payload.get("id")
            if isinstance(module_id, str) and module_id:
                items.append(payload)
    return items


def main() -> int:
    lock_payload = {}
    if LOCK_PATH.exists():
        lock_payload = yaml.safe_load(LOCK_PATH.read_text(encoding="utf-8")) or {}
        if not isinstance(lock_payload, dict):
            lock_payload = {}

    classes = _collect_modules(CLASS_ROOT)
    objects = _collect_modules(OBJECT_ROOT)

    output = {
        "version": lock_payload.get("version", 1),
        "core_model_version": lock_payload.get("core_model_version", "1.0.0"),
        "classes": {},
        "objects": {},
    }

    for item in sorted(classes, key=lambda entry: entry["id"]):
        output["classes"][item["id"]] = {"version": str(item.get("version", "1.0.0"))}

    for item in sorted(objects, key=lambda entry: entry["id"]):
        class_ref = item.get("class_ref")
        if not isinstance(class_ref, str) or not class_ref:
            continue
        output["objects"][item["id"]] = {
            "version": str(item.get("version", "1.0.0")),
            "class_ref": class_ref,
        }

    LOCK_PATH.write_text(yaml.safe_dump(output, sort_keys=False, allow_unicode=False), encoding="utf-8")
    print(f"[phase4] Model lock synced: {LOCK_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
