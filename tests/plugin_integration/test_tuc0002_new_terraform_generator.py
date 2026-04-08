#!/usr/bin/env python3
"""Integration checks for TUC-0002 Terraform generator onboarding."""

from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]

EXPECTED_TERRAFORM_PLUGIN_IDS = {
    "object.mikrotik.generator.terraform",
    "object.proxmox.generator.terraform",
}


def _list_plugin_ids(manifest_path: Path) -> set[str]:
    payload = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
    plugins = payload.get("plugins", [])
    if not isinstance(plugins, list):
        return set()
    out: set[str] = set()
    for row in plugins:
        if not isinstance(row, dict):
            continue
        plugin_id = row.get("id")
        if isinstance(plugin_id, str) and plugin_id.strip():
            out.add(plugin_id.strip())
    return out


def test_tuc0002_expected_terraform_generators_exist_in_manifests() -> None:
    manifest_paths = [
        REPO_ROOT / "topology-tools" / "plugins" / "plugins.yaml",
        *sorted((REPO_ROOT / "topology" / "object-modules").glob("*/plugins.yaml")),
    ]
    discovered: set[str] = set()
    for manifest in manifest_paths:
        if manifest.exists():
            discovered.update(_list_plugin_ids(manifest))

    missing = sorted(EXPECTED_TERRAFORM_PLUGIN_IDS - discovered)
    assert not missing, f"missing expected terraform plugin ids: {missing}"
