#!/usr/bin/env python3
"""Generate hardware identity patch templates from secret annotations.

This utility scans project instance shards and object templates, resolves
hardware identity secret annotations, and emits patch YAML files per instance.

Generated files are intended for operator-assisted capture workflows:
- collect serial/MAC values from devices (SSH/API/manual inventory),
- fill patch files,
- apply values to encrypted side-car secrets.
"""

from __future__ import annotations

import argparse
import ipaddress
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import yaml
from field_annotations import FieldAnnotation, parse_field_annotation


@dataclass(frozen=True)
class SecretPathSpec:
    path: str
    annotation: FieldAnnotation


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _default_topology_path() -> Path:
    return _repo_root() / "v5" / "topology" / "topology.yaml"


def _load_yaml(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(payload, dict):
        raise ValueError(f"YAML root must be mapping in {path}")
    return payload


def _normalize_token(value: str) -> str:
    token = value.strip().lower()
    return "".join(ch if ch.isalnum() else "_" for ch in token).strip("_")


def _collect_secret_annotations(
    node: Any,
    *,
    path: tuple[Any, ...] = (),
    out: dict[str, FieldAnnotation],
) -> None:
    if isinstance(node, dict):
        for key, value in node.items():
            _collect_secret_annotations(value, path=path + (key,), out=out)
        return
    if isinstance(node, list):
        for idx, value in enumerate(node):
            _collect_secret_annotations(value, path=path + (idx,), out=out)
        return
    if not isinstance(node, str) or not node.startswith("@") or node.startswith("@@"):
        return
    annotation, annotation_error = parse_field_annotation(node)
    if annotation_error is not None or annotation is None or not annotation.secret:
        return
    flat_path = _format_path(path)
    if flat_path:
        out[flat_path] = annotation


def _format_path(path: tuple[Any, ...]) -> str:
    if not path:
        return ""
    parts: list[str] = []
    for token in path:
        if isinstance(token, int):
            parts.append(f"[{token}]")
            continue
        if parts:
            parts.append(".")
        parts.append(str(token))
    return "".join(parts)


def _derive_interface_mac_secret_annotations(object_payload: dict[str, Any]) -> dict[str, FieldAnnotation]:
    result: dict[str, FieldAnnotation] = {}
    hardware_specs = object_payload.get("hardware_specs")
    if not isinstance(hardware_specs, dict):
        return result
    interfaces = hardware_specs.get("interfaces")
    if not isinstance(interfaces, dict):
        return result

    for _, entries in interfaces.items():
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            mac_token = entry.get("mac")
            if not isinstance(mac_token, str):
                continue
            annotation, annotation_error = parse_field_annotation(mac_token)
            if annotation_error is not None or annotation is None or not annotation.secret:
                continue
            name = entry.get("name")
            if not isinstance(name, str) or not name.strip():
                continue
            key = name.strip()
            band = entry.get("band")
            if isinstance(band, str) and band.strip():
                key = f"{key}_{_normalize_token(band)}"
            result[f"hardware_identity.mac_addresses.{key}"] = annotation
    return result


def collect_hardware_identity_secret_paths(object_payload: dict[str, Any]) -> dict[str, FieldAnnotation]:
    annotations: dict[str, FieldAnnotation] = {}
    _collect_secret_annotations(object_payload, out=annotations)
    projected = _derive_interface_mac_secret_annotations(object_payload)

    result: dict[str, FieldAnnotation] = {}
    for path, annotation in annotations.items():
        if path.startswith("hardware_identity."):
            result[path] = annotation
    for path, annotation in projected.items():
        result[path] = annotation
    return result


def _discover_instance_map(raw: dict[str, Any]) -> dict[str, dict[str, Any]]:
    instances = raw.get("instances")
    if isinstance(instances, dict):
        return {str(k): v for k, v in instances.items() if isinstance(v, dict)}
    result: dict[str, dict[str, Any]] = {}
    for key, value in raw.items():
        if isinstance(key, str) and isinstance(value, dict):
            result[key] = value
    return result


def _split_path(path: str) -> list[str]:
    parts: list[str] = []
    for token in path.split("."):
        if token:
            parts.append(token)
    return parts


def _lookup_by_path(node: dict[str, Any], path: str) -> tuple[bool, Any]:
    current: Any = node
    for token in _split_path(path):
        if not isinstance(current, dict) or token not in current:
            return False, None
        current = current[token]
    return True, current


def _set_by_path(node: dict[str, Any], path: str, value: Any) -> None:
    current: dict[str, Any] = node
    parts = _split_path(path)
    if not parts:
        return
    for token in parts[:-1]:
        child = current.get(token)
        if not isinstance(child, dict):
            child = {}
            current[token] = child
        current = child
    current[parts[-1]] = value


def _placeholder_for(path: str, annotation: FieldAnnotation) -> str:
    if path == "hardware_identity.serial_number":
        return "<DISCOVER_SERIAL_NUMBER>"
    if path.startswith("hardware_identity.mac_addresses."):
        key = path.split(".", maxsplit=2)[2]
        normalized = re.sub(r"[^A-Za-z0-9]+", "_", key).upper().strip("_")
        return f"<DISCOVER_MAC_{normalized}>"
    if isinstance(annotation.value_type, str) and annotation.value_type:
        normalized_type = re.sub(r"[^A-Za-z0-9]+", "_", annotation.value_type).upper().strip("_")
        return f"<DISCOVER_{normalized_type}>"
    normalized_path = re.sub(r"[^A-Za-z0-9]+", "_", path).upper().strip("_")
    return f"<DISCOVER_{normalized_path}>"


def _load_format_registry(registry_path: Path) -> dict[str, dict[str, Any]]:
    payload = _load_yaml(registry_path)
    formats = payload.get("formats")
    if not isinstance(formats, dict):
        raise ValueError(f"Format registry must contain mapping 'formats': {registry_path}")
    result: dict[str, dict[str, Any]] = {}
    for key, value in formats.items():
        if isinstance(key, str) and isinstance(value, dict):
            result[key] = value
    return result


def _validate_with_spec(value: Any, spec: dict[str, Any]) -> tuple[bool, str]:
    expected_type = spec.get("type")
    if expected_type == "string" and not isinstance(value, str):
        return False, f"expected string, got {type(value).__name__}"
    if expected_type == "integer" and (not isinstance(value, int) or isinstance(value, bool)):
        return False, f"expected integer, got {type(value).__name__}"
    if expected_type == "number" and (not isinstance(value, (int, float)) or isinstance(value, bool)):
        return False, f"expected number, got {type(value).__name__}"
    if expected_type == "boolean" and not isinstance(value, bool):
        return False, f"expected boolean, got {type(value).__name__}"

    pattern = spec.get("pattern")
    if isinstance(pattern, str):
        regex = re.compile(pattern)
        if not isinstance(value, str) or regex.fullmatch(value) is None:
            return False, "regex mismatch"

    validator = spec.get("validator")
    if validator == "ipv4":
        try:
            ipaddress.IPv4Address(str(value))
        except Exception:
            return False, "invalid ipv4"
    elif validator == "ipv6":
        try:
            ipaddress.IPv6Address(str(value))
        except Exception:
            return False, "invalid ipv6"
    elif validator == "cidr":
        try:
            ipaddress.ip_network(str(value), strict=False)
        except Exception:
            return False, "invalid cidr"
    elif validator == "uri":
        parsed = urlparse(str(value))
        if not parsed.scheme:
            return False, "invalid uri"
    return True, "ok"


def _validate_discovered_value(
    *,
    value: Any,
    annotation: FieldAnnotation,
    formats: dict[str, dict[str, Any]],
) -> tuple[bool, str]:
    value_type = annotation.value_type
    if not isinstance(value_type, str) or not value_type:
        return True, "ok"
    spec = formats.get(value_type)
    if not isinstance(spec, dict):
        return False, f"unknown format '{value_type}'"
    return _validate_with_spec(value, spec)


def build_hardware_identity_patch(
    *,
    instance_id: str,
    path_specs: dict[str, FieldAnnotation],
    discovered: dict[str, Any] | None,
    include_placeholders: bool,
    formats: dict[str, dict[str, Any]],
) -> tuple[dict[str, Any] | None, list[str]]:
    errors: list[str] = []
    patch: dict[str, Any] = {"instance": instance_id}
    payload: dict[str, Any] = {}

    for path in sorted(path_specs):
        annotation = path_specs[path]
        found = False
        value: Any = None
        if isinstance(discovered, dict):
            found, value = _lookup_by_path(discovered, path)

        if found:
            ok, reason = _validate_discovered_value(value=value, annotation=annotation, formats=formats)
            if not ok:
                errors.append(
                    f"instance '{instance_id}': discovered value at '{path}' does not match "
                    f"format '{annotation.value_type}': {reason}"
                )
                continue
            _set_by_path(payload, path, value)
            continue

        if include_placeholders:
            _set_by_path(payload, path, _placeholder_for(path, annotation))

    if not payload:
        return None, errors

    patch.update(payload)
    return patch, errors


def _iter_instance_rows(instances_root: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in sorted(instances_root.rglob("*.yaml"), key=lambda p: p.relative_to(instances_root).as_posix()):
        relative_parts = path.relative_to(instances_root).parts
        if any(part.startswith("_") for part in relative_parts):
            continue
        if path.name == "project.yaml":
            continue
        payload = _load_yaml(path)
        instance_id = payload.get("instance")
        object_ref = payload.get("object_ref")
        if not isinstance(instance_id, str) or not instance_id:
            continue
        if not isinstance(object_ref, str) or not object_ref:
            continue
        row_annotations: dict[str, FieldAnnotation] = {}
        _collect_secret_annotations(payload, out=row_annotations)
        hardware_row_annotations = {
            key: value for key, value in row_annotations.items() if key.startswith("hardware_identity.")
        }
        rows.append(
            {
                "instance": instance_id,
                "object_ref": object_ref,
                "row_secret_annotations": hardware_row_annotations,
            }
        )
    return rows


def _load_object_map(objects_root: Path) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for path in sorted(objects_root.rglob("*.yaml"), key=lambda p: p.relative_to(objects_root).as_posix()):
        payload = _load_yaml(path)
        object_id = payload.get("object")
        if isinstance(object_id, str) and object_id:
            result[object_id] = payload
    return result


def _resolve_project_layout(
    *,
    topology_path: Path,
    project_override: str,
) -> tuple[str, Path, Path, Path]:
    topology = _load_yaml(topology_path)
    framework = topology.get("framework")
    project = topology.get("project")
    if not isinstance(framework, dict):
        raise ValueError("topology manifest is missing 'framework' mapping")
    if not isinstance(project, dict):
        raise ValueError("topology manifest is missing 'project' mapping")

    active_project = project_override.strip() if project_override else ""
    if not active_project:
        active = project.get("active")
        if not isinstance(active, str) or not active.strip():
            raise ValueError("topology project.active must be non-empty string")
        active_project = active.strip()

    projects_root_value = project.get("projects_root")
    if not isinstance(projects_root_value, str) or not projects_root_value.strip():
        raise ValueError("topology project.projects_root must be non-empty string")

    repo_root = _repo_root()
    projects_root = repo_root / projects_root_value
    project_root = projects_root / active_project
    project_manifest_path = project_root / "project.yaml"
    project_manifest = _load_yaml(project_manifest_path)

    instances_root_value = project_manifest.get("instances_root")
    secrets_root_value = project_manifest.get("secrets_root")
    if not isinstance(instances_root_value, str) or not instances_root_value.strip():
        raise ValueError(f"project manifest missing non-empty 'instances_root': {project_manifest_path}")
    if not isinstance(secrets_root_value, str) or not secrets_root_value.strip():
        raise ValueError(f"project manifest missing non-empty 'secrets_root': {project_manifest_path}")

    objects_root_value = framework.get("object_modules_root")
    if not isinstance(objects_root_value, str) or not objects_root_value.strip():
        raise ValueError("topology framework.object_modules_root must be non-empty string")
    objects_root = repo_root / objects_root_value
    instances_root = project_root / instances_root_value
    secrets_root = project_root / secrets_root_value
    return active_project, objects_root, instances_root, secrets_root


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate hardware identity patch templates from secret annotations.")
    parser.add_argument(
        "--topology",
        type=Path,
        default=_default_topology_path(),
        help="Path to topology manifest (default: topology/topology.yaml).",
    )
    parser.add_argument(
        "--project",
        default="",
        help="Project id override (default: project.active from topology manifest).",
    )
    parser.add_argument(
        "--discovery-file",
        type=Path,
        default=None,
        help="Optional YAML with discovered values. Supports root.instances mapping or root mapping by instance id.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help=("Output directory for patch files. Default: " "build/hardware-identity-patches/<project>/"),
    )
    parser.add_argument(
        "--instance",
        action="append",
        default=[],
        help="Limit generation to one or more instance ids (repeatable).",
    )
    parser.add_argument(
        "--only-discovered",
        action="store_true",
        help="Emit only fields that exist in discovery file (no placeholders).",
    )
    parser.add_argument(
        "--format-registry",
        type=Path,
        default=Path(__file__).resolve().parent / "data" / "instance-field-formats.yaml",
        help="Path to field format registry used for discovered value validation.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        project_id, objects_root, instances_root, _ = _resolve_project_layout(
            topology_path=args.topology,
            project_override=str(args.project),
        )
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    if not objects_root.exists():
        print(f"ERROR: objects root does not exist: {objects_root}", file=sys.stderr)
        return 2
    if not instances_root.exists():
        print(f"ERROR: instances root does not exist: {instances_root}", file=sys.stderr)
        return 2

    if args.output_dir is not None:
        output_dir = args.output_dir
    else:
        output_dir = _repo_root() / "v5-build" / "hardware-identity-patches" / project_id
    output_dir.mkdir(parents=True, exist_ok=True)

    discovery_map: dict[str, dict[str, Any]] = {}
    if args.discovery_file is not None:
        try:
            raw_discovery = _load_yaml(args.discovery_file)
            discovery_map = _discover_instance_map(raw_discovery)
        except Exception as exc:
            print(f"ERROR: failed to read discovery file '{args.discovery_file}': {exc}", file=sys.stderr)
            return 2

    try:
        format_registry = _load_format_registry(args.format_registry)
    except Exception as exc:
        print(f"ERROR: failed to load format registry '{args.format_registry}': {exc}", file=sys.stderr)
        return 2

    object_map = _load_object_map(objects_root)
    instance_rows = _iter_instance_rows(instances_root)
    selected_instances = {item.strip() for item in args.instance if isinstance(item, str) and item.strip()}

    total_candidates = 0
    generated = 0
    errors: list[str] = []

    for row in instance_rows:
        instance_id = row["instance"]
        if selected_instances and instance_id not in selected_instances:
            continue

        object_payload = object_map.get(row["object_ref"])
        if not isinstance(object_payload, dict):
            continue

        object_paths = collect_hardware_identity_secret_paths(object_payload)
        row_paths = row.get("row_secret_annotations", {})
        merged_paths = dict(object_paths)
        if isinstance(row_paths, dict):
            merged_paths.update({k: v for k, v in row_paths.items() if isinstance(k, str)})
        if not merged_paths:
            continue

        total_candidates += 1
        discovered = discovery_map.get(instance_id)
        patch, patch_errors = build_hardware_identity_patch(
            instance_id=instance_id,
            path_specs=merged_paths,
            discovered=discovered,
            include_placeholders=not args.only_discovered,
            formats=format_registry,
        )
        errors.extend(patch_errors)
        if patch is None:
            continue

        output_path = output_dir / f"{instance_id}.yaml"
        output_path.write_text(
            yaml.safe_dump(patch, allow_unicode=False, sort_keys=False),
            encoding="utf-8",
        )
        generated += 1

    if errors:
        for row in errors:
            print(f"ERROR: {row}", file=sys.stderr)
        return 2

    print(
        f"Generated {generated} hardware identity patch file(s) "
        f"for {total_candidates} annotated instance(s) in '{output_dir}'."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
