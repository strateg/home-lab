"""Runtime helper steps for compile-topology orchestrator."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import yaml
from identifier_policy import contains_unsafe_identifier_chars

INSTANCE_SOURCE_MODES = {"auto", "sharded-only"}
_INSTANCE_VERSION_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")
_LAYER_BUCKETS: dict[str, str] = {
    "L0": "L0-meta",
    "L1": "L1-foundation",
    "L2": "L2-network",
    "L3": "L3-data",
    "L4": "L4-platform",
    "L5": "L5-application",
    "L6": "L6-observability",
    "L7": "L7-operations",
}


@dataclass
class ManifestPathBundle:
    class_modules_root: Path
    object_modules_root: Path
    capability_catalog_path: Path
    capability_packs_path: Path
    layer_contract_path: Path
    instances_root_path: Path | None
    secrets_root_path: Path | None
    model_lock_path: Path
    project_id: str
    project_root: Path
    project_manifest_path: Path


@dataclass
class CompileInputs:
    class_map: dict[str, dict[str, Any]]
    object_map: dict[str, dict[str, Any]]
    catalog_ids: set[str]
    packs_map: dict[str, dict[str, Any]]
    instance_payload: dict[str, Any] | None
    rows: list[dict[str, Any]]
    lock_payload: dict[str, Any] | None
    instance_source_mode: str


def discover_plugin_manifests(
    *,
    base_manifest_path: Path,
    class_modules_root: Path,
    object_modules_root: Path,
    instance_manifests_root: Path | None = None,
    manifest_name: str = "plugins.yaml",
) -> list[Path]:
    """Discover plugin manifests with deterministic merge order.

    Merge order policy:
    1. explicit base manifest from CLI/config
    2. class module manifests (sorted lexicographically by relative path)
    3. object module manifests (sorted lexicographically by relative path)
    4. instance manifests (sorted lexicographically by relative path)
    """

    discovered: list[tuple[int, str, Path]] = []
    roots: list[tuple[int, Path | None]] = [
        (0, class_modules_root),
        (1, object_modules_root),
        (2, instance_manifests_root),
    ]
    base_resolved = base_manifest_path.resolve()

    for root_order, root in roots:
        if root is None:
            continue
        if not root.exists() or not root.is_dir():
            continue
        for manifest_path in root.rglob(manifest_name):
            resolved = manifest_path.resolve()
            if resolved == base_resolved:
                continue
            try:
                rel_key = resolved.relative_to(root.resolve()).as_posix()
            except ValueError:
                rel_key = resolved.as_posix()
            discovered.append((root_order, rel_key.casefold(), resolved))

    discovered.sort(key=lambda item: (item[0], item[1], item[2].as_posix().casefold()))

    ordered = [base_resolved]
    ordered.extend(path for _, _, path in discovered)
    return ordered


def resolve_manifest_paths(
    *,
    framework_paths: dict[str, Any],
    project_id: str,
    project_root: Path,
    project_manifest: dict[str, Any],
    resolve_repo_path: Callable[[str], Path],
) -> ManifestPathBundle:
    def _project_relative_path(raw: Any) -> Path | None:
        if not isinstance(raw, str):
            return None
        value = raw.strip()
        if not value:
            return None
        candidate = Path(value)
        if candidate.is_absolute():
            return candidate
        return project_root / candidate

    return ManifestPathBundle(
        class_modules_root=resolve_repo_path(str(framework_paths.get("class_modules_root", ""))),
        object_modules_root=resolve_repo_path(str(framework_paths.get("object_modules_root", ""))),
        capability_catalog_path=resolve_repo_path(str(framework_paths.get("capability_catalog", ""))),
        capability_packs_path=resolve_repo_path(str(framework_paths.get("capability_packs", ""))),
        layer_contract_path=resolve_repo_path(str(framework_paths.get("layer_contract", ""))),
        instances_root_path=_project_relative_path(project_manifest.get("instances_root")),
        secrets_root_path=_project_relative_path(project_manifest.get("secrets_root")),
        model_lock_path=resolve_repo_path(str(framework_paths.get("model_lock", ""))),
        project_id=project_id,
        project_root=project_root,
        project_manifest_path=project_root / "project.yaml",
    )


def resolve_instance_source_mode(
    *,
    requested_mode: str,
    paths: ManifestPathBundle,
) -> str:
    _ = paths
    if requested_mode == "sharded-only":
        return "sharded-only"
    return "sharded-only"


def _diag_path(*, repo_root: Path, path: Path) -> str:
    try:
        return str(path.relative_to(repo_root).as_posix())
    except ValueError:
        return str(path.as_posix())


def _is_supported_instance_version(value: str) -> bool:
    match = _INSTANCE_VERSION_RE.fullmatch(value.strip())
    if match is None:
        return False
    major = int(match.group(1))
    return major == 1


def _load_group_layer_map(
    *,
    layer_contract_path: Path,
    load_yaml: Callable[..., dict[str, Any] | None],
    add_diag: Callable[..., None],
    repo_root: Path,
) -> dict[str, str]:
    payload = load_yaml(
        layer_contract_path,
        code_missing="E1001",
        code_parse="E1003",
        stage="load",
    )
    if not isinstance(payload, dict):
        return {}
    group_layers = payload.get("group_layers")
    if not isinstance(group_layers, dict):
        add_diag(
            code="E3201",
            severity="error",
            stage="validate",
            message="layer-contract must contain mapping key 'group_layers'.",
            path=_diag_path(repo_root=repo_root, path=layer_contract_path),
        )
        return {}
    result: dict[str, str] = {}
    for group_name, layer_name in group_layers.items():
        if isinstance(group_name, str) and group_name and isinstance(layer_name, str) and layer_name:
            result[group_name] = layer_name
    return result


def _load_sharded_instance_payload(
    *,
    instances_root: Path | None,
    mode: str,
    group_layer_map: dict[str, str],
    add_diag: Callable[..., None],
    repo_root: Path,
    project_manifest_path: Path,
) -> dict[str, Any] | None:
    if instances_root is None:
        if mode == "sharded-only":
            add_diag(
                code="E7107",
                severity="error",
                stage="load",
                message="Sharded instance source requires non-empty project instances_root.",
                path=f"{_diag_path(repo_root=repo_root, path=project_manifest_path)}:instances_root",
            )
        return None
    if not instances_root.exists() or not instances_root.is_dir():
        if mode == "sharded-only":
            add_diag(
                code="E1001",
                severity="error",
                stage="load",
                message=f"Directory does not exist: {instances_root}",
                path=_diag_path(repo_root=repo_root, path=instances_root),
            )
        return None

    grouped_rows: dict[str, list[dict[str, Any]]] = {}
    seen_instances: dict[str, Path] = {}
    shard_files = sorted(
        (path for path in instances_root.rglob("*.yaml") if path.is_file()),
        key=lambda item: item.relative_to(instances_root).as_posix().casefold(),
    )
    for path in shard_files:
        relative_path = path.relative_to(instances_root).as_posix()
        relative_parts = Path(relative_path).parts
        name = path.name
        if any(part.startswith("_") for part in relative_parts):
            continue
        if name == "project.yaml":
            continue
        if name == "instance-bindings.yaml":
            add_diag(
                code="E7105",
                severity="error",
                stage="load",
                message="Legacy instance-bindings.yaml cannot be ingested from instances_root.",
                path=_diag_path(repo_root=repo_root, path=path),
            )
            continue

        try:
            payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except (OSError, yaml.YAMLError) as exc:
            add_diag(
                code="E1003",
                severity="error",
                stage="load",
                message=f"YAML parse error: {exc}",
                path=_diag_path(repo_root=repo_root, path=path),
            )
            continue
        if not isinstance(payload, dict):
            add_diag(
                code="E1004",
                severity="error",
                stage="load",
                message="Expected mapping/object at YAML root.",
                path=_diag_path(repo_root=repo_root, path=path),
            )
            continue
        if "instance_bindings" in payload:
            add_diag(
                code="E7103",
                severity="error",
                stage="validate",
                message="Sharded instance file must contain a single instance row, not 'instance_bindings'.",
                path=_diag_path(repo_root=repo_root, path=path),
            )
            continue

        shard_version = payload.get("version")
        has_supported_version = isinstance(shard_version, str) and _is_supported_instance_version(shard_version)
        if not has_supported_version:
            add_diag(
                code="E7104",
                severity="error",
                stage="validate",
                message=(
                    "Unsupported shard version metadata. "
                    f"version='{shard_version}'. "
                    "Use strict contract 'version: 1.0.0'; 'schema_version' is not supported."
                ),
                path=_diag_path(repo_root=repo_root, path=path),
            )
            continue

        required_keys = ("instance", "group", "layer", "object_ref")
        missing = [key for key in required_keys if key not in payload]
        if missing:
            add_diag(
                code="E3201",
                severity="error",
                stage="validate",
                message=f"Instance shard is missing required keys: {', '.join(missing)}.",
                path=_diag_path(repo_root=repo_root, path=path),
            )
            continue

        instance_id = payload.get("instance")
        group_name = payload.get("group")
        layer = payload.get("layer")
        object_ref = payload.get("object_ref")
        explicit_class_ref = payload.get("class_ref")
        if not isinstance(instance_id, str) or not instance_id:
            add_diag(
                code="E3201",
                severity="error",
                stage="validate",
                message="Instance shard must define non-empty 'instance'.",
                path=f"{_diag_path(repo_root=repo_root, path=path)}:instance",
            )
            continue
        if contains_unsafe_identifier_chars(instance_id):
            add_diag(
                code="E3201",
                severity="error",
                stage="validate",
                message=(
                    f"Instance id '{instance_id}' contains filename-unsafe characters; "
                    "use only cross-platform filename-safe symbols."
                ),
                path=f"{_diag_path(repo_root=repo_root, path=path)}:instance",
            )
            continue
        if path.stem != instance_id:
            add_diag(
                code="E7101",
                severity="error",
                stage="validate",
                message=f"File basename '{path.stem}' must match instance '{instance_id}'.",
                path=_diag_path(repo_root=repo_root, path=path),
            )
            continue
        if instance_id in seen_instances:
            add_diag(
                code="E7102",
                severity="error",
                stage="resolve",
                message=(
                    f"Duplicate instance '{instance_id}' in shard files: "
                    f"{_diag_path(repo_root=repo_root, path=seen_instances[instance_id])} and "
                    f"{_diag_path(repo_root=repo_root, path=path)}."
                ),
                path=_diag_path(repo_root=repo_root, path=path),
            )
            continue
        seen_instances[instance_id] = path

        if not isinstance(group_name, str) or not group_name:
            add_diag(
                code="E3201",
                severity="error",
                stage="validate",
                message="Instance shard must define non-empty 'group'.",
                path=f"{_diag_path(repo_root=repo_root, path=path)}:group",
            )
            continue
        if not isinstance(layer, str) or not layer:
            add_diag(
                code="E3201",
                severity="error",
                stage="validate",
                message="Instance shard must define non-empty 'layer'.",
                path=f"{_diag_path(repo_root=repo_root, path=path)}:layer",
            )
            continue
        if not isinstance(object_ref, str) or not object_ref:
            add_diag(
                code="E3201",
                severity="error",
                stage="validate",
                message="Instance shard must define non-empty 'object_ref'.",
                path=f"{_diag_path(repo_root=repo_root, path=path)}:object_ref",
            )
            continue
        if explicit_class_ref is not None and (not isinstance(explicit_class_ref, str) or not explicit_class_ref):
            add_diag(
                code="E3201",
                severity="error",
                stage="validate",
                message="If provided, class_ref must be non-empty string.",
                path=f"{_diag_path(repo_root=repo_root, path=path)}:class_ref",
            )
            continue
        expected_layer = group_layer_map.get(group_name)
        if expected_layer is None:
            add_diag(
                code="E3201",
                severity="error",
                stage="validate",
                message=f"Unknown instance group '{group_name}' (missing in layer-contract group_layers).",
                path=f"{_diag_path(repo_root=repo_root, path=path)}:group",
            )
            continue
        if layer != expected_layer:
            add_diag(
                code="E3201",
                severity="error",
                stage="validate",
                message=f"Group '{group_name}' must use layer '{expected_layer}', got '{layer}'.",
                path=f"{_diag_path(repo_root=repo_root, path=path)}:layer",
            )
            continue
        if len(relative_parts) != 3:
            add_diag(
                code="E7108",
                severity="error",
                stage="validate",
                message=(
                    "Instance shard path must be exactly "
                    "'<layer-bucket>/<group>/<instance>.yaml' under instances_root."
                ),
                path=_diag_path(repo_root=repo_root, path=path),
            )
            continue
        expected_bucket = _LAYER_BUCKETS.get(layer)
        layer_bucket = str(relative_parts[0])
        group_dir = str(relative_parts[1])
        if isinstance(expected_bucket, str) and expected_bucket and layer_bucket != expected_bucket:
            add_diag(
                code="E7108",
                severity="error",
                stage="validate",
                message=(
                    f"Layer bucket '{layer_bucket}' does not match layer '{layer}'. " f"Expected '{expected_bucket}'."
                ),
                path=_diag_path(repo_root=repo_root, path=path),
            )
            continue
        if group_dir != group_name:
            add_diag(
                code="E7109",
                severity="error",
                stage="validate",
                message=f"Group directory '{group_dir}' must match shard group '{group_name}'.",
                path=_diag_path(repo_root=repo_root, path=path),
            )
            continue

        row = dict(payload)
        row.pop("schema_version", None)
        row.pop("version", None)
        row.pop("group", None)
        if not isinstance(explicit_class_ref, str):
            row.pop("class_ref", None)
        row["_source_file"] = str(path)
        grouped_rows.setdefault(group_name, []).append(row)

    ordered_rows: dict[str, list[dict[str, Any]]] = {}
    for group_name in sorted(grouped_rows):
        group_rows = grouped_rows[group_name]
        group_rows.sort(key=lambda item: str(item.get("instance", "")))
        ordered_rows[group_name] = group_rows

    if not ordered_rows:
        return None
    return {"instance_bindings": ordered_rows}


def load_core_compile_inputs(
    *,
    paths: ManifestPathBundle,
    instances_mode: str,
    load_yaml: Callable[..., dict[str, Any] | None],
    add_diag: Callable[..., None],
    repo_root: Path,
) -> CompileInputs:
    # Plugin-first runtime: compile-derived maps and capability contracts
    # are published by compiler plugins and wired later.
    class_map: dict[str, dict[str, Any]] = {}
    object_map: dict[str, dict[str, Any]] = {}
    catalog_ids: set[str] = set()
    packs_map: dict[str, dict[str, Any]] = {}

    resolved_instances_mode = resolve_instance_source_mode(
        requested_mode=instances_mode,
        paths=paths,
    )
    group_layer_map = _load_group_layer_map(
        layer_contract_path=paths.layer_contract_path,
        load_yaml=load_yaml,
        add_diag=add_diag,
        repo_root=repo_root,
    )
    instance_payload = _load_sharded_instance_payload(
        instances_root=paths.instances_root_path,
        mode=resolved_instances_mode,
        group_layer_map=group_layer_map,
        add_diag=add_diag,
        repo_root=repo_root,
        project_manifest_path=paths.project_manifest_path,
    )

    # Normalized instance rows and model lock payload are plugin-owned
    # in plugin-first mode.
    rows: list[dict[str, Any]] = []
    lock_payload = None

    return CompileInputs(
        class_map=class_map,
        object_map=object_map,
        catalog_ids=catalog_ids,
        packs_map=packs_map,
        instance_payload=instance_payload,
        rows=rows,
        lock_payload=lock_payload,
        instance_source_mode=resolved_instances_mode,
    )


def apply_plugin_compile_outputs(
    *,
    inputs: CompileInputs,
    plugin_ctx: Any,
    compilation_owner: Callable[[str], str],
    add_diag: Callable[..., None],
) -> None:
    def _published_outputs() -> dict[str, Any]:
        published_getter = getattr(plugin_ctx, "get_published_data", None)
        if callable(published_getter):
            published_candidate = published_getter()
            if isinstance(published_candidate, dict):
                return published_candidate
        return {}

    def _find_output(*, key: str) -> list[tuple[str, Any]]:
        matches: list[tuple[str, Any]] = []
        for plugin_id, payload in _published_outputs().items():
            if not isinstance(plugin_id, str):
                continue
            if not isinstance(payload, dict):
                continue
            if key in payload:
                matches.append((plugin_id, payload[key]))
        return matches

    def _get_single_output(*, key: str) -> tuple[str, Any] | None:
        matches = _find_output(key=key)
        if not matches:
            return None
        if len(matches) == 1:
            return matches[0]
        add_diag(
            code="E6901",
            severity="error",
            stage="compile",
            message=(
                f"Ambiguous plugin compile output for key '{key}': " f"{[plugin_id for plugin_id, _ in matches]}."
            ),
            path="pipeline:mode",
        )
        return None

    if compilation_owner("model_lock_data") == "plugin":
        lock_payload_entry = _get_single_output(key="lock_payload")
        plugin_lock_payload = lock_payload_entry[1] if isinstance(lock_payload_entry, tuple) else None
        if isinstance(plugin_lock_payload, dict):
            inputs.lock_payload = plugin_lock_payload
            plugin_ctx.model_lock = plugin_lock_payload

    if compilation_owner("module_maps") == "plugin":
        class_map_entry = _get_single_output(key="class_map")
        object_map_entry = _get_single_output(key="object_map")
        plugin_class_map = class_map_entry[1] if isinstance(class_map_entry, tuple) else None
        plugin_object_map = object_map_entry[1] if isinstance(object_map_entry, tuple) else None
        if isinstance(plugin_class_map, dict) and isinstance(plugin_object_map, dict):
            inputs.class_map = plugin_class_map
            inputs.object_map = plugin_object_map
        else:
            add_diag(
                code="E6901",
                severity="error",
                stage="compile",
                message=(
                    "pipeline_mode=plugin-first requires compiler outputs "
                    "'class_map' and 'object_map' to be published by exactly one plugin."
                ),
                path="pipeline:mode",
            )

    if compilation_owner("instance_rows") == "plugin":
        rows_entry = _get_single_output(key="normalized_rows")
        plugin_rows = rows_entry[1] if isinstance(rows_entry, tuple) else None
        if isinstance(plugin_rows, list):
            inputs.rows = [item for item in plugin_rows if isinstance(item, dict)]
        else:
            add_diag(
                code="E6901",
                severity="error",
                stage="compile",
                message=(
                    "pipeline_mode=plugin-first requires compiler output "
                    "'normalized_rows' to be published by exactly one plugin."
                ),
                path="pipeline:mode",
            )

    if compilation_owner("capability_contract_data") == "plugin":
        catalog_entry = _get_single_output(key="catalog_ids")
        packs_entry = _get_single_output(key="packs_map")
        plugin_catalog_ids = catalog_entry[1] if isinstance(catalog_entry, tuple) else None
        plugin_packs_map = packs_entry[1] if isinstance(packs_entry, tuple) else None
        if isinstance(plugin_catalog_ids, list) and isinstance(plugin_packs_map, dict):
            inputs.catalog_ids = {item for item in plugin_catalog_ids if isinstance(item, str)}
            inputs.packs_map = plugin_packs_map
        else:
            add_diag(
                code="E6901",
                severity="error",
                stage="compile",
                message=(
                    "pipeline_mode=plugin-first requires compiler outputs "
                    "'catalog_ids' and 'packs_map' to be published by exactly one plugin."
                ),
                path="pipeline:mode",
            )


def emit_effective_artifact(
    *,
    errors: int,
    compiled_contract_ok: bool,
    enable_plugins: bool,
    plugin_ctx: Any,
    execute_plugins: Callable[..., None],
    artifact_owner: Callable[[str], str],
    output_json: Path,
    effective_payload: dict[str, Any],
    add_diag: Callable[..., None],
    repo_root: Path,
) -> None:
    if errors != 0 or not compiled_contract_ok:
        return

    if enable_plugins and plugin_ctx is not None:
        execute_plugins(stage="generate", ctx=plugin_ctx)

    if artifact_owner("effective_json") == "core":
        output_json.parent.mkdir(parents=True, exist_ok=True)
        output_json.write_text(
            json.dumps(effective_payload, ensure_ascii=True, indent=2, default=str),
            encoding="utf-8",
        )
        add_diag(
            code="I9001",
            severity="info",
            stage="emit",
            message="Compile success.",
            path=str(output_json.relative_to(repo_root).as_posix()),
            confidence=1.0,
        )
        return

    if not output_json.exists():
        add_diag(
            code="E3001",
            severity="error",
            stage="emit",
            message="effective JSON artifact was not generated by plugins.",
            path=str(output_json.relative_to(repo_root).as_posix()),
        )
        return

    add_diag(
        code="I9001",
        severity="info",
        stage="emit",
        message="Compile success.",
        path=str(output_json.relative_to(repo_root).as_posix()),
        confidence=1.0,
    )
