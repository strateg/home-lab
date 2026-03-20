#!/usr/bin/env python3
"""Split legacy instance-bindings.yaml into ADR0071 sharded instance files."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from identifier_policy import contains_unsafe_identifier_chars, normalize_identifier_for_filename

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT = REPO_ROOT / "v5" / "projects" / "home-lab" / "_legacy" / "instance-bindings.yaml"
DEFAULT_OUTPUT_ROOT = REPO_ROOT / "v5" / "topology" / "instances"
DEFAULT_PROJECT_FILE = DEFAULT_OUTPUT_ROOT / "project.yaml"


def _load_yaml(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(payload, dict):
        raise ValueError(f"expected mapping/object at YAML root: {path}")
    return payload


def _normalize_instance_id(*, instance_id: str, allow_sanitize: bool) -> tuple[str, bool]:
    candidate = normalize_identifier_for_filename(instance_id)
    changed = candidate != instance_id
    if changed and not allow_sanitize:
        raise ValueError(
            f"instance id '{instance_id}' contains filename-unsafe characters; "
            "rerun with --sanitize-instance-ids or rename the instance id."
        )
    if contains_unsafe_identifier_chars(candidate):
        raise ValueError(f"instance id '{instance_id}' cannot be normalized safely")
    if not candidate:
        raise ValueError(f"instance id '{instance_id}' cannot be normalized to non-empty filename")
    return candidate, changed


def _sanitize_row(
    *,
    group_name: str,
    row: dict[str, Any],
    drop_class_ref: bool,
    sanitize_instance_ids: bool,
    rewrite_map: dict[str, str],
) -> dict[str, Any]:
    instance_id_raw = row.get("instance")
    instance_id = instance_id_raw
    if not isinstance(instance_id, str) or not instance_id:
        raise ValueError(f"group '{group_name}' contains row without non-empty 'instance'")
    normalized_instance_id, changed = _normalize_instance_id(
        instance_id=instance_id,
        allow_sanitize=sanitize_instance_ids,
    )
    if changed:
        rewrite_map[instance_id] = normalized_instance_id

    payload: dict[str, Any] = {
        "instance": normalized_instance_id,
        "object_ref": row.get("object_ref"),
        "group": group_name,
        "layer": row.get("layer"),
        "version": "1.0.0",
    }
    if not drop_class_ref and isinstance(row.get("class_ref"), str) and row.get("class_ref"):
        payload["class_ref"] = row["class_ref"]

    for key, value in row.items():
        if key in {"instance", "class_ref", "layer", "object_ref"}:
            continue
        payload[key] = value

    return payload


def _write_shards(
    *,
    bindings: dict[str, Any],
    output_root: Path,
    drop_class_ref: bool,
    sanitize_instance_ids: bool,
    force: bool,
) -> tuple[int, dict[str, str]]:
    instance_bindings = bindings.get("instance_bindings")
    if not isinstance(instance_bindings, dict):
        raise ValueError("legacy file must contain mapping key 'instance_bindings'")

    rewrite_map: dict[str, str] = {}
    count = 0
    for group_name in sorted(instance_bindings):
        group_rows = instance_bindings[group_name]
        if not isinstance(group_name, str) or not group_name:
            raise ValueError("group name must be non-empty string")
        if not isinstance(group_rows, list):
            raise ValueError(f"instance_bindings.{group_name} must be a list")

        group_dir = output_root / group_name
        group_dir.mkdir(parents=True, exist_ok=True)

        for row in group_rows:
            if not isinstance(row, dict):
                raise ValueError(f"instance_bindings.{group_name} contains non-object row")
            shard_payload = _sanitize_row(
                group_name=group_name,
                row=row,
                drop_class_ref=drop_class_ref,
                sanitize_instance_ids=sanitize_instance_ids,
                rewrite_map=rewrite_map,
            )
            instance_id = shard_payload["instance"]
            target = group_dir / f"{instance_id}.yaml"
            if target.exists() and not force:
                raise FileExistsError(f"target already exists: {target}")
            target.write_text(
                yaml.safe_dump(shard_payload, sort_keys=False, allow_unicode=False),
                encoding="utf-8",
            )
            count += 1
    return count, rewrite_map


def _write_project_file(
    *,
    bindings: dict[str, Any],
    source_path: Path,
    target_path: Path,
    force: bool,
) -> None:
    if target_path.exists() and not force:
        raise FileExistsError(f"project file already exists: {target_path}")

    try:
        migrated_from = source_path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        migrated_from = str(source_path)

    payload = {
        "schema_version": 1,
        "project": "home-lab",
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "migrated_from": migrated_from,
        "legacy_metadata": {
            "generated_at": bindings.get("generated_at"),
            "source_mapping": bindings.get("source_mapping"),
        },
    }
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text(yaml.safe_dump(payload, sort_keys=False, allow_unicode=False), encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input",
        default=str(DEFAULT_INPUT.relative_to(REPO_ROOT).as_posix()),
        help="Path to legacy instance-bindings.yaml file.",
    )
    parser.add_argument(
        "--output-root",
        default=str(DEFAULT_OUTPUT_ROOT.relative_to(REPO_ROOT).as_posix()),
        help="Root directory for shard files (group/<instance>.yaml).",
    )
    parser.add_argument(
        "--project-file",
        default=str(DEFAULT_PROJECT_FILE.relative_to(REPO_ROOT).as_posix()),
        help="Project metadata file path to create/update.",
    )
    parser.add_argument(
        "--keep-class-ref",
        action="store_true",
        help="Keep class_ref in generated shards (default: dropped).",
    )
    parser.add_argument(
        "--sanitize-instance-ids",
        action="store_true",
        help="Normalize filename-unsafe instance ids (e.g. ':' -> '.') to make shard filenames valid.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing shard and project files.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    source_path = (REPO_ROOT / args.input).resolve() if not Path(args.input).is_absolute() else Path(args.input)
    output_root = (
        (REPO_ROOT / args.output_root).resolve() if not Path(args.output_root).is_absolute() else Path(args.output_root)
    )
    project_file = (
        (REPO_ROOT / args.project_file).resolve()
        if not Path(args.project_file).is_absolute()
        else Path(args.project_file)
    )

    bindings = _load_yaml(source_path)
    shard_count, rewrite_map = _write_shards(
        bindings=bindings,
        output_root=output_root,
        drop_class_ref=not args.keep_class_ref,
        sanitize_instance_ids=args.sanitize_instance_ids,
        force=args.force,
    )
    _write_project_file(
        bindings=bindings,
        source_path=source_path,
        target_path=project_file,
        force=args.force,
    )
    print(f"Shards written: {shard_count}")
    print(f"Project metadata: {project_file}")
    if rewrite_map:
        print("Instance ID rewrites:")
        for old_id, new_id in sorted(rewrite_map.items()):
            print(f"  - {old_id} -> {new_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
