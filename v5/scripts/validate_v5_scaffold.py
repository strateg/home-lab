#!/usr/bin/env python3
"""Validate Phase 0 v5 scaffold integrity."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]

REQUIRED_PATHS = (
    "v5/topology/topology.yaml",
    "v5/topology",
    "v5/topology/class-modules",
    "v5/topology/object-modules",
    "v5/topology/instances/home-lab",
    "v5/topology-tools",
    "v5/tests",
    "v5/topology/model.lock.yaml",
    "v5-generated",
    "v5-build",
    "v5-dist",
)


def check_required_paths(errors: list[dict[str, str]]) -> None:
    for relative_path in REQUIRED_PATHS:
        path = ROOT / relative_path
        if not path.exists():
            errors.append(
                {
                    "code": "V5_PATH_MISSING",
                    "path": relative_path,
                    "message": f"Required path is missing: {relative_path}",
                }
            )


def check_yaml_syntax(errors: list[dict[str, str]]) -> None:
    for yaml_file in sorted((ROOT / "v5/topology").rglob("*.yaml")):
        try:
            yaml.safe_load(yaml_file.read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            errors.append(
                {
                    "code": "V5_YAML_PARSE_ERROR",
                    "path": str(yaml_file.relative_to(ROOT)),
                    "message": f"YAML parsing failed: {exc}",
                }
            )


def check_model_lock_shape(errors: list[dict[str, str]]) -> None:
    lock_file = ROOT / "v5/topology/model.lock.yaml"
    if not lock_file.exists():
        return

    try:
        payload = yaml.safe_load(lock_file.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError:
        return

    if not isinstance(payload, dict):
        errors.append(
            {
                "code": "V5_LOCK_INVALID_ROOT",
                "path": "v5/topology/model.lock.yaml",
                "message": "model.lock.yaml root must be a mapping/object.",
            }
        )
        return

    required_keys = ("core_model_version", "classes", "objects")
    for key in required_keys:
        if key not in payload:
            errors.append(
                {
                    "code": "V5_LOCK_MISSING_KEY",
                    "path": "v5/topology/model.lock.yaml",
                    "message": f"model.lock.yaml is missing required key: {key}",
                }
            )


def check_topology_manifest(errors: list[dict[str, str]]) -> None:
    manifest_file = ROOT / "v5/topology/topology.yaml"
    if not manifest_file.exists():
        return

    try:
        payload = yaml.safe_load(manifest_file.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        errors.append(
            {
                "code": "V5_MANIFEST_PARSE_ERROR",
                "path": "v5/topology/topology.yaml",
                "message": f"topology manifest parsing failed: {exc}",
            }
        )
        return

    if not isinstance(payload, dict):
        errors.append(
            {
                "code": "V5_MANIFEST_INVALID_ROOT",
                "path": "v5/topology/topology.yaml",
                "message": "topology manifest root must be a mapping/object.",
            }
        )
        return

    paths = payload.get("paths")
    if not isinstance(paths, dict):
        errors.append(
            {
                "code": "V5_MANIFEST_MISSING_PATHS",
                "path": "v5/topology/topology.yaml",
                "message": "topology manifest must contain 'paths' mapping.",
            }
        )
        return

    for key, rel_path in paths.items():
        if not isinstance(rel_path, str) or not rel_path:
            errors.append(
                {
                    "code": "V5_MANIFEST_INVALID_PATH_VALUE",
                    "path": "v5/topology/topology.yaml",
                    "message": f"path entry '{key}' must be non-empty string.",
                }
            )
            continue
        if not (ROOT / rel_path).exists():
            errors.append(
                {
                    "code": "V5_MANIFEST_PATH_MISSING",
                    "path": "v5/topology/topology.yaml",
                    "message": f"path entry '{key}' points to missing path: {rel_path}",
                }
            )


def main() -> int:
    errors: list[dict[str, str]] = []

    check_required_paths(errors)
    check_yaml_syntax(errors)
    check_model_lock_shape(errors)
    check_topology_manifest(errors)

    if errors:
        print("v5 scaffold validation: FAIL")
        print(json.dumps({"errors": errors}, ensure_ascii=True, indent=2))
        return 1

    print("v5 scaffold validation: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
