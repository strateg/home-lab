"""Plugin manifest discovery helpers for deterministic merge order."""

from __future__ import annotations

from pathlib import Path


def discover_plugin_manifest_paths(
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
    roots: list[tuple[int, Path | None]] = [
        (0, class_modules_root),
        (1, object_modules_root),
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
