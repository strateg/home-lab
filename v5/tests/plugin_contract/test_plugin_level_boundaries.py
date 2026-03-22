#!/usr/bin/env python3
"""Contract checks for four-level plugin boundary rules."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

import yaml

V5_ROOT = Path(__file__).resolve().parents[2]

CLASS_MANIFEST_ROOT = V5_ROOT / "topology" / "class-modules"
OBJECT_MANIFEST_ROOT = V5_ROOT / "topology" / "object-modules"


def _iter_manifests(root: Path) -> Iterable[Path]:
    if not root.exists():
        return []
    return sorted(path for path in root.rglob("plugins.yaml") if path.is_file())


def _iter_plugin_source_files(manifest_path: Path) -> Iterable[Path]:
    payload = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
    plugins = payload.get("plugins", [])
    if not isinstance(plugins, list):
        return []

    files: list[Path] = []
    for row in plugins:
        if not isinstance(row, dict):
            continue
        entry = row.get("entry")
        if not isinstance(entry, str) or ":" not in entry:
            continue
        module_rel, _class_name = entry.rsplit(":", 1)
        if not module_rel.endswith(".py"):
            continue
        files.append((manifest_path.parent / module_rel).resolve())
    return files


def _collect_text_violations(files: Iterable[Path], *, forbidden_markers: tuple[str, ...]) -> list[str]:
    violations: list[str] = []
    for file_path in files:
        if not file_path.exists():
            violations.append(f"missing plugin source: {file_path}")
            continue
        body = file_path.read_text(encoding="utf-8")
        leaked = [marker for marker in forbidden_markers if marker in body]
        if leaked:
            rel = file_path.relative_to(V5_ROOT).as_posix()
            violations.append(f"{rel}: forbidden markers {leaked}")
    return violations


def test_class_level_plugins_do_not_reference_object_or_instance_ids() -> None:
    plugin_files: list[Path] = []
    for manifest_path in _iter_manifests(CLASS_MANIFEST_ROOT):
        plugin_files.extend(_iter_plugin_source_files(manifest_path))

    violations = _collect_text_violations(
        plugin_files,
        forbidden_markers=("obj.", "inst."),
    )
    assert violations == [], (
        "Class-level plugins must not mention object or instance identifiers: "
        f"{violations}"
    )


def test_object_level_plugins_do_not_reference_instance_ids() -> None:
    plugin_files: list[Path] = []
    for manifest_path in _iter_manifests(OBJECT_MANIFEST_ROOT):
        plugin_files.extend(_iter_plugin_source_files(manifest_path))

    violations = _collect_text_violations(
        plugin_files,
        forbidden_markers=("inst.",),
    )
    assert violations == [], (
        "Object-level plugins must not mention instance identifiers: "
        f"{violations}"
    )
