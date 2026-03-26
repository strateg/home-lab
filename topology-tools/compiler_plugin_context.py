"""Plugin context construction helpers for compile-topology."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from kernel import PluginContext


def create_plugin_context(
    *,
    manifest_path: Path,
    repo_root: Path,
    runtime_profile: str,
    strict_model_lock: bool,
    pipeline_mode: str,
    parity_gate: bool,
    raw_manifest: dict[str, Any],
    run_generated_at: str,
    compiled_model_version: str,
    compiler_pipeline_version: str,
    source_manifest_digest: str,
    class_modules_root: Path,
    object_modules_root: Path,
    project_id: str,
    project_root: Path,
    project_manifest_path: Path,
    class_map: dict[str, dict[str, Any]],
    object_map: dict[str, dict[str, Any]],
    instance_bindings: dict[str, Any],
    capability_catalog_path: Path,
    capability_packs_path: Path,
    model_lock_path: Path,
    lock_payload: dict[str, Any] | None,
    output_dir: Path,
    generator_artifacts_root: Path,
    workspace_root: Path,
    dist_root: Path,
    signing_backend: str,
    release_tag: str,
    sbom_output_dir: Path,
    source_file: Path,
    compiled_file: Path,
    require_new_model: bool,
    secrets_mode: str,
    secrets_root: str,
    validation_owner: Callable[[str], str],
    compilation_owner: Callable[[str], str],
    artifact_owner: Callable[[str], str],
) -> PluginContext:
    try:
        topology_path_value = str(manifest_path.relative_to(repo_root).as_posix())
    except ValueError:
        topology_path_value = str(manifest_path.as_posix())

    try:
        artifacts_root_value = str(generator_artifacts_root.relative_to(repo_root).as_posix())
    except ValueError:
        artifacts_root_value = str(generator_artifacts_root.as_posix())
    try:
        workspace_root_value = str(workspace_root.relative_to(repo_root).as_posix())
    except ValueError:
        workspace_root_value = str(workspace_root.as_posix())
    try:
        dist_root_value = str(dist_root.relative_to(repo_root).as_posix())
    except ValueError:
        dist_root_value = str(dist_root.as_posix())
    try:
        sbom_output_dir_value = str(sbom_output_dir.relative_to(repo_root).as_posix())
    except ValueError:
        sbom_output_dir_value = str(sbom_output_dir.as_posix())
    try:
        project_root_value = str(project_root.relative_to(repo_root).as_posix())
    except ValueError:
        project_root_value = str(project_root.as_posix())
    try:
        project_manifest_value = str(project_manifest_path.relative_to(repo_root).as_posix())
    except ValueError:
        project_manifest_value = str(project_manifest_path.as_posix())

    embedded_in_owner = validation_owner("embedded_in")
    model_lock_owner = validation_owner("model_lock")
    references_owner = validation_owner("references")
    capability_contract_owner = validation_owner("capability_contract")
    instance_rows_owner = compilation_owner("instance_rows")
    capability_contract_data_owner = compilation_owner("capability_contract_data")
    effective_json_owner = artifact_owner("effective_json")
    return PluginContext(
        topology_path=topology_path_value,
        profile=runtime_profile,
        model_lock=lock_payload or {},
        raw_yaml=raw_manifest,
        classes={class_id: item["payload"] for class_id, item in class_map.items()},
        objects={object_id: item["payload"] for object_id, item in object_map.items()},
        instance_bindings=instance_bindings,
        config={
            "strict_mode": strict_model_lock,
            "pipeline_mode": pipeline_mode,
            "parity_gate": parity_gate,
            "compile_generated_at": run_generated_at,
            "compiled_model_version": compiled_model_version,
            "compiler_pipeline_version": compiler_pipeline_version,
            "source_manifest_digest": source_manifest_digest,
            "runtime_profile": runtime_profile,
            "validation_owner_embedded_in": embedded_in_owner,
            "validation_owner_model_lock": model_lock_owner,
            "validation_owner_references": references_owner,
            "validation_owner_capability_contract": capability_contract_owner,
            "compilation_owner_instance_rows": instance_rows_owner,
            "compilation_owner_capability_contract_data": capability_contract_data_owner,
            "generation_owner_effective_json": effective_json_owner,
            "compilation_owner_module_maps": compilation_owner("module_maps"),
            "compilation_owner_model_lock_data": compilation_owner("model_lock_data"),
            "capability_catalog_path": str(capability_catalog_path),
            "capability_packs_path": str(capability_packs_path),
            "model_lock_path": str(model_lock_path),
            "class_modules_root": str(class_modules_root),
            "object_modules_root": str(object_modules_root),
            "project_id": project_id,
            "project_root": project_root_value,
            "project_manifest_path": project_manifest_value,
            "require_new_model": require_new_model,
            "generator_artifacts_root": artifacts_root_value,
            "workspace_root": workspace_root_value,
            "dist_root": dist_root_value,
            "signing_backend": signing_backend,
            "release_tag": release_tag,
            "sbom_output_dir": sbom_output_dir_value,
            "secrets_mode": secrets_mode,
            "secrets_root": secrets_root,
            "repo_root": str(repo_root),
        },
        output_dir=str(output_dir),
        workspace_root=workspace_root_value,
        dist_root=dist_root_value,
        signing_backend=signing_backend,
        release_tag=release_tag,
        sbom_output_dir=sbom_output_dir_value,
        source_file=str(source_file),
        compiled_file=str(compiled_file),
    )
