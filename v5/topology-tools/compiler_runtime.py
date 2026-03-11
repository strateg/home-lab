"""Runtime helper steps for compile-topology orchestrator."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


@dataclass
class ManifestPathBundle:
    class_modules_root: Path
    object_modules_root: Path
    capability_catalog_path: Path
    capability_packs_path: Path
    instance_bindings_path: Path
    model_lock_path: Path


@dataclass
class CompileInputs:
    class_map: dict[str, dict[str, Any]]
    object_map: dict[str, dict[str, Any]]
    catalog_ids: set[str]
    packs_map: dict[str, dict[str, Any]]
    instance_payload: dict[str, Any] | None
    rows: list[dict[str, Any]]
    lock_payload: dict[str, Any] | None


def discover_plugin_manifests(
    *,
    base_manifest_path: Path,
    class_modules_root: Path,
    object_modules_root: Path,
    manifest_name: str = "plugins.yaml",
) -> list[Path]:
    """Discover plugin manifests with deterministic merge order.

    Merge order policy:
    1. explicit base manifest from CLI/config
    2. class module manifests (sorted lexicographically by relative path)
    3. object module manifests (sorted lexicographically by relative path)
    """

    discovered: list[tuple[int, str, Path]] = []
    roots = ((0, class_modules_root), (1, object_modules_root))
    base_resolved = base_manifest_path.resolve()

    for root_order, root in roots:
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
    manifest_paths: dict[str, Any],
    resolve_repo_path: Callable[[str], Path],
) -> ManifestPathBundle:
    return ManifestPathBundle(
        class_modules_root=resolve_repo_path(str(manifest_paths.get("class_modules_root", ""))),
        object_modules_root=resolve_repo_path(str(manifest_paths.get("object_modules_root", ""))),
        capability_catalog_path=resolve_repo_path(str(manifest_paths.get("capability_catalog", ""))),
        capability_packs_path=resolve_repo_path(str(manifest_paths.get("capability_packs", ""))),
        instance_bindings_path=resolve_repo_path(str(manifest_paths.get("instance_bindings", ""))),
        model_lock_path=resolve_repo_path(str(manifest_paths.get("model_lock", ""))),
    )


def load_core_compile_inputs(
    *,
    paths: ManifestPathBundle,
    compilation_owner: Callable[[str], str],
    load_module_map: Callable[..., dict[str, dict[str, Any]]],
    load_capability_contract: Callable[..., tuple[set[str], dict[str, dict[str, Any]]]],
    load_yaml: Callable[..., dict[str, Any] | None],
    load_instance_rows: Callable[[dict[str, Any]], list[dict[str, Any]]],
) -> CompileInputs:
    if compilation_owner("module_maps") == "core":
        class_map = load_module_map(directory=paths.class_modules_root, module_type="class")
        object_map = load_module_map(directory=paths.object_modules_root, module_type="object")
    else:
        class_map = {}
        object_map = {}

    if compilation_owner("capability_contract_data") == "core":
        catalog_ids, packs_map = load_capability_contract(
            catalog_path=paths.capability_catalog_path,
            packs_path=paths.capability_packs_path,
        )
    else:
        catalog_ids, packs_map = set(), {}

    instance_payload = load_yaml(
        paths.instance_bindings_path,
        code_missing="E1001",
        code_parse="E1003",
        stage="load",
    )
    if compilation_owner("instance_rows") == "core":
        rows = load_instance_rows(instance_payload or {})
    else:
        rows = []

    lock_payload = None
    if compilation_owner("model_lock_data") == "core" and paths.model_lock_path.exists():
        lock_payload = load_yaml(paths.model_lock_path, code_missing="E1001", code_parse="E2401", stage="load")

    return CompileInputs(
        class_map=class_map,
        object_map=object_map,
        catalog_ids=catalog_ids,
        packs_map=packs_map,
        instance_payload=instance_payload,
        rows=rows,
        lock_payload=lock_payload,
    )


def apply_plugin_compile_outputs(
    *,
    inputs: CompileInputs,
    plugin_ctx: Any,
    compilation_owner: Callable[[str], str],
    add_diag: Callable[..., None],
) -> None:
    if compilation_owner("model_lock_data") == "plugin":
        plugin_lock_payload = (
            plugin_ctx.plugin_outputs.get("base.compiler.model_lock_loader", {}).get("lock_payload")
            if isinstance(plugin_ctx.plugin_outputs, dict)
            else None
        )
        plugin_lock_loaded = (
            plugin_ctx.plugin_outputs.get("base.compiler.model_lock_loader", {}).get("model_lock_loaded")
            if isinstance(plugin_ctx.plugin_outputs, dict)
            else None
        )
        if isinstance(plugin_lock_payload, dict):
            inputs.lock_payload = plugin_lock_payload
            plugin_ctx.model_lock = plugin_lock_payload
        if isinstance(plugin_lock_loaded, bool):
            plugin_ctx.config["model_lock_loaded"] = plugin_lock_loaded
        else:
            plugin_ctx.config["model_lock_loaded"] = isinstance(inputs.lock_payload, dict)

    if compilation_owner("module_maps") == "plugin":
        plugin_class_map = (
            plugin_ctx.plugin_outputs.get("base.compiler.module_loader", {}).get("class_map")
            if isinstance(plugin_ctx.plugin_outputs, dict)
            else None
        )
        plugin_object_map = (
            plugin_ctx.plugin_outputs.get("base.compiler.module_loader", {}).get("object_map")
            if isinstance(plugin_ctx.plugin_outputs, dict)
            else None
        )
        if isinstance(plugin_class_map, dict) and isinstance(plugin_object_map, dict):
            inputs.class_map = plugin_class_map
            inputs.object_map = plugin_object_map
        else:
            add_diag(
                code="E6901",
                severity="error",
                stage="validate",
                message=(
                    "pipeline_mode=plugin-first requires compiler plugin "
                    "'base.compiler.module_loader' to publish class_map and object_map."
                ),
                path="pipeline:mode",
            )

    if compilation_owner("instance_rows") == "plugin":
        plugin_rows = (
            plugin_ctx.plugin_outputs.get("base.compiler.instance_rows", {}).get("normalized_rows")
            if isinstance(plugin_ctx.plugin_outputs, dict)
            else None
        )
        if isinstance(plugin_rows, list):
            inputs.rows = [item for item in plugin_rows if isinstance(item, dict)]
        else:
            add_diag(
                code="E6901",
                severity="error",
                stage="validate",
                message=(
                    "pipeline_mode=plugin-first requires compiler plugin "
                    "'base.compiler.instance_rows' to publish normalized_rows."
                ),
                path="pipeline:mode",
            )
        plugin_ctx.config["normalized_rows"] = inputs.rows

    if compilation_owner("capability_contract_data") == "plugin":
        plugin_catalog_ids = (
            plugin_ctx.plugin_outputs.get("base.compiler.capability_contract_loader", {}).get("catalog_ids")
            if isinstance(plugin_ctx.plugin_outputs, dict)
            else None
        )
        plugin_packs_map = (
            plugin_ctx.plugin_outputs.get("base.compiler.capability_contract_loader", {}).get("packs_map")
            if isinstance(plugin_ctx.plugin_outputs, dict)
            else None
        )
        if isinstance(plugin_catalog_ids, list) and isinstance(plugin_packs_map, dict):
            inputs.catalog_ids = {item for item in plugin_catalog_ids if isinstance(item, str)}
            inputs.packs_map = plugin_packs_map
        else:
            add_diag(
                code="E6901",
                severity="error",
                stage="validate",
                message=(
                    "pipeline_mode=plugin-first requires compiler plugin "
                    "'base.compiler.capability_contract_loader' to publish "
                    "catalog_ids and packs_map."
                ),
                path="pipeline:mode",
            )
        plugin_ctx.config["capability_catalog_ids"] = sorted(inputs.catalog_ids)
        plugin_ctx.config["capability_packs"] = inputs.packs_map


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
