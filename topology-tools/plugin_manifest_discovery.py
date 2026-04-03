"""Plugin manifest discovery helpers for deterministic merge order."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


def _sort_key_for_path(*, root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix().casefold()
    except ValueError:
        return path.resolve().as_posix().casefold()


def _path_within_root(*, root: Path, path: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def _resolve_index_entry_path(*, index_dir: Path, entry: Any) -> Path | None:
    if isinstance(entry, str):
        raw = entry.strip()
    elif isinstance(entry, dict):
        raw = ""
        for key in ("plugins_manifest", "manifest", "path"):
            value = entry.get(key)
            if isinstance(value, str) and value.strip():
                raw = value.strip()
                break
    else:
        raw = ""
    if not raw:
        return None

    candidate = Path(raw)
    if not candidate.is_absolute():
        candidate = index_dir / candidate
    return candidate.resolve()


def _manifest_paths_on_disk(*, root: Path, manifest_name: str) -> set[Path]:
    if not root.exists() or not root.is_dir():
        return set()
    return {item.resolve() for item in root.rglob(manifest_name) if item.is_file()}


def validate_module_index_consistency(
    *,
    module_index_path: Path,
    class_modules_root: Path,
    object_modules_root: Path,
    manifest_name: str = "plugins.yaml",
) -> list[str]:
    """Validate module-index.yaml consistency against filesystem manifests."""

    resolved_index = module_index_path.resolve()
    if not resolved_index.exists() or not resolved_index.is_file():
        return [f"module-index file is missing: {resolved_index.as_posix()}"]

    try:
        payload = yaml.safe_load(resolved_index.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as exc:
        return [f"module-index cannot be parsed: {resolved_index.as_posix()}: {exc}"]

    if not isinstance(payload, dict):
        return [f"module-index root must be mapping: {resolved_index.as_posix()}"]

    class_entries = payload.get("class_modules")
    object_entries = payload.get("object_modules")
    if not isinstance(class_entries, list) or not isinstance(object_entries, list):
        return [f"module-index must contain list fields class_modules/object_modules: {resolved_index.as_posix()}"]

    errors: list[str] = []
    index_dir = resolved_index.parent
    indexed_class: set[Path] = set()
    indexed_object: set[Path] = set()

    def _validate_entries(entries: list[Any], *, label: str, root: Path, bucket: set[Path]) -> None:
        for idx, entry in enumerate(entries):
            resolved = _resolve_index_entry_path(index_dir=index_dir, entry=entry)
            if resolved is None:
                errors.append(f"{label}[{idx}] missing plugins_manifest/manifest/path field")
                continue
            if not _path_within_root(root=root, path=resolved):
                errors.append(f"{label}[{idx}] path is outside {root.resolve().as_posix()}: {resolved.as_posix()}")
                continue
            if not resolved.exists() or not resolved.is_file():
                errors.append(f"{label}[{idx}] manifest path does not exist: {resolved.as_posix()}")
                continue
            if resolved in bucket:
                errors.append(f"{label}[{idx}] duplicate manifest entry: {resolved.as_posix()}")
                continue
            bucket.add(resolved)

    _validate_entries(class_entries, label="class_modules", root=class_modules_root, bucket=indexed_class)
    _validate_entries(object_entries, label="object_modules", root=object_modules_root, bucket=indexed_object)

    disk_class = _manifest_paths_on_disk(root=class_modules_root, manifest_name=manifest_name)
    disk_object = _manifest_paths_on_disk(root=object_modules_root, manifest_name=manifest_name)

    for missing in sorted(
        disk_class - indexed_class, key=lambda item: _sort_key_for_path(root=class_modules_root, path=item)
    ):
        errors.append(f"class_modules index missing manifest present on disk: {missing.as_posix()}")
    for missing in sorted(
        disk_object - indexed_object,
        key=lambda item: _sort_key_for_path(root=object_modules_root, path=item),
    ):
        errors.append(f"object_modules index missing manifest present on disk: {missing.as_posix()}")

    for missing in sorted(
        indexed_class - disk_class, key=lambda item: _sort_key_for_path(root=class_modules_root, path=item)
    ):
        errors.append(f"class_modules index points to missing filesystem manifest: {missing.as_posix()}")
    for missing in sorted(
        indexed_object - disk_object,
        key=lambda item: _sort_key_for_path(root=object_modules_root, path=item),
    ):
        errors.append(f"object_modules index points to missing filesystem manifest: {missing.as_posix()}")

    return errors


def _module_index_paths(
    *,
    module_index_path: Path | None,
    class_modules_root: Path,
    object_modules_root: Path,
) -> tuple[list[Path], list[Path]] | None:
    if module_index_path is None:
        return None
    if not module_index_path.exists() or not module_index_path.is_file():
        return None

    try:
        payload = yaml.safe_load(module_index_path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return None
    if not isinstance(payload, dict):
        return None

    class_entries = payload.get("class_modules")
    object_entries = payload.get("object_modules")
    if not isinstance(class_entries, list) or not isinstance(object_entries, list):
        return None

    index_dir = module_index_path.parent
    class_manifests: list[Path] = []
    object_manifests: list[Path] = []

    for entry in class_entries:
        resolved = _resolve_index_entry_path(index_dir=index_dir, entry=entry)
        if resolved is None:
            continue
        if _path_within_root(root=class_modules_root, path=resolved):
            class_manifests.append(resolved)

    for entry in object_entries:
        resolved = _resolve_index_entry_path(index_dir=index_dir, entry=entry)
        if resolved is None:
            continue
        if _path_within_root(root=object_modules_root, path=resolved):
            object_manifests.append(resolved)

    if not class_manifests and not object_manifests:
        return None

    class_manifests = sorted(
        set(class_manifests),
        key=lambda item: _sort_key_for_path(root=class_modules_root, path=item),
    )
    object_manifests = sorted(
        set(object_manifests),
        key=lambda item: _sort_key_for_path(root=object_modules_root, path=item),
    )
    return class_manifests, object_manifests


def discover_plugin_manifest_paths(
    *,
    base_manifest_path: Path,
    class_modules_root: Path,
    object_modules_root: Path,
    project_plugins_root: Path | None = None,
    module_index_path: Path | None = None,
    manifest_name: str = "plugins.yaml",
) -> list[Path]:
    """Discover plugin manifests with deterministic merge order.

    Merge order policy:
    1. explicit base manifest from CLI/config
    2. class module manifests (sorted lexicographically by relative path)
    3. object module manifests (sorted lexicographically by relative path)
    4. project plugin manifests (sorted lexicographically by relative path)

    Optional optimization:
    - if ``module_index_path`` exists and is valid, class/object manifests are loaded
      from module-index entries.
    - if module-index is absent or invalid, discovery falls back to recursive scan.
    """

    discovered: list[tuple[int, str, Path]] = []
    base_resolved = base_manifest_path.resolve()
    indexed_paths = _module_index_paths(
        module_index_path=module_index_path,
        class_modules_root=class_modules_root,
        object_modules_root=object_modules_root,
    )

    if indexed_paths is None:
        roots: list[tuple[int, Path | None]] = [
            (0, class_modules_root),
            (1, object_modules_root),
        ]
        for root_order, root in roots:
            if root is None:
                continue
            if not root.exists() or not root.is_dir():
                continue
            for manifest_path in root.rglob(manifest_name):
                resolved = manifest_path.resolve()
                if resolved == base_resolved:
                    continue
                rel_key = _sort_key_for_path(root=root, path=resolved)
                discovered.append((root_order, rel_key, resolved))
    else:
        class_manifests, object_manifests = indexed_paths
        for manifest_path in class_manifests:
            if manifest_path == base_resolved:
                continue
            rel_key = _sort_key_for_path(root=class_modules_root, path=manifest_path)
            discovered.append((0, rel_key, manifest_path))
        for manifest_path in object_manifests:
            if manifest_path == base_resolved:
                continue
            rel_key = _sort_key_for_path(root=object_modules_root, path=manifest_path)
            discovered.append((1, rel_key, manifest_path))

    if project_plugins_root is not None and project_plugins_root.exists() and project_plugins_root.is_dir():
        for manifest_path in project_plugins_root.rglob(manifest_name):
            resolved = manifest_path.resolve()
            if resolved == base_resolved:
                continue
            rel_key = _sort_key_for_path(root=project_plugins_root, path=resolved)
            discovered.append((2, rel_key, resolved))

    discovered.sort(key=lambda item: (item[0], item[1], item[2].as_posix().casefold()))

    ordered = [base_resolved]
    ordered.extend(path for _, _, path in discovered)
    return ordered
