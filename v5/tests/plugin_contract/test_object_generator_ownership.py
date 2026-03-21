#!/usr/bin/env python3
"""Contract checks for ADR0078 object-generator ownership boundaries."""

from __future__ import annotations

from pathlib import Path

import yaml

V5_ROOT = Path(__file__).resolve().parents[2]

OBJECT_GENERATOR_IDS = {
    "base.generator.terraform_mikrotik",
    "base.generator.bootstrap_mikrotik",
    "base.generator.terraform_proxmox",
    "base.generator.bootstrap_proxmox",
    "base.generator.bootstrap_orangepi",
}

SHIM_FILES = [
    V5_ROOT / "topology-tools" / "plugins" / "generators" / "terraform_mikrotik_generator.py",
    V5_ROOT / "topology-tools" / "plugins" / "generators" / "bootstrap_mikrotik_generator.py",
    V5_ROOT / "topology-tools" / "plugins" / "generators" / "terraform_proxmox_generator.py",
    V5_ROOT / "topology-tools" / "plugins" / "generators" / "bootstrap_proxmox_generator.py",
    V5_ROOT / "topology-tools" / "plugins" / "generators" / "bootstrap_orangepi_generator.py",
]

MODULE_MANIFESTS = [
    V5_ROOT / "topology" / "object-modules" / "mikrotik" / "plugins.yaml",
    V5_ROOT / "topology" / "object-modules" / "proxmox" / "plugins.yaml",
    V5_ROOT / "topology" / "object-modules" / "orangepi" / "plugins.yaml",
]

OBJECT_TEMPLATE_ROOTS = [
    V5_ROOT / "topology" / "object-modules" / "mikrotik" / "templates",
    V5_ROOT / "topology" / "object-modules" / "proxmox" / "templates",
    V5_ROOT / "topology" / "object-modules" / "orangepi" / "templates",
]

LEGACY_OBJECT_TEMPLATE_DIRS = [
    V5_ROOT / "topology-tools" / "templates" / "terraform" / "mikrotik",
    V5_ROOT / "topology-tools" / "templates" / "terraform" / "proxmox",
    V5_ROOT / "topology-tools" / "templates" / "bootstrap" / "mikrotik",
    V5_ROOT / "topology-tools" / "templates" / "bootstrap" / "proxmox",
    V5_ROOT / "topology-tools" / "templates" / "bootstrap" / "orangepi",
]


def _plugin_ids(manifest_path: Path) -> set[str]:
    payload = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
    plugins = payload.get("plugins", [])
    result: set[str] = set()
    for item in plugins:
        if isinstance(item, dict):
            plugin_id = item.get("id")
            if isinstance(plugin_id, str):
                result.add(plugin_id)
    return result


def test_object_generator_shims_are_removed_from_tools_domain() -> None:
    missing = [path for path in SHIM_FILES if path.exists()]
    assert missing == [], f"Object-generator shim files must be removed: {missing}"


def test_central_manifest_does_not_register_object_generators() -> None:
    central_manifest = V5_ROOT / "topology-tools" / "plugins" / "plugins.yaml"
    central_ids = _plugin_ids(central_manifest)
    owned_in_central = sorted(OBJECT_GENERATOR_IDS.intersection(central_ids))
    assert owned_in_central == [], (
        "Object-specific generators must not be registered in central manifest: "
        f"{owned_in_central}"
    )


def test_object_generator_registration_is_owned_by_module_manifests() -> None:
    module_ids: set[str] = set()
    for manifest_path in MODULE_MANIFESTS:
        assert manifest_path.exists(), f"Missing module manifest: {manifest_path}"
        module_ids.update(_plugin_ids(manifest_path))
    missing = sorted(OBJECT_GENERATOR_IDS.difference(module_ids))
    assert missing == [], f"Object-specific generators missing from module manifests: {missing}"


def test_object_specific_templates_are_not_stored_in_tools_domain() -> None:
    leaked_files: list[Path] = []
    for root in LEGACY_OBJECT_TEMPLATE_DIRS:
        if not root.exists():
            continue
        leaked_files.extend(path for path in root.rglob("*") if path.is_file())
    assert leaked_files == [], f"Object-specific templates must not exist in tools domain: {leaked_files}"


def test_object_specific_templates_exist_in_object_modules() -> None:
    missing_roots = [path for path in OBJECT_TEMPLATE_ROOTS if not path.exists()]
    assert missing_roots == [], f"Missing object template roots: {missing_roots}"
