#!/usr/bin/env python3
"""Bootstrap v4->v5 mapping inventory for Phase 1 (archive-based v4 baseline)."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate initial v4->v5 mapping inventory.")
    parser.add_argument(
        "--topology",
        default="archive/v4/topology.yaml",
        help="Path to source v4 topology entrypoint (archive baseline).",
    )
    parser.add_argument(
        "--effective-json",
        default="build/diagnostics/v4-phase1-effective-topology.json",
        help="Path to compiled effective topology JSON.",
    )
    parser.add_argument(
        "--output",
        default="projects/home-lab/_legacy/v4-to-v5-mapping.yaml",
        help="Output mapping YAML path.",
    )
    parser.add_argument(
        "--refresh-effective",
        action="store_true",
        help="Recompile v4 topology before generating mapping.",
    )
    return parser.parse_args()


def run_compile(topology: Path, effective_json: Path) -> None:
    cmd = [
        sys.executable,
        str(ROOT / "archive/v4/topology-tools/compile-topology.py"),
        "--topology",
        str(topology),
        "--output-json",
        str(effective_json),
        "--strict-model-lock",
    ]
    print(f"[phase1] RUN: {' '.join(cmd)}", flush=True)
    subprocess.run(cmd, cwd=ROOT, check=True)


def load_existing_mapping(output_path: Path) -> dict:
    if not output_path.exists():
        return {}
    try:
        payload = yaml.safe_load(output_path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError:
        return {}
    if not isinstance(payload, dict):
        return {}
    entities = payload.get("entities")
    if not isinstance(entities, dict):
        return {}
    return entities


def build_existing_index(existing_entities: dict, group: str) -> dict[str, dict]:
    rows = existing_entities.get(group, [])
    if not isinstance(rows, list):
        return {}
    index: dict[str, dict] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        instance_id = row.get("instance_id")
        if isinstance(instance_id, str) and instance_id:
            index[instance_id] = row
    return index


def build_rows(items: list[dict], key: str, existing_index: dict[str, dict]) -> list[dict]:
    rows = []
    seen_ids: set[str] = set()
    for item in sorted(items, key=lambda row: str(row.get(key, ""))):
        instance_id = item.get(key)
        if not isinstance(instance_id, str) or not instance_id:
            continue
        if instance_id in seen_ids:
            continue
        seen_ids.add(instance_id)
        existing_row = existing_index.get(instance_id, {})
        rows.append(
            {
                "instance_id": instance_id,
                "source_id": instance_id,
                "class_ref": existing_row.get("class_ref"),
                "object_ref": existing_row.get("object_ref"),
                "status": existing_row.get("status", "pending"),
                "notes": existing_row.get("notes", ""),
            }
        )
    return rows


def build_l5_rows(items: list[dict], existing_index: dict[str, dict]) -> list[dict]:
    id_counts: dict[str, int] = {}
    for item in items:
        service_id = item.get("id")
        if isinstance(service_id, str) and service_id:
            id_counts[service_id] = id_counts.get(service_id, 0) + 1

    def sort_key(item: dict) -> tuple[str, str, str]:
        runtime = item.get("runtime") or {}
        return (
            str(item.get("id", "")),
            str(runtime.get("type", "")),
            str(runtime.get("target_ref", "")),
        )

    rows = []
    for item in sorted(items, key=sort_key):
        service_id = item.get("id")
        if not isinstance(service_id, str) or not service_id:
            continue
        runtime = item.get("runtime") or {}
        runtime_type = runtime.get("type") if isinstance(runtime.get("type"), str) else "unknown"
        target_ref = runtime.get("target_ref") if isinstance(runtime.get("target_ref"), str) else "unknown"

        if id_counts.get(service_id, 0) > 1:
            instance_id = f"{service_id}@{runtime_type}:{target_ref}"
        else:
            instance_id = service_id

        existing_row = existing_index.get(instance_id)
        if existing_row is None and id_counts.get(service_id, 0) > 1:
            existing_row = existing_index.get(service_id, {})
        if existing_row is None:
            existing_row = {}

        rows.append(
            {
                "instance_id": instance_id,
                "source_id": service_id,
                "runtime_type": runtime_type,
                "runtime_target_ref": target_ref,
                "class_ref": existing_row.get("class_ref"),
                "object_ref": existing_row.get("object_ref"),
                "status": existing_row.get("status", "pending"),
                "notes": existing_row.get("notes", ""),
            }
        )
    return rows


def count_by_status(rows: list[dict]) -> dict[str, int]:
    counters = {"mapped": 0, "pending": 0, "gap": 0}
    for row in rows:
        status = row.get("status")
        if status not in counters:
            counters["pending"] += 1
            continue
        counters[status] += 1
    return counters


def main() -> int:
    args = parse_args()
    topology_path = (ROOT / args.topology).resolve()
    effective_json_path = (ROOT / args.effective_json).resolve()
    output_path = (ROOT / args.output).resolve()

    if args.refresh_effective or not effective_json_path.exists():
        run_compile(topology_path, effective_json_path)

    if not effective_json_path.exists():
        raise FileNotFoundError(f"Compiled topology JSON is missing: {effective_json_path}")

    payload = json.loads(effective_json_path.read_text(encoding="utf-8"))
    l1 = payload.get("L1_foundation", {}) or {}
    l4 = payload.get("L4_platform", {}) or {}
    l5 = payload.get("L5_application", {}) or {}

    existing_entities = load_existing_mapping(output_path)
    devices = build_rows(
        l1.get("devices", []) or [],
        "id",
        build_existing_index(existing_entities, "devices"),
    )
    vms = build_rows(
        l4.get("vms", []) or [],
        "id",
        build_existing_index(existing_entities, "vms"),
    )
    lxc = build_rows(
        l4.get("lxc", []) or [],
        "id",
        build_existing_index(existing_entities, "lxc"),
    )
    services = build_l5_rows(
        l5.get("services", []) or [],
        build_existing_index(existing_entities, "services"),
    )

    output = {
        "schema_version": 1,
        "migration_phase": 1,
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "source": {
            "topology": str(Path(args.topology).as_posix()),
            "effective_json": str(Path(args.effective_json).as_posix()),
        },
        "summary": {
            "devices_total": len(devices),
            "vms_total": len(vms),
            "lxc_total": len(lxc),
            "services_total": len(services),
            "devices_status": count_by_status(devices),
            "vms_status": count_by_status(vms),
            "lxc_status": count_by_status(lxc),
            "services_status": count_by_status(services),
        },
        "entities": {
            "devices": devices,
            "vms": vms,
            "lxc": lxc,
            "services": services,
        },
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        yaml.safe_dump(output, sort_keys=False, allow_unicode=False, default_flow_style=False),
        encoding="utf-8",
    )
    print(f"[phase1] Mapping inventory written: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
