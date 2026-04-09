#!/usr/bin/env python3
"""Contract tests for plugin manifest ID naming policy."""

from __future__ import annotations

import re
from pathlib import Path

import yaml

V5_ROOT = Path(__file__).resolve().parents[2]
BASE_MANIFEST = V5_ROOT / "topology-tools" / "plugins" / "plugins.yaml"
CLASS_ROOT = V5_ROOT / "topology" / "class-modules"
OBJECT_ROOT = V5_ROOT / "topology" / "object-modules"
PROJECT_PLUGIN_ROOT = V5_ROOT / "projects" / "home-lab" / "plugins"

# Transitional policy: support dot/underscore styles, require lowercase and segmented IDs.
ID_PATTERN = re.compile(r"^[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+$")


def _iter_manifest_paths() -> list[Path]:
    manifests: list[Path] = []
    if BASE_MANIFEST.exists():
        manifests.append(BASE_MANIFEST)
    if CLASS_ROOT.exists():
        manifests.extend(sorted(path for path in CLASS_ROOT.rglob("plugins.yaml") if path.is_file()))
    if OBJECT_ROOT.exists():
        manifests.extend(sorted(path for path in OBJECT_ROOT.rglob("plugins.yaml") if path.is_file()))
    if PROJECT_PLUGIN_ROOT.exists():
        manifests.extend(sorted(path for path in PROJECT_PLUGIN_ROOT.rglob("plugins.yaml") if path.is_file()))
    return manifests


def _load_plugin_rows(path: Path) -> list[dict[str, object]]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    plugins = payload.get("plugins", [])
    if not isinstance(plugins, list):
        return []
    return [item for item in plugins if isinstance(item, dict)]


def test_manifest_plugin_ids_match_transitional_policy() -> None:
    violations: list[str] = []
    for manifest_path in _iter_manifest_paths():
        rel = manifest_path.relative_to(V5_ROOT).as_posix()
        for row in _load_plugin_rows(manifest_path):
            plugin_id = row.get("id")
            if not isinstance(plugin_id, str) or not plugin_id:
                continue
            if ID_PATTERN.match(plugin_id):
                continue
            violations.append(f"{rel}:{plugin_id}")

    assert violations == [], f"Plugin IDs violate naming policy: {violations}"


def test_manifest_plugin_ids_are_globally_unique() -> None:
    seen: dict[str, str] = {}
    duplicates: list[str] = []

    for manifest_path in _iter_manifest_paths():
        rel = manifest_path.relative_to(V5_ROOT).as_posix()
        for row in _load_plugin_rows(manifest_path):
            plugin_id = row.get("id")
            if not isinstance(plugin_id, str) or not plugin_id:
                continue
            previous = seen.get(plugin_id)
            if previous is None:
                seen[plugin_id] = rel
                continue
            duplicates.append(f"{plugin_id}: {previous} and {rel}")

    assert duplicates == [], f"Duplicate plugin IDs across manifests: {duplicates}"
