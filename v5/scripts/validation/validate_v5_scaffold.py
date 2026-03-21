#!/usr/bin/env python3
"""Validate Phase 0 v5 scaffold integrity."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]

REQUIRED_PATHS = (
    "v5/topology/topology.yaml",
    "v5/topology",
    "v5/topology/class-modules",
    "v5/topology/object-modules",
    "v5/projects",
    "v5/topology-tools",
    "v5/tests",
    "v5/topology/model.lock.yaml",
    "v5/topology/layer-contract.yaml",
    "v5-generated",
    "v5-build",
    "v5-dist",
)
REQUIRED_FRAMEWORK_KEYS = (
    "class_modules_root",
    "object_modules_root",
    "model_lock",
    "layer_contract",
    "capability_catalog",
    "capability_packs",
)
REQUIRED_PROJECT_KEYS = ("active", "projects_root")
REQUIRED_PROJECT_MANIFEST_KEYS = ("instances_root", "secrets_root")


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

    if "paths" in payload:
        errors.append(
            {
                "code": "E7808",
                "path": "v5/topology/topology.yaml:paths",
                "message": "Legacy manifest contract section 'paths' is unsupported in strict-only mode.",
            }
        )
        return

    framework = payload.get("framework")
    if not isinstance(framework, dict):
        errors.append(
            {
                "code": "V5_MANIFEST_MISSING_FRAMEWORK",
                "path": "v5/topology/topology.yaml",
                "message": "topology manifest must contain 'framework' mapping.",
            }
        )
        return

    project = payload.get("project")
    if not isinstance(project, dict):
        errors.append(
            {
                "code": "V5_MANIFEST_MISSING_PROJECT",
                "path": "v5/topology/topology.yaml",
                "message": "topology manifest must contain 'project' mapping.",
            }
        )
        return

    for key in REQUIRED_FRAMEWORK_KEYS:
        rel_path = framework.get(key)
        if not isinstance(rel_path, str) or not rel_path.strip():
            errors.append(
                {
                    "code": "V5_MANIFEST_INVALID_PATH_VALUE",
                    "path": "v5/topology/topology.yaml",
                    "message": f"framework entry '{key}' must be non-empty string.",
                }
            )
            continue
        if not (ROOT / rel_path).exists():
            errors.append(
                {
                    "code": "V5_MANIFEST_PATH_MISSING",
                    "path": "v5/topology/topology.yaml",
                    "message": f"framework entry '{key}' points to missing path: {rel_path}",
                }
            )

    for key in REQUIRED_PROJECT_KEYS:
        value = project.get(key)
        if not isinstance(value, str) or not value.strip():
            errors.append(
                {
                    "code": "V5_MANIFEST_INVALID_PATH_VALUE",
                    "path": "v5/topology/topology.yaml",
                    "message": f"project entry '{key}' must be non-empty string.",
                }
            )
    active = project.get("active")
    projects_root = project.get("projects_root")
    if not isinstance(active, str) or not active.strip():
        return
    if not isinstance(projects_root, str) or not projects_root.strip():
        return

    projects_root_path = ROOT / projects_root
    if not projects_root_path.exists():
        errors.append(
            {
                "code": "V5_MANIFEST_PATH_MISSING",
                "path": "v5/topology/topology.yaml",
                "message": f"project.projects_root points to missing path: {projects_root}",
            }
        )
        return
    project_root = projects_root_path / active
    project_manifest = project_root / "project.yaml"
    if not project_manifest.exists():
        errors.append(
            {
                "code": "V5_MANIFEST_PATH_MISSING",
                "path": "v5/topology/topology.yaml",
                "message": f"project manifest is missing: {project_manifest.relative_to(ROOT).as_posix()}",
            }
        )
        return

    try:
        project_payload = yaml.safe_load(project_manifest.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        errors.append(
            {
                "code": "V5_MANIFEST_PARSE_ERROR",
                "path": str(project_manifest.relative_to(ROOT).as_posix()),
                "message": f"project manifest parsing failed: {exc}",
            }
        )
        return
    if not isinstance(project_payload, dict):
        errors.append(
            {
                "code": "V5_MANIFEST_INVALID_ROOT",
                "path": str(project_manifest.relative_to(ROOT).as_posix()),
                "message": "project manifest root must be a mapping/object.",
            }
        )
        return

    declared_project = project_payload.get("project")
    if isinstance(declared_project, str) and declared_project and declared_project != active:
        errors.append(
            {
                "code": "V5_MANIFEST_INVALID_PATH_VALUE",
                "path": str(project_manifest.relative_to(ROOT).as_posix()),
                "message": f"project manifest project '{declared_project}' does not match active '{active}'.",
            }
        )

    for key in REQUIRED_PROJECT_MANIFEST_KEYS:
        rel_path = project_payload.get(key)
        if not isinstance(rel_path, str) or not rel_path.strip():
            errors.append(
                {
                    "code": "V5_MANIFEST_INVALID_PATH_VALUE",
                    "path": str(project_manifest.relative_to(ROOT).as_posix()),
                    "message": f"project manifest key '{key}' must be non-empty string.",
                }
            )
            continue
        candidate = (project_root / rel_path).resolve()
        if not candidate.exists():
            errors.append(
                {
                    "code": "V5_MANIFEST_PATH_MISSING",
                    "path": str(project_manifest.relative_to(ROOT).as_posix()),
                    "message": f"project manifest key '{key}' points to missing path: {candidate}",
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
