#!/usr/bin/env python3
"""Sync v5 model.lock.yaml from current class/object module files."""

from __future__ import annotations

from pathlib import Path
import sys

import yaml

ROOT = Path(__file__).resolve().parents[2]
TOOLS_ROOT = ROOT / "topology-tools"
sys.path.insert(0, str(TOOLS_ROOT))

from yaml_loader import load_yaml_file

LOCK_PATH = ROOT / "topology/model.lock.yaml"
CLASS_ROOT = ROOT / "topology/class-modules"
OBJECT_ROOT = ROOT / "topology/object-modules"


def _collect_modules(root: Path, key: str) -> list[dict]:
    items: list[dict] = []
    for path in sorted(root.rglob("*.yaml")):
        try:
            payload = load_yaml_file(path) or {}
        except yaml.YAMLError:
            continue
        if isinstance(payload, dict):
            module_id = payload.get(key) or payload.get(f"@{key}")
            if isinstance(module_id, str) and module_id:
                items.append(payload)
    return items


def _module_version(payload: dict) -> str:
    value = payload.get("version") or payload.get("@version") or "1.0.0"
    return str(value)


def _object_class_ref(payload: dict) -> str | None:
    value = payload.get("class_ref") or payload.get("@extends") or payload.get("extends")
    if isinstance(value, str) and value:
        return value
    return None


def main() -> int:
    lock_payload = {}
    if LOCK_PATH.exists():
        lock_payload = yaml.safe_load(LOCK_PATH.read_text(encoding="utf-8")) or {}
        if not isinstance(lock_payload, dict):
            lock_payload = {}

    classes = _collect_modules(CLASS_ROOT, "class")
    objects = _collect_modules(OBJECT_ROOT, "object")

    output = {
        "version": lock_payload.get("version", 1),
        "core_model_version": lock_payload.get("core_model_version", "1.0.0"),
        "classes": {},
        "objects": {},
    }

    for item in sorted(classes, key=lambda entry: entry.get("class") or entry.get("@class")):
        class_id = item.get("class") or item.get("@class")
        if not isinstance(class_id, str) or not class_id:
            continue
        output["classes"][class_id] = {"version": _module_version(item)}

    for item in sorted(objects, key=lambda entry: entry.get("object") or entry.get("@object")):
        object_id = item.get("object") or item.get("@object")
        if not isinstance(object_id, str) or not object_id:
            continue
        class_ref = _object_class_ref(item)
        if class_ref is None:
            continue
        output["objects"][object_id] = {
            "version": _module_version(item),
            "class_ref": class_ref,
        }

    LOCK_PATH.write_text(yaml.safe_dump(output, sort_keys=False, allow_unicode=False), encoding="utf-8")
    print(f"[phase4] Model lock synced: {LOCK_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
