#!/usr/bin/env python3
"""Contract checks for ADR0086 Wave 3 plugin layout policy."""

from __future__ import annotations

from pathlib import Path

import yaml

V5_ROOT = Path(__file__).resolve().parents[2]
CLASS_ROOT = V5_ROOT / "topology" / "class-modules"
OBJECT_ROOT = V5_ROOT / "topology" / "object-modules"

REMOVED_EMPTY_MANIFESTS = (
    V5_ROOT / "topology" / "class-modules" / "router" / "plugins.yaml",
    V5_ROOT / "topology" / "object-modules" / "glinet" / "plugins.yaml",
)

REMOVED_ROUTER_WRAPPER_IDS = {
    "class_router.validator_json.router_data_channel_interface",
    "object_glinet.validator_json.router_ports",
    "object_mikrotik.validator_json.router_ports",
}

NETWORK_VALIDATOR_OLD_ID = "object_network.validator_json.ethernet_cable_endpoints"
NETWORK_VALIDATOR_NEW_ID = "object.network.validator_json.ethernet_cable_endpoints"
NETWORK_MANIFEST = V5_ROOT / "topology" / "object-modules" / "network" / "plugins.yaml"


def _iter_module_manifests() -> list[Path]:
    manifests: list[Path] = []
    manifests.extend(sorted(path for path in CLASS_ROOT.rglob("plugins.yaml") if path.is_file()))
    manifests.extend(sorted(path for path in OBJECT_ROOT.rglob("plugins.yaml") if path.is_file()))
    return manifests


def _load_plugin_ids(manifest_path: Path) -> list[str]:
    payload = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
    plugins = payload.get("plugins", [])
    if not isinstance(plugins, list):
        return []
    result: list[str] = []
    for row in plugins:
        if not isinstance(row, dict):
            continue
        plugin_id = row.get("id")
        if isinstance(plugin_id, str) and plugin_id:
            result.append(plugin_id)
    return result


def test_removed_empty_manifests_do_not_reappear() -> None:
    leaked = [path.relative_to(V5_ROOT).as_posix() for path in REMOVED_EMPTY_MANIFESTS if path.exists()]
    assert leaked == [], f"Removed empty manifests must not reappear: {leaked}"


def test_module_manifests_are_non_empty_when_present() -> None:
    empty_manifests: list[str] = []
    for manifest_path in _iter_module_manifests():
        payload = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
        plugins = payload.get("plugins", [])
        if not isinstance(plugins, list) or not plugins:
            empty_manifests.append(manifest_path.relative_to(V5_ROOT).as_posix())
    assert empty_manifests == [], f"Module manifests must be removed if they are empty: {empty_manifests}"


def test_removed_router_wrapper_plugin_ids_are_absent_from_module_manifests() -> None:
    leaked: list[str] = []
    for manifest_path in _iter_module_manifests():
        rel = manifest_path.relative_to(V5_ROOT).as_posix()
        for plugin_id in _load_plugin_ids(manifest_path):
            if plugin_id in REMOVED_ROUTER_WRAPPER_IDS:
                leaked.append(f"{rel}:{plugin_id}")
    assert leaked == [], f"Removed router wrapper plugin IDs must remain absent: {leaked}"


def test_network_validator_id_is_normalized_to_dot_style() -> None:
    assert NETWORK_MANIFEST.exists(), f"Missing network module manifest: {NETWORK_MANIFEST}"
    plugin_ids = set(_load_plugin_ids(NETWORK_MANIFEST))
    assert NETWORK_VALIDATOR_NEW_ID in plugin_ids
    assert NETWORK_VALIDATOR_OLD_ID not in plugin_ids
