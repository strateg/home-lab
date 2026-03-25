#!/usr/bin/env python3
"""Validate Phase 1 completion gates for v4->v5 mapping."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[2]
MAPPING_PATH = ROOT / "projects/home-lab/_legacy/v4-to-v5-mapping.yaml"
BACKLOG_PATH = ROOT / "projects/home-lab/_legacy/phase1-module-backlog.yaml"
BINDINGS_PATH = ROOT / "projects/home-lab/_legacy/instance-bindings.yaml"
GROUP_LAYER_MAP = {
    "l1_devices": "L1",
    "l1_firmware": "L1",
    "l1_os": "L1",
    "l4_vms": "L4",
    "l4_lxc": "L4",
    "l5_services": "L5",
}


def _load_yaml(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(payload, dict):
        raise ValueError(f"YAML root must be mapping/object: {path}")
    return payload


def _count_status(rows: list[dict[str, Any]]) -> dict[str, int]:
    counters = {"mapped": 0, "pending": 0, "gap": 0}
    for row in rows:
        status = row.get("status")
        if status in counters:
            counters[status] += 1
        else:
            counters["pending"] += 1
    return counters


def _rows_by_id(rows: list[dict[str, Any]], id_key: str) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        item_id = row.get(id_key)
        if isinstance(item_id, str) and item_id:
            result[item_id] = row
    return result


def _validate_binding_rows(
    *,
    group: str,
    rows_any: list[Any],
    errors: list[str],
) -> list[dict[str, Any]]:
    expected_layer = GROUP_LAYER_MAP.get(group)
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for idx, row in enumerate(rows_any):
        path = f"instance-bindings.{group}[{idx}]"
        if not isinstance(row, dict):
            errors.append(f"{path}: row must be object")
            continue
        item_id = row.get("instance")
        if not isinstance(item_id, str) or not item_id:
            errors.append(f"{path}: missing non-empty instance")
            continue
        if item_id in seen:
            errors.append(f"{path}: duplicate instance '{item_id}' in group '{group}'")
        seen.add(item_id)
        layer = row.get("layer")
        if not isinstance(layer, str) or not layer:
            errors.append(f"{path}: missing non-empty layer")
        elif expected_layer is not None and layer != expected_layer:
            errors.append(f"{path}: layer '{layer}' must be '{expected_layer}' for group '{group}'")
        rows.append(row)
    return rows


def _validate_entity_rows(
    *,
    group: str,
    rows: list[dict[str, Any]],
    errors: list[str],
) -> dict[str, int]:
    seen: set[str] = set()
    for idx, row in enumerate(rows):
        path = f"entities.{group}[{idx}]"
        instance_id = row.get("instance_id")
        class_ref = row.get("class_ref")
        object_ref = row.get("object_ref")
        status = row.get("status")

        if not isinstance(instance_id, str) or not instance_id:
            errors.append(f"{path}: missing non-empty instance_id")
            continue
        if instance_id in seen:
            errors.append(f"{path}: duplicate instance_id '{instance_id}' in group '{group}'")
        seen.add(instance_id)

        if not isinstance(class_ref, str) or not class_ref:
            errors.append(f"{path}: missing class_ref")
        if not isinstance(object_ref, str) or not object_ref:
            errors.append(f"{path}: missing object_ref")
        if status not in ("mapped", "pending", "gap"):
            errors.append(f"{path}: invalid status '{status}'")

    return _count_status(rows)


def _validate_bindings_sync(
    *,
    mapping_entities: dict[str, Any],
    bindings_root: dict[str, Any],
    errors: list[str],
) -> None:
    bindings = bindings_root.get("instance_bindings")
    if not isinstance(bindings, dict):
        errors.append("instance-bindings: missing mapping 'instance_bindings'")
        return

    for group, mapping_rows_any in mapping_entities.items():
        if not isinstance(mapping_rows_any, list):
            continue
        binding_rows_any = bindings.get(group, [])
        if not isinstance(binding_rows_any, list):
            errors.append(f"instance-bindings.{group}: must be list")
            continue

        mapping_rows = []
        for idx, row in enumerate(mapping_rows_any):
            if not isinstance(row, dict):
                errors.append(f"mapping.entities.{group}[{idx}]: row must be object")
                continue
            mapping_rows.append(row)

        binding_rows = _validate_binding_rows(group=group, rows_any=binding_rows_any, errors=errors)

        if len(mapping_rows) != len(binding_rows):
            errors.append(
                f"instance-bindings.{group}: row count mismatch mapping={len(mapping_rows)} bindings={len(binding_rows)}"
            )

        mapping_by_id = _rows_by_id(mapping_rows, "instance_id")
        bindings_by_id = _rows_by_id(binding_rows, "instance")
        for instance_id, mrow in mapping_by_id.items():
            brow = bindings_by_id.get(instance_id)
            if brow is None:
                errors.append(f"instance-bindings.{group}: missing row for instance '{instance_id}'")
                continue
            if brow.get("class_ref") != mrow.get("class_ref"):
                errors.append(f"instance-bindings.{group}:{instance_id}: class_ref mismatch")
            if brow.get("object_ref") != mrow.get("object_ref"):
                errors.append(f"instance-bindings.{group}:{instance_id}: object_ref mismatch")
            if brow.get("status") != mrow.get("status"):
                errors.append(f"instance-bindings.{group}:{instance_id}: status mismatch")

        for instance_id in bindings_by_id:
            if instance_id not in mapping_by_id:
                errors.append(
                    f"instance-bindings.{group}: unexpected instance '{instance_id}' (not present in mapping)"
                )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate Phase 1 completion gates.")
    parser.add_argument(
        "--report-json",
        default="",
        help="Optional path for writing machine-readable gate report JSON.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    errors: list[str] = []

    for path in (MAPPING_PATH, BACKLOG_PATH, BINDINGS_PATH):
        if not path.exists():
            errors.append(f"required file is missing: {path.relative_to(ROOT).as_posix()}")
    if errors:
        print("phase1 gate: FAIL")
        for item in errors:
            print(f"- {item}")
        return 1

    mapping = _load_yaml(MAPPING_PATH)
    backlog = _load_yaml(BACKLOG_PATH)
    bindings = _load_yaml(BINDINGS_PATH)

    entities = mapping.get("entities")
    if not isinstance(entities, dict):
        errors.append("mapping: missing mapping key 'entities'")
        entities = {}

    status_summary: dict[str, dict[str, int]] = {}
    total_rows = 0
    for group, rows_any in entities.items():
        if not isinstance(rows_any, list):
            errors.append(f"mapping.entities.{group}: must be list")
            continue
        rows = []
        for idx, row in enumerate(rows_any):
            if not isinstance(row, dict):
                errors.append(f"mapping.entities.{group}[{idx}]: row must be object")
                continue
            rows.append(row)
        total_rows += len(rows)
        status_summary[group] = _validate_entity_rows(group=group, rows=rows, errors=errors)

        if status_summary[group]["pending"] > 0 or status_summary[group]["gap"] > 0:
            errors.append(
                f"mapping.entities.{group}: pending={status_summary[group]['pending']} gap={status_summary[group]['gap']} (must be 0)"
            )

    gaps = backlog.get("gaps")
    if not isinstance(gaps, dict):
        errors.append("backlog: missing mapping key 'gaps'")
        gaps = {}
    classes_gap = gaps.get("classes", [])
    objects_gap = gaps.get("objects", [])
    unassigned = gaps.get("unassigned", {})
    unassigned_class = unassigned.get("class_ref", []) if isinstance(unassigned, dict) else []
    unassigned_object = unassigned.get("object_ref", []) if isinstance(unassigned, dict) else []

    if classes_gap:
        errors.append(f"backlog: classes gap is not empty ({len(classes_gap)})")
    if objects_gap:
        errors.append(f"backlog: objects gap is not empty ({len(objects_gap)})")
    if unassigned_class:
        errors.append(f"backlog: unassigned class_ref is not empty ({len(unassigned_class)})")
    if unassigned_object:
        errors.append(f"backlog: unassigned object_ref is not empty ({len(unassigned_object)})")

    _validate_bindings_sync(mapping_entities=entities, bindings_root=bindings, errors=errors)

    report = {
        "phase": 1,
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "inputs": {
            "mapping": str(MAPPING_PATH.relative_to(ROOT).as_posix()),
            "backlog": str(BACKLOG_PATH.relative_to(ROOT).as_posix()),
            "bindings": str(BINDINGS_PATH.relative_to(ROOT).as_posix()),
        },
        "summary": {
            "total_entities": total_rows,
            "status_by_group": status_summary,
            "classes_gap": len(classes_gap) if isinstance(classes_gap, list) else None,
            "objects_gap": len(objects_gap) if isinstance(objects_gap, list) else None,
            "unassigned_class_ref": len(unassigned_class) if isinstance(unassigned_class, list) else None,
            "unassigned_object_ref": len(unassigned_object) if isinstance(unassigned_object, list) else None,
        },
        "ok": not errors,
        "error_count": len(errors),
        "errors": errors,
    }

    if args.report_json:
        report_path = Path(args.report_json)
        if not report_path.is_absolute():
            report_path = ROOT / report_path
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, ensure_ascii=True, indent=2), encoding="utf-8")
        print(f"[phase1] gate report: {report_path}")

    if errors:
        print("phase1 gate: FAIL")
        for item in errors:
            print(f"- {item}")
        return 1

    print("phase1 gate: PASS")
    print(f"total_entities={total_rows}")
    for group, counters in status_summary.items():
        print(f"{group}: mapped={counters['mapped']} pending={counters['pending']} gap={counters['gap']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
