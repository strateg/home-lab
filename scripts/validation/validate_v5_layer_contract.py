#!/usr/bin/env python3
"""Validate v5 L0-L7 layer contract across class/object/instance bindings."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[2]
TOOLS_ROOT = ROOT / "topology-tools"
sys.path.insert(0, str(TOOLS_ROOT))

from yaml_loader import load_yaml_file

DEFAULT_MANIFEST = ROOT / "topology/topology.yaml"
DEFAULT_VALID_LAYERS = ("L0", "L1", "L2", "L3", "L4", "L5", "L6", "L7")
LAYER_BUCKETS = {
    "L0": "L0-meta",
    "L1": "L1-foundation",
    "L2": "L2-network",
    "L3": "L3-data",
    "L4": "L4-platform",
    "L5": "L5-application",
    "L6": "L6-observability",
    "L7": "L7-operations",
}
LEGACY_INSTANCE_BUCKETS = tuple(LAYER_BUCKETS.values())


def _is_planned_status(value: Any) -> bool:
    return isinstance(value, str) and value.lower() in {"planned", "deferred"}


def _load_yaml_map(path: Path, *, errors: list[str]) -> dict[str, Any]:
    if not path.exists():
        errors.append(f"missing file: {path.relative_to(ROOT).as_posix()}")
        return {}
    try:
        payload = load_yaml_file(path) or {}
    except yaml.YAMLError as exc:
        errors.append(f"yaml parse error in {path.relative_to(ROOT).as_posix()}: {exc}")
        return {}
    if not isinstance(payload, dict):
        errors.append(f"yaml root must be object: {path.relative_to(ROOT).as_posix()}")
        return {}
    return payload


def _normalize_layers(value: Any, *, path: str, valid_layers: set[str], errors: list[str]) -> list[str]:
    if not isinstance(value, list) or not value:
        errors.append(f"{path}: expected non-empty list of layers")
        return []
    layers: list[str] = []
    seen: set[str] = set()
    for idx, item in enumerate(value):
        item_path = f"{path}[{idx}]"
        if not isinstance(item, str) or not item:
            errors.append(f"{item_path}: layer must be non-empty string")
            continue
        if item not in valid_layers:
            errors.append(f"{item_path}: unknown layer '{item}'")
            continue
        if item in seen:
            errors.append(f"{item_path}: duplicate layer '{item}'")
            continue
        seen.add(item)
        layers.append(item)
    return layers


def _iter_yaml_files(directory: Path) -> list[Path]:
    if not directory.exists():
        return []
    return sorted(path for path in directory.rglob("*.yaml") if path.is_file())


def _load_instance_bindings_from_shards(instances_root: Path, *, errors: list[str]) -> dict[str, Any]:
    if not instances_root.exists():
        errors.append(f"missing directory: {instances_root.relative_to(ROOT).as_posix()}")
        return {}
    grouped: dict[str, list[dict[str, Any]]] = {}
    for path in _iter_yaml_files(instances_root):
        rel = path.relative_to(instances_root)
        if any(part.startswith("_") for part in rel.parts):
            continue
        if path.name == "project.yaml":
            continue
        payload = _load_yaml_map(path, errors=errors)
        if not payload:
            continue
        rel_parts = rel.parts
        if len(rel_parts) not in {2, 3}:
            errors.append(
                f"{path.relative_to(ROOT).as_posix()}: instance shard path must be "
                "'<group>/<instance>.yaml' or '<group>/<host-shard>/<instance>.yaml'"
            )
            continue
        top_level_dir = str(rel_parts[0])
        if top_level_dir in LEGACY_INSTANCE_BUCKETS:
            errors.append(
                f"{path.relative_to(ROOT).as_posix()}: legacy layer-bucket instances path is not allowed; "
                "use canonical '<group>/...'"
            )
            continue
        if "instance_bindings" in payload:
            errors.append(
                f"{path.relative_to(ROOT).as_posix()}: sharded instance file must not contain 'instance_bindings'"
            )
            continue
        group = payload.get("@group")
        if not isinstance(group, str) or not group:
            errors.append(f"{path.relative_to(ROOT).as_posix()}: missing non-empty @group")
            continue
        if top_level_dir != group:
            errors.append(
                f"{path.relative_to(ROOT).as_posix()}: shard top-level directory '{top_level_dir}' "
                f"must match group '{group}'"
            )
            continue
        row = dict(payload)
        row.pop("@version", None)
        row.pop("@group", None)
        grouped.setdefault(group, []).append(row)
    for group_name in grouped:
        grouped[group_name].sort(key=lambda item: str(item.get("@instance", "")))
    return {"instance_bindings": grouped}


def _parse_object_layer_override(payload: dict[str, Any]) -> Any:
    topology = payload.get("topology")
    if not isinstance(topology, dict):
        return None
    return topology.get("allowed_layers")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate v5 L0-L7 layer contract.")
    parser.add_argument(
        "--topology",
        default=str(DEFAULT_MANIFEST.relative_to(ROOT).as_posix()),
        help="Path to v5 topology manifest YAML.",
    )
    parser.add_argument(
        "--report-json",
        default="",
        help="Optional path for machine-readable validation report JSON.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    errors: list[str] = []

    manifest_path = Path(args.topology)
    if not manifest_path.is_absolute():
        manifest_path = ROOT / manifest_path
    manifest = _load_yaml_map(manifest_path, errors=errors)
    if isinstance(manifest, dict) and "paths" in manifest:
        errors.append("E7808: legacy manifest contract section 'paths' is unsupported in strict-only mode")

    framework = manifest.get("framework") if isinstance(manifest, dict) else None
    if not isinstance(framework, dict):
        errors.append("topology manifest must contain mapping key 'framework'")
        framework = {}
    project = manifest.get("project") if isinstance(manifest, dict) else None
    if not isinstance(project, dict):
        errors.append("topology manifest must contain mapping key 'project'")
        project = {}

    class_modules_root = ROOT / str(framework.get("class_modules_root", ""))
    object_modules_root = ROOT / str(framework.get("object_modules_root", ""))
    layer_contract_path = ROOT / str(framework.get("layer_contract", ""))

    project_id = project.get("active")
    projects_root = project.get("projects_root")
    project_root_path = None
    if isinstance(project_id, str) and project_id.strip() and isinstance(projects_root, str) and projects_root.strip():
        project_root_path = ROOT / projects_root / project_id
    else:
        errors.append("topology manifest project.active and project.projects_root must be non-empty strings")

    instances_root_path: Path | None = None
    project_manifest_path: Path | None = None
    if isinstance(project_root_path, Path):
        project_manifest_path = project_root_path / "project.yaml"
        project_manifest = _load_yaml_map(project_manifest_path, errors=errors)
        instances_root_rel = project_manifest.get("instances_root")
        if isinstance(instances_root_rel, str) and instances_root_rel.strip():
            instances_root_path = (project_root_path / instances_root_rel).resolve()
        else:
            errors.append(
                "E7808: project manifest must define non-empty instances_root for strict-only instance source contract"
            )

    layer_contract = _load_yaml_map(layer_contract_path, errors=errors)
    valid_layers = set(DEFAULT_VALID_LAYERS)
    if isinstance(layer_contract, dict):
        configured_layers = layer_contract.get("layers")
        if configured_layers is not None:
            parsed_layers = _normalize_layers(
                configured_layers,
                path="layer-contract.layers",
                valid_layers=set(DEFAULT_VALID_LAYERS),
                errors=errors,
            )
            if parsed_layers:
                valid_layers = set(parsed_layers)

    group_layers_any = layer_contract.get("group_layers", {}) if isinstance(layer_contract, dict) else {}
    class_layers_any = layer_contract.get("class_layers", {}) if isinstance(layer_contract, dict) else {}
    runtime_rules_any = layer_contract.get("runtime_target_rules", []) if isinstance(layer_contract, dict) else []

    group_layers: dict[str, str] = {}
    if not isinstance(group_layers_any, dict):
        errors.append("layer-contract.group_layers must be a mapping")
    else:
        for group, layer in group_layers_any.items():
            path = f"layer-contract.group_layers.{group}"
            if not isinstance(group, str) or not group:
                errors.append(f"{path}: group name must be non-empty string")
                continue
            if not isinstance(layer, str) or not layer:
                errors.append(f"{path}: layer must be non-empty string")
                continue
            if layer not in valid_layers:
                errors.append(f"{path}: unknown layer '{layer}'")
                continue
            group_layers[group] = layer

    class_layers_cfg: dict[str, list[str]] = {}
    class_layers_status: dict[str, str] = {}
    if not isinstance(class_layers_any, dict):
        errors.append("layer-contract.class_layers must be a mapping")
    else:
        for class_id, cfg in class_layers_any.items():
            path = f"layer-contract.class_layers.{class_id}"
            if not isinstance(class_id, str) or not class_id:
                errors.append(f"{path}: class id must be non-empty string")
                continue
            if not isinstance(cfg, dict):
                errors.append(f"{path}: class config must be object")
                continue
            allowed_layers = _normalize_layers(
                cfg.get("allowed_layers"),
                path=f"{path}.allowed_layers",
                valid_layers=valid_layers,
                errors=errors,
            )
            status = cfg.get("status")
            if status is not None and not isinstance(status, str):
                errors.append(f"{path}.status: status must be string")
                continue
            if allowed_layers:
                class_layers_cfg[class_id] = allowed_layers
                if isinstance(status, str):
                    class_layers_status[class_id] = status

    runtime_rules: list[dict[str, Any]] = []
    if runtime_rules_any:
        if not isinstance(runtime_rules_any, list):
            errors.append("layer-contract.runtime_target_rules must be list")
        else:
            for idx, rule in enumerate(runtime_rules_any):
                path = f"layer-contract.runtime_target_rules[{idx}]"
                if not isinstance(rule, dict):
                    errors.append(f"{path}: rule must be object")
                    continue
                relation = rule.get("relation")
                direction = rule.get("direction", "")
                status = rule.get("status", "")
                source_layers = _normalize_layers(
                    rule.get("source_layers"),
                    path=f"{path}.source_layers",
                    valid_layers=valid_layers,
                    errors=errors,
                )
                target_layers = _normalize_layers(
                    rule.get("allowed_target_layers"),
                    path=f"{path}.allowed_target_layers",
                    valid_layers=valid_layers,
                    errors=errors,
                )
                if not isinstance(relation, str) or not relation:
                    errors.append(f"{path}.relation: relation must be non-empty string")
                    continue
                if direction not in ("", "downward", "upward", "same", "lateral"):
                    errors.append(f"{path}.direction: unsupported direction '{direction}'")
                    continue
                if status and not isinstance(status, str):
                    errors.append(f"{path}.status: status must be string")
                    continue
                runtime_rules.append(
                    {
                        "relation": relation,
                        "direction": direction,
                        "source_layers": source_layers,
                        "allowed_target_layers": target_layers,
                        "status": status,
                    }
                )

    class_files = [path for path in _iter_yaml_files(class_modules_root) if path.name.startswith("class.")]
    if not class_files:
        errors.append(f"class modules directory has no yaml files: {class_modules_root.relative_to(ROOT).as_posix()}")
    object_files = [path for path in _iter_yaml_files(object_modules_root) if path.name.startswith("obj.")]
    if not object_files:
        errors.append(f"object modules directory has no yaml files: {object_modules_root.relative_to(ROOT).as_posix()}")

    class_payloads: dict[str, dict[str, Any]] = {}
    class_rel_paths: dict[str, str] = {}
    for path in class_files:
        payload = _load_yaml_map(path, errors=errors)
        class_id = payload.get("@class")
        rel_path = path.relative_to(ROOT).as_posix()
        if not isinstance(class_id, str) or not class_id:
            errors.append(f"{rel_path}: class module missing non-empty @class")
            continue
        if class_id in class_payloads:
            errors.append(f"{rel_path}: duplicate class id '{class_id}'")
            continue
        class_payloads[class_id] = payload
        class_rel_paths[class_id] = path.relative_to(class_modules_root).as_posix()

    class_allowed_layers: dict[str, list[str]] = {}
    for class_id in sorted(class_payloads):
        allowed_layers = class_layers_cfg.get(class_id)
        if not allowed_layers:
            errors.append(f"class '{class_id}' is missing layer-contract.class_layers entry")
            continue
        class_allowed_layers[class_id] = allowed_layers

    for class_id in sorted(class_layers_cfg):
        if class_id not in class_payloads:
            if _is_planned_status(class_layers_status.get(class_id)):
                continue
            errors.append(f"layer-contract.class_layers has unknown class '{class_id}'")

    class_declared_layer: dict[str, str] = {}
    for class_id, payload in class_payloads.items():
        declared = payload.get("@layer")
        rel_path = class_rel_paths.get(class_id, class_id)
        display_path = f"topology/class-modules/{rel_path}" if rel_path != class_id else rel_path
        if declared is None:
            continue
        if not isinstance(declared, str) or not declared:
            errors.append(f"class '{class_id}' has non-string @layer")
            continue
        if declared not in valid_layers:
            errors.append(f"class '{class_id}' has unknown @layer '{declared}'")
            continue
        expected_bucket = LAYER_BUCKETS.get(declared)
        if isinstance(expected_bucket, str) and expected_bucket:
            rel_parts = Path(rel_path).parts
            if not rel_parts:
                errors.append(
                    f"{display_path}: class '{class_id}' has invalid path; expected '{expected_bucket}/...'"
                )
            elif rel_parts[0] != expected_bucket:
                errors.append(
                    f"{display_path}: class '{class_id}' with @layer '{declared}' must be placed under "
                    f"'topology/class-modules/{expected_bucket}/...'"
                )
        class_declared_layer[class_id] = declared

    object_payloads: dict[str, dict[str, Any]] = {}
    object_class_refs: dict[str, str] = {}
    object_allowed_layers: dict[str, list[str]] = {}
    object_default_layer: dict[str, str] = {}
    for path in object_files:
        payload = _load_yaml_map(path, errors=errors)
        object_id = payload.get("@object")
        class_ref = payload.get("@extends")
        rel_path = path.relative_to(ROOT).as_posix()

        if not isinstance(object_id, str) or not object_id:
            errors.append(f"{rel_path}: object module missing non-empty @object")
            continue
        if object_id in object_payloads:
            errors.append(f"{rel_path}: duplicate object id '{object_id}'")
            continue
        if not isinstance(class_ref, str) or not class_ref:
            errors.append(f"{rel_path}: object '{object_id}' missing non-empty @extends")
            continue
        if class_ref not in class_payloads:
            errors.append(f"{rel_path}: object '{object_id}' references unknown @extends '{class_ref}'")
            continue

        object_payloads[object_id] = payload
        object_class_refs[object_id] = class_ref

        derived_layer = class_declared_layer.get(class_ref)
        declared_layer = payload.get("@layer")
        if declared_layer is not None:
            errors.append(
                f"{rel_path}: object '{object_id}' must not declare @layer "
                "(layer is derived from class via @extends)"
            )

        override_layers = _parse_object_layer_override(payload)
        if override_layers is None:
            object_allowed_layers[object_id] = list(class_allowed_layers.get(class_ref, []))
            if isinstance(derived_layer, str) and derived_layer:
                object_default_layer[object_id] = derived_layer
            continue

        parsed_override = _normalize_layers(
            override_layers,
            path=f"{rel_path}.topology.allowed_layers",
            valid_layers=valid_layers,
            errors=errors,
        )
        class_layers = set(class_allowed_layers.get(class_ref, []))
        if not class_layers:
            errors.append(f"{rel_path}: class '{class_ref}' has no resolved allowed layers")
            object_allowed_layers[object_id] = parsed_override
            continue
        if not set(parsed_override).issubset(class_layers):
            errors.append(
                f"{rel_path}: object layer override must be subset of class layers "
                f"(class={sorted(class_layers)}, object={sorted(set(parsed_override))})"
            )
        object_allowed_layers[object_id] = parsed_override
        if object_id not in object_default_layer and isinstance(derived_layer, str) and derived_layer:
            object_default_layer[object_id] = derived_layer
        if object_id not in object_default_layer and len(parsed_override) == 1:
            object_default_layer[object_id] = parsed_override[0]

    if isinstance(instances_root_path, Path):
        instance_bindings = _load_instance_bindings_from_shards(instances_root_path, errors=errors)
    else:
        errors.append("E7808: topology project manifest must define non-empty instances_root in strict-only mode")
        instance_bindings = {}
    bindings_any = instance_bindings.get("instance_bindings", {})
    if not isinstance(bindings_any, dict):
        errors.append("instance-bindings must contain mapping key 'instance_bindings'")
        bindings_any = {}

    layer_order = {layer: idx for idx, layer in enumerate(DEFAULT_VALID_LAYERS)}
    instances_by_id: dict[str, dict[str, Any]] = {}
    runtime_edges: list[dict[str, Any]] = []

    for group, rows_any in bindings_any.items():
        group_path = f"instance_bindings.{group}"
        expected_group_layer = group_layers.get(group)
        if not isinstance(rows_any, list):
            errors.append(f"{group_path}: expected list")
            continue
        if expected_group_layer is None:
            errors.append(f"{group_path}: group is not declared in layer-contract.group_layers")
            continue

        for idx, row in enumerate(rows_any):
            path = f"{group_path}[{idx}]"
            if not isinstance(row, dict):
                errors.append(f"{path}: row must be object")
                continue

            row_id = row.get("@instance")
            object_ref = row.get("@extends")

            if not isinstance(row_id, str) or not row_id:
                errors.append(f"{path}: missing non-empty @instance")
                continue
            if row_id in instances_by_id:
                errors.append(f"{path}: duplicate instance '{row_id}'")
                continue
            if not isinstance(object_ref, str) or not object_ref:
                errors.append(f"{path}: missing non-empty @extends")
                continue
            if object_ref not in object_payloads:
                errors.append(f"{path}: unknown @extends '{object_ref}'")
                continue

            if "@layer" in row:
                errors.append(
                    f"{path}: instance '{row_id}' must not declare @layer; "
                    "layer is derived from @extends -> class.@layer"
                )
                continue

            row_layer = object_default_layer.get(object_ref)
            if not isinstance(row_layer, str) or not row_layer:
                errors.append(f"{path}: cannot derive layer from object '{object_ref}'")
                continue

            if row_layer != expected_group_layer:
                errors.append(
                    f"{path}: layer '{row_layer}' must match group layer '{expected_group_layer}' for group '{group}'"
                )

            class_ref = object_class_refs.get(object_ref)
            if not isinstance(class_ref, str) or not class_ref:
                errors.append(f"{path}: cannot resolve class from object @extends '{object_ref}'")
                continue
            if class_ref not in class_payloads:
                errors.append(f"{path}: unknown class '{class_ref}'")
                continue

            object_class_ref = object_class_refs.get(object_ref)
            if object_class_ref != class_ref:
                errors.append(
                    f"{path}: class/object mismatch: class='{class_ref}', @extends='{object_ref}' "
                    f"binds to '{object_class_ref}'"
                )

            if row_layer not in set(class_allowed_layers.get(class_ref, [])):
                errors.append(f"{path}: layer '{row_layer}' is not allowed by class '{class_ref}'")
            if row_layer not in set(object_allowed_layers.get(object_ref, [])):
                errors.append(f"{path}: layer '{row_layer}' is not allowed by object '{object_ref}'")

            instances_by_id[row_id] = {
                "instance": row_id,
                "layer": row_layer,
                "path": path,
            }

            runtime = row.get("runtime")
            if isinstance(runtime, dict):
                target_ref = runtime.get("target_ref")
                if isinstance(target_ref, str) and target_ref:
                    runtime_edges.append(
                        {
                            "source_id": row_id,
                            "source_layer": row_layer,
                            "target_ref": target_ref,
                            "path": f"{path}.runtime.target_ref",
                        }
                    )

    for edge in runtime_edges:
        source_layer = edge["source_layer"]
        target_ref = edge["target_ref"]
        target = instances_by_id.get(target_ref)
        if target is None:
            errors.append(f"{edge['path']}: target_ref '{target_ref}' does not exist in instance_bindings")
            continue

        target_layer = target["layer"]
        matched_rules = [
            rule
            for rule in runtime_rules
            if rule.get("relation") == "runtime.target_ref"
            and source_layer in set(rule.get("source_layers", []))
            and not _is_planned_status(rule.get("status"))
        ]
        if not matched_rules:
            continue

        for rule in matched_rules:
            allowed_target_layers = set(rule.get("allowed_target_layers", []))
            if allowed_target_layers and target_layer not in allowed_target_layers:
                errors.append(
                    f"{edge['path']}: target '{target_ref}' layer '{target_layer}' is not allowed "
                    f"for source layer '{source_layer}' (allowed={sorted(allowed_target_layers)})"
                )
            direction = rule.get("direction", "")
            if direction == "downward":
                if layer_order.get(target_layer, 99) >= layer_order.get(source_layer, -1):
                    errors.append(f"{edge['path']}: downward dependency required, got {source_layer} -> {target_layer}")
            elif direction == "upward":
                if layer_order.get(target_layer, -1) <= layer_order.get(source_layer, 99):
                    errors.append(f"{edge['path']}: upward dependency required, got {source_layer} -> {target_layer}")
            elif direction in {"same", "lateral"} and target_layer != source_layer:
                errors.append(f"{edge['path']}: same-layer dependency required, got {source_layer} -> {target_layer}")

    report = {
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "ok": not errors,
        "error_count": len(errors),
        "inputs": {
            "topology": manifest_path.relative_to(ROOT).as_posix() if manifest_path.exists() else str(manifest_path),
            "layer_contract": (
                layer_contract_path.relative_to(ROOT).as_posix()
                if layer_contract_path.exists()
                else str(layer_contract_path)
            ),
            "project_manifest": (
                project_manifest_path.relative_to(ROOT).as_posix()
                if isinstance(project_manifest_path, Path) and project_manifest_path.exists()
                else str(project_manifest_path or "")
            ),
            "instances_root": (
                instances_root_path.relative_to(ROOT).as_posix()
                if isinstance(instances_root_path, Path) and instances_root_path.exists()
                else str(instances_root_path or "")
            ),
        },
        "summary": {
            "classes": len(class_payloads),
            "objects": len(object_payloads),
            "instances": len(instances_by_id),
            "runtime_edges": len(runtime_edges),
        },
        "errors": errors,
    }

    if args.report_json:
        report_path = Path(args.report_json)
        if not report_path.is_absolute():
            report_path = ROOT / report_path
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, ensure_ascii=True, indent=2), encoding="utf-8")
        print(f"[v5-layer] report: {report_path}")

    if errors:
        print("v5 layer contract: FAIL")
        for error in errors:
            print(f"- {error}")
        return 1

    print("v5 layer contract: PASS")
    print(
        f"classes={report['summary']['classes']} objects={report['summary']['objects']} "
        f"instances={report['summary']['instances']} runtime_edges={report['summary']['runtime_edges']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
