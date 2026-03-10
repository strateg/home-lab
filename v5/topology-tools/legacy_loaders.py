"""Legacy loading/normalization helpers extracted from compile-topology.py.

These functions preserve legacy behavior while keeping the orchestrator thin.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Iterable


def iter_yaml_files(directory: Path) -> Iterable[Path]:
    if not directory.exists():
        return []
    return sorted(path for path in directory.rglob("*.yaml") if path.is_file())


def is_module_file(path: Path, module_type: str) -> bool:
    if module_type == "class":
        return path.name.startswith("class.")
    if module_type == "object":
        return path.name.startswith("obj.")
    return True


def load_module_map(
    *,
    directory: Path,
    module_type: str,
    load_yaml: Callable[[Path, str, str, str], dict[str, Any] | None],
    add_diag: Callable[..., None],
    repo_root: Path,
) -> dict[str, dict[str, Any]]:
    module_map: dict[str, dict[str, Any]] = {}
    files = [path for path in iter_yaml_files(directory) if is_module_file(path, module_type)]
    if not files:
        add_diag(
            code="E1001",
            severity="error",
            stage="load",
            message=f"No {module_type} YAML files found under {directory}",
            path=str(directory.relative_to(repo_root).as_posix()),
        )
        return module_map

    for path in files:
        payload = load_yaml(path, "E1001", "E1003", "load")
        if payload is None:
            continue
        module_key = "class" if module_type == "class" else "object"
        item_id = payload.get(module_key)
        if not isinstance(item_id, str) or not item_id:
            add_diag(
                code="E3201",
                severity="error",
                stage="validate",
                message=f"{module_type} module is missing '{module_key}'.",
                path=str(path.relative_to(repo_root).as_posix()),
            )
            continue
        if item_id in module_map:
            add_diag(
                code="E2102",
                severity="error",
                stage="resolve",
                message=f"Duplicate {module_type} {module_key} '{item_id}'.",
                path=str(path.relative_to(repo_root).as_posix()),
            )
            continue
        module_map[item_id] = {"payload": payload, "path": path}
    return module_map


def load_capability_contract(
    *,
    catalog_path: Path,
    packs_path: Path,
    load_yaml: Callable[[Path, str, str, str], dict[str, Any] | None],
    add_diag: Callable[..., None],
    repo_root: Path,
) -> tuple[set[str], dict[str, dict[str, Any]]]:
    catalog_ids: set[str] = set()
    packs_map: dict[str, dict[str, Any]] = {}

    catalog_payload = load_yaml(catalog_path, "E1001", "E1003", "load")
    if catalog_payload is None:
        return catalog_ids, packs_map
    capabilities = catalog_payload.get("capabilities")
    if not isinstance(capabilities, list):
        add_diag(
            code="E3201",
            severity="error",
            stage="validate",
            message="capability catalog must define list key 'capabilities'.",
            path=str(catalog_path.relative_to(repo_root).as_posix()),
        )
        return catalog_ids, packs_map
    for idx, item in enumerate(capabilities):
        path = f"{catalog_path.relative_to(repo_root).as_posix()}:capabilities[{idx}]"
        if not isinstance(item, dict):
            add_diag(
                code="E3201",
                severity="error",
                stage="validate",
                message="capability entry must be object.",
                path=path,
            )
            continue
        cap_id = item.get("id")
        if not isinstance(cap_id, str) or not cap_id:
            add_diag(
                code="E3201",
                severity="error",
                stage="validate",
                message="capability entry missing non-empty id.",
                path=path,
            )
            continue
        if cap_id in catalog_ids:
            add_diag(
                code="E2102",
                severity="error",
                stage="resolve",
                message=f"duplicate capability id '{cap_id}' in catalog.",
                path=path,
            )
            continue
        catalog_ids.add(cap_id)

    packs_payload = load_yaml(packs_path, "E1001", "E1003", "load")
    if packs_payload is None:
        return catalog_ids, packs_map
    packs = packs_payload.get("packs")
    if not isinstance(packs, list):
        add_diag(
            code="E3201",
            severity="error",
            stage="validate",
            message="capability packs file must define list key 'packs'.",
            path=str(packs_path.relative_to(repo_root).as_posix()),
        )
        return catalog_ids, packs_map
    for idx, item in enumerate(packs):
        path = f"{packs_path.relative_to(repo_root).as_posix()}:packs[{idx}]"
        if not isinstance(item, dict):
            add_diag(
                code="E3201",
                severity="error",
                stage="validate",
                message="capability pack entry must be object.",
                path=path,
            )
            continue
        pack_id = item.get("id")
        if not isinstance(pack_id, str) or not pack_id:
            add_diag(
                code="E3201",
                severity="error",
                stage="validate",
                message="capability pack entry missing non-empty id.",
                path=path,
            )
            continue
        if pack_id in packs_map:
            add_diag(
                code="E2102",
                severity="error",
                stage="resolve",
                message=f"duplicate capability pack id '{pack_id}'.",
                path=path,
            )
            continue
        pack_caps = item.get("capabilities")
        if not isinstance(pack_caps, list):
            add_diag(
                code="E3201",
                severity="error",
                stage="validate",
                message=f"pack '{pack_id}' must define list key 'capabilities'.",
                path=path,
            )
            continue
        for cap in pack_caps:
            if not isinstance(cap, str):
                add_diag(
                    code="E3201",
                    severity="error",
                    stage="validate",
                    message=f"pack '{pack_id}' has non-string capability entry.",
                    path=path,
                )
                continue
            if not cap.startswith("vendor.") and cap not in catalog_ids:
                add_diag(
                    code="E3201",
                    severity="error",
                    stage="validate",
                    message=f"pack '{pack_id}' references unknown capability '{cap}'.",
                    path=path,
                )
        packs_map[pack_id] = item
    return catalog_ids, packs_map


def load_instance_rows(
    *,
    payload: dict[str, Any],
    add_diag: Callable[..., None],
) -> list[dict[str, Any]]:
    bindings = payload.get("instance_bindings")
    if not isinstance(bindings, dict):
        add_diag(
            code="E3201",
            severity="error",
            stage="validate",
            message="instance-bindings root must contain mapping 'instance_bindings'.",
            path="instance_bindings",
        )
        return []

    rows: list[dict[str, Any]] = []
    seen_instances: set[str] = set()
    for group_name, group_rows in bindings.items():
        if not isinstance(group_rows, list):
            add_diag(
                code="E3201",
                severity="error",
                stage="validate",
                message=f"instance_bindings.{group_name} must be a list.",
                path=f"instance_bindings.{group_name}",
            )
            continue

        for idx, row in enumerate(group_rows):
            if not isinstance(row, dict):
                add_diag(
                    code="E3201",
                    severity="error",
                    stage="validate",
                    message="Instance row must be an object.",
                    path=f"instance_bindings.{group_name}[{idx}]",
                )
                continue
            instance_id = row.get("instance")
            layer = row.get("layer")
            class_ref = row.get("class_ref")
            object_ref = row.get("object_ref")
            firmware_ref = row.get("firmware_ref")
            os_refs = row.get("os_refs")

            if not isinstance(instance_id, str) or not instance_id:
                add_diag(
                    code="E3201",
                    severity="error",
                    stage="validate",
                    message="Instance row must define non-empty 'instance'.",
                    path=f"instance_bindings.{group_name}[{idx}].instance",
                )
                continue
            if instance_id in seen_instances:
                add_diag(
                    code="E2102",
                    severity="error",
                    stage="resolve",
                    message=f"Duplicate instance '{instance_id}'.",
                    path=f"instance_bindings.{group_name}[{idx}]",
                )
                continue
            seen_instances.add(instance_id)

            if not isinstance(class_ref, str) or not class_ref:
                add_diag(
                    code="E3201",
                    severity="error",
                    stage="validate",
                    message="Instance row must define non-empty 'class_ref'.",
                    path=f"instance_bindings.{group_name}[{idx}].class_ref",
                )
            if not isinstance(object_ref, str) or not object_ref:
                add_diag(
                    code="E3201",
                    severity="error",
                    stage="validate",
                    message="Instance row must define non-empty 'object_ref'.",
                    path=f"instance_bindings.{group_name}[{idx}].object_ref",
                )
            if not isinstance(layer, str) or not layer:
                add_diag(
                    code="E3201",
                    severity="error",
                    stage="validate",
                    message="Instance row must define non-empty 'layer'.",
                    path=f"instance_bindings.{group_name}[{idx}].layer",
                )
            if firmware_ref is not None and (not isinstance(firmware_ref, str) or not firmware_ref):
                add_diag(
                    code="E3201",
                    severity="error",
                    stage="validate",
                    message="firmware_ref must be non-empty string when set.",
                    path=f"instance_bindings.{group_name}[{idx}].firmware_ref",
                )
            if os_refs is not None and not isinstance(os_refs, list):
                add_diag(
                    code="E3201",
                    severity="error",
                    stage="validate",
                    message="os_refs must be a list when set.",
                    path=f"instance_bindings.{group_name}[{idx}].os_refs",
                )
                os_refs = []

            embedded_in = row.get("embedded_in")
            if embedded_in is not None and (not isinstance(embedded_in, str) or not embedded_in):
                add_diag(
                    code="E3201",
                    severity="error",
                    stage="validate",
                    message="embedded_in must be non-empty string when set.",
                    path=f"instance_bindings.{group_name}[{idx}].embedded_in",
                )
                embedded_in = None

            normalized_os_refs: list[str] = []
            if isinstance(os_refs, list):
                for os_idx, os_ref in enumerate(os_refs):
                    if not isinstance(os_ref, str) or not os_ref:
                        add_diag(
                            code="E3201",
                            severity="error",
                            stage="validate",
                            message="os_refs entries must be non-empty strings.",
                            path=f"instance_bindings.{group_name}[{idx}].os_refs[{os_idx}]",
                        )
                        continue
                    normalized_os_refs.append(os_ref)

            rows.append(
                {
                    "group": group_name,
                    "instance": instance_id,
                    "layer": layer,
                    "source_id": row.get("source_id", instance_id),
                    "class_ref": class_ref,
                    "object_ref": object_ref,
                    "status": row.get("status", "pending"),
                    "notes": row.get("notes", ""),
                    "runtime": row.get("runtime"),
                    "firmware_ref": firmware_ref if isinstance(firmware_ref, str) and firmware_ref else None,
                    "os_refs": normalized_os_refs,
                    "embedded_in": embedded_in if isinstance(embedded_in, str) and embedded_in else None,
                }
            )
    return rows
