#!/usr/bin/env python3
"""Contract checks for four-level plugin boundary rules."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import yaml

V5_ROOT = Path(__file__).resolve().parents[2]

CLASS_MANIFEST_ROOT = V5_ROOT / "topology" / "class-modules"
OBJECT_MANIFEST_ROOT = V5_ROOT / "topology" / "object-modules"


@dataclass(frozen=True)
class PluginSource:
    path: Path
    kind: str


def _iter_manifests(root: Path) -> Iterable[Path]:
    if not root.exists():
        return []
    return sorted(path for path in root.rglob("plugins.yaml") if path.is_file())


def _iter_plugin_sources(manifest_path: Path) -> Iterable[PluginSource]:
    payload = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
    plugins = payload.get("plugins", [])
    if not isinstance(plugins, list):
        return []

    sources: list[PluginSource] = []
    for row in plugins:
        if not isinstance(row, dict):
            continue
        entry = row.get("entry")
        kind = row.get("kind")
        if not isinstance(entry, str) or ":" not in entry:
            continue
        if not isinstance(kind, str) or not kind:
            continue
        module_rel, _class_name = entry.rsplit(":", 1)
        if not module_rel.endswith(".py"):
            continue
        sources.append(PluginSource(path=(manifest_path.parent / module_rel).resolve(), kind=kind))
    return sources


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
        plugin_files.extend(source.path for source in _iter_plugin_sources(manifest_path))

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
        plugin_files.extend(source.path for source in _iter_plugin_sources(manifest_path))

    violations = _collect_text_violations(
        plugin_files,
        forbidden_markers=("inst.",),
    )
    assert violations == [], (
        "Object-level plugins must not mention instance identifiers: "
        f"{violations}"
    )


def test_module_level_plugins_do_not_mutate_sys_path() -> None:
    plugin_files: list[Path] = []
    for manifest_path in _iter_manifests(CLASS_MANIFEST_ROOT):
        plugin_files.extend(source.path for source in _iter_plugin_sources(manifest_path))
    for manifest_path in _iter_manifests(OBJECT_MANIFEST_ROOT):
        plugin_files.extend(source.path for source in _iter_plugin_sources(manifest_path))

    violations = _collect_text_violations(plugin_files, forbidden_markers=("sys.path.insert(",))
    assert violations == [], (
        "Class/object plugin modules must not mutate sys.path; import paths are kernel responsibility: "
        f"{violations}"
    )


def test_class_and_object_non_generator_plugins_are_specific_to_their_scope() -> None:
    class_violations: list[str] = []
    object_violations: list[str] = []

    for manifest_path in _iter_manifests(CLASS_MANIFEST_ROOT):
        for source in _iter_plugin_sources(manifest_path):
            if source.kind == "generator":
                continue
            if not source.path.exists():
                class_violations.append(f"missing plugin source: {source.path}")
                continue
            body = source.path.read_text(encoding="utf-8")
            if "class." not in body:
                rel = source.path.relative_to(V5_ROOT).as_posix()
                class_violations.append(rel)

    for manifest_path in _iter_manifests(OBJECT_MANIFEST_ROOT):
        for source in _iter_plugin_sources(manifest_path):
            if source.kind == "generator":
                continue
            if not source.path.exists():
                object_violations.append(f"missing plugin source: {source.path}")
                continue
            body = source.path.read_text(encoding="utf-8")
            if "obj." not in body:
                rel = source.path.relative_to(V5_ROOT).as_posix()
                object_violations.append(rel)

    assert class_violations == [], (
        "Class-level non-generator plugins without class-specific names should move to core/global level: "
        f"{class_violations}"
    )
    assert object_violations == [], (
        "Object-level non-generator plugins without object-specific names should move to core/global level: "
        f"{object_violations}"
    )
