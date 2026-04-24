#!/usr/bin/env python3
"""Generate class->object->instance layer derivation audit report."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "topology-tools"))

from layer_derivation import load_class_layer_map, load_object_layer_map
from semantic_keywords import load_semantic_keyword_registry, resolve_semantic_value
from yaml_loader import load_yaml_file


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate layer derivation audit report.")
    parser.add_argument("--repo-root", type=Path, default=ROOT, help="Repository root path.")
    parser.add_argument(
        "--topology",
        default="topology/topology.yaml",
        help="Topology manifest path (relative to repo root by default).",
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        default=ROOT / "build" / "diagnostics" / "layer-derivation-report.json",
        help="Output JSON report path.",
    )
    parser.add_argument(
        "--output-txt",
        type=Path,
        default=ROOT / "build" / "diagnostics" / "layer-derivation-report.txt",
        help="Output text report path.",
    )
    parser.add_argument(
        "--enforce",
        action="store_true",
        help="Exit non-zero when violations are detected.",
    )
    return parser.parse_args()


def _iter_yaml_files(root: Path, prefix: str) -> list[Path]:
    if not root.exists() or not root.is_dir():
        return []
    return sorted(path for path in root.rglob("*.yaml") if path.is_file() and path.name.startswith(prefix))


def _resolve_path(base: Path, raw: Any) -> Path:
    if not isinstance(raw, str) or not raw.strip():
        return base
    value = Path(raw)
    if value.is_absolute():
        return value
    return base / value


def _instance_rows(instances_root: Path) -> list[tuple[str, dict[str, Any]]]:
    rows: list[tuple[str, dict[str, Any]]] = []
    if not instances_root.exists() or not instances_root.is_dir():
        return rows
    for path in sorted(p for p in instances_root.rglob("*.yaml") if p.is_file()):
        rel = path.relative_to(instances_root)
        if any(part.startswith("_") for part in rel.parts):
            continue
        if path.name in {"project.yaml", "instance-bindings.yaml"}:
            continue
        payload = load_yaml_file(path) or {}
        if isinstance(payload, dict):
            rows.append((rel.as_posix(), payload))
    return rows


def main() -> int:
    args = _parse_args()
    repo_root = args.repo_root.resolve()
    topology_path = _resolve_path(repo_root, args.topology).resolve()
    output_json = args.output_json.resolve() if args.output_json.is_absolute() else (repo_root / args.output_json).resolve()
    output_txt = args.output_txt.resolve() if args.output_txt.is_absolute() else (repo_root / args.output_txt).resolve()

    manifest = load_yaml_file(topology_path) or {}
    if not isinstance(manifest, dict):
        print("layer-derivation-report: invalid topology manifest")
        return 2

    framework = manifest.get("framework", {}) if isinstance(manifest.get("framework"), dict) else {}
    project = manifest.get("project", {}) if isinstance(manifest.get("project"), dict) else {}

    class_root = _resolve_path(repo_root, framework.get("class_modules_root", "topology/class-modules")).resolve()
    object_root = _resolve_path(repo_root, framework.get("object_modules_root", "topology/object-modules")).resolve()
    semantic_path = _resolve_path(repo_root, framework.get("semantic_keywords", "topology/semantic-keywords.yaml")).resolve()

    project_id = project.get("active")
    projects_root = _resolve_path(repo_root, project.get("projects_root", "projects")).resolve()
    project_manifest_path = projects_root / str(project_id or "") / "project.yaml"
    project_manifest = load_yaml_file(project_manifest_path) or {}
    instances_root = projects_root / str(project_id or "") / str(project_manifest.get("instances_root", "topology/instances"))

    semantic_registry = load_semantic_keyword_registry(semantic_path)
    class_layer_map = load_class_layer_map(class_modules_root=class_root, semantic_registry=semantic_registry)
    object_layer_map = load_object_layer_map(
        object_modules_root=object_root,
        semantic_registry=semantic_registry,
        class_layer_map=class_layer_map,
    )

    violations: list[dict[str, str]] = []
    objects_with_declared_layer = 0
    object_files = _iter_yaml_files(object_root, "obj.")
    for path in object_files:
        payload = load_yaml_file(path) or {}
        if not isinstance(payload, dict):
            continue
        object_id_res = resolve_semantic_value(payload, registry=semantic_registry, context="entity_manifest", token="object_id")
        class_ref_res = resolve_semantic_value(payload, registry=semantic_registry, context="entity_manifest", token="parent_ref")
        object_id = str(object_id_res.value) if object_id_res.found else "<unknown>"
        class_ref = str(class_ref_res.value) if class_ref_res.found else "<unknown>"
        if "@layer" in payload:
            objects_with_declared_layer += 1
            violations.append(
                {
                    "code": "LDR001",
                    "message": f"object '{object_id}' must not declare @layer",
                    "path": path.relative_to(repo_root).as_posix(),
                }
            )
        if class_ref != "<unknown>" and class_ref not in class_layer_map:
            violations.append(
                {
                    "code": "LDR002",
                    "message": f"object '{object_id}' references class '{class_ref}' without resolvable @layer",
                    "path": path.relative_to(repo_root).as_posix(),
                }
            )

    instances_total = 0
    instances_with_explicit_layer = 0
    instance_explicit_mismatch = 0
    for rel, payload in _instance_rows(instances_root):
        instances_total += 1
        if not isinstance(payload, dict):
            continue
        instance_res = resolve_semantic_value(payload, registry=semantic_registry, context="entity_manifest", token="instance_id")
        object_res = resolve_semantic_value(payload, registry=semantic_registry, context="entity_manifest", token="parent_ref")
        layer_res = resolve_semantic_value(payload, registry=semantic_registry, context="entity_manifest", token="entity_layer")
        instance_id = str(instance_res.value) if instance_res.found else "<unknown>"
        object_ref = str(object_res.value) if object_res.found else "<unknown>"
        derived_layer = object_layer_map.get(object_ref)
        if derived_layer is None:
            violations.append(
                {
                    "code": "LDR003",
                    "message": f"instance '{instance_id}' cannot derive layer from object '{object_ref}'",
                    "path": f"{instances_root.relative_to(repo_root).as_posix()}/{rel}",
                }
            )
            continue
        if layer_res.found:
            instances_with_explicit_layer += 1
            explicit = layer_res.value
            if explicit != derived_layer:
                instance_explicit_mismatch += 1
                violations.append(
                    {
                        "code": "LDR004",
                        "message": f"instance '{instance_id}' explicit @layer '{explicit}' conflicts with derived '{derived_layer}'",
                        "path": f"{instances_root.relative_to(repo_root).as_posix()}/{rel}",
                    }
                )

    report = {
        "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat(),
        "topology": topology_path.relative_to(repo_root).as_posix(),
        "summary": {
            "classes_total": len(class_layer_map),
            "objects_total": len(object_files),
            "objects_with_declared_layer": objects_with_declared_layer,
            "objects_resolved_layers": len(object_layer_map),
            "instances_total": instances_total,
            "instances_with_explicit_layer": instances_with_explicit_layer,
            "instance_explicit_mismatch": instance_explicit_mismatch,
            "violations": len(violations),
        },
        "violations": violations,
    }

    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "Layer Derivation Report",
        "=======================",
        f"generated_at: {report['generated_at']}",
        f"topology: {report['topology']}",
        "",
        "Summary:",
    ]
    for key, value in report["summary"].items():
        lines.append(f"- {key}: {value}")
    if violations:
        lines.append("")
        lines.append("Violations:")
        for item in violations:
            lines.append(f"- [{item['code']}] {item['message']} ({item['path']})")
    output_txt.parent.mkdir(parents=True, exist_ok=True)
    output_txt.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"[layer-derivation] report json: {output_json}")
    print(f"[layer-derivation] report txt:  {output_txt}")
    if violations and args.enforce:
        print(f"[layer-derivation] FAIL: violations={len(violations)}")
        return 1
    print(f"[layer-derivation] PASS: violations={len(violations)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

