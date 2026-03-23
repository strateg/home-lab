#!/usr/bin/env python3
"""Contract checks for bootstrap file config externalization (ADR0078)."""

from __future__ import annotations

from pathlib import Path

import yaml

V5_ROOT = Path(__file__).resolve().parents[2]
MIKROTIK_MANIFEST = V5_ROOT / "topology" / "object-modules" / "mikrotik" / "plugins.yaml"
PROXMOX_MANIFEST = V5_ROOT / "topology" / "object-modules" / "proxmox" / "plugins.yaml"
ORANGEPI_MANIFEST = V5_ROOT / "topology" / "object-modules" / "orangepi" / "plugins.yaml"
MIKROTIK_GENERATOR = (
    V5_ROOT / "topology" / "object-modules" / "mikrotik" / "plugins" / "bootstrap_mikrotik_generator.py"
)
PROXMOX_GENERATOR = (
    V5_ROOT / "topology" / "object-modules" / "proxmox" / "plugins" / "bootstrap_proxmox_generator.py"
)
ORANGEPI_GENERATOR = (
    V5_ROOT / "topology" / "object-modules" / "orangepi" / "plugins" / "bootstrap_orangepi_generator.py"
)


def _plugin_entry(manifest_path: Path, plugin_id: str) -> dict:
    payload = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
    plugins = payload.get("plugins", [])
    if not isinstance(plugins, list):
        raise AssertionError(f"Invalid plugins payload in {manifest_path}")
    for row in plugins:
        if isinstance(row, dict) and row.get("id") == plugin_id:
            return row
    raise AssertionError(f"Plugin '{plugin_id}' not found in {manifest_path}")


def test_mikrotik_bootstrap_manifest_externalizes_file_mappings() -> None:
    plugin = _plugin_entry(MIKROTIK_MANIFEST, "base.generator.bootstrap_mikrotik")
    config = plugin.get("config")
    assert isinstance(config, dict), "Generator config must be a mapping"
    bootstrap_files = config.get("bootstrap_files")
    assert isinstance(bootstrap_files, list) and bootstrap_files, (
        "bootstrap_files must be configured in module manifest"
    )

    for idx, row in enumerate(bootstrap_files):
        assert isinstance(row, dict), f"bootstrap_files[{idx}] must be mapping/object"
        assert isinstance(row.get("output_file"), str) and row.get("output_file"), (
            f"bootstrap_files[{idx}].output_file must be non-empty string"
        )
        assert isinstance(row.get("template"), str) and row.get("template"), (
            f"bootstrap_files[{idx}].template must be non-empty string"
        )


def test_mikrotik_bootstrap_manifest_schema_declares_file_structure() -> None:
    plugin = _plugin_entry(MIKROTIK_MANIFEST, "base.generator.bootstrap_mikrotik")
    schema = plugin.get("config_schema")
    assert isinstance(schema, dict), "Generator config_schema must be a mapping"
    properties = schema.get("properties")
    assert isinstance(properties, dict), "Generator config_schema.properties must be a mapping"
    files_schema = properties.get("bootstrap_files")
    assert isinstance(files_schema, dict), "config_schema must declare bootstrap_files"
    items = files_schema.get("items")
    assert isinstance(items, dict), "bootstrap_files.items must be a mapping"
    required = items.get("required")
    assert isinstance(required, list), "bootstrap_files.items.required must be a list"
    for field in ("output_file", "template"):
        assert field in required, f"bootstrap_files.items.required must include '{field}'"


def test_mikrotik_bootstrap_generator_has_no_hardcoded_file_mappings() -> None:
    body = MIKROTIK_GENERATOR.read_text(encoding="utf-8")
    assert 'node_root / "init-terraform.rsc"' not in body, (
        "File mappings must not be hardcoded in generator code"
    )
    assert 'node_root / "README.md"' not in body, (
        "File mappings must not be hardcoded in generator code"
    )
    assert '"bootstrap/init-terraform.rsc.j2"' not in body, (
        "Template paths must not be hardcoded in generator code"
    )


def test_proxmox_bootstrap_manifest_externalizes_file_mappings() -> None:
    plugin = _plugin_entry(PROXMOX_MANIFEST, "base.generator.bootstrap_proxmox")
    config = plugin.get("config")
    assert isinstance(config, dict), "Generator config must be a mapping"
    bootstrap_files = config.get("bootstrap_files")
    assert isinstance(bootstrap_files, list) and bootstrap_files, (
        "bootstrap_files must be configured in module manifest"
    )
    post_install_scripts = config.get("post_install_scripts")
    assert isinstance(post_install_scripts, list) and post_install_scripts, (
        "post_install_scripts must be configured in module manifest"
    )

    for idx, row in enumerate(bootstrap_files):
        assert isinstance(row, dict), f"bootstrap_files[{idx}] must be mapping/object"
        assert isinstance(row.get("output_file"), str) and row.get("output_file"), (
            f"bootstrap_files[{idx}].output_file must be non-empty string"
        )
        assert isinstance(row.get("template"), str) and row.get("template"), (
            f"bootstrap_files[{idx}].template must be non-empty string"
        )

    for idx, row in enumerate(post_install_scripts):
        assert isinstance(row, dict), f"post_install_scripts[{idx}] must be mapping/object"
        assert isinstance(row.get("output_file"), str) and row.get("output_file"), (
            f"post_install_scripts[{idx}].output_file must be non-empty string"
        )
        assert isinstance(row.get("template"), str) and row.get("template"), (
            f"post_install_scripts[{idx}].template must be non-empty string"
        )


def test_proxmox_bootstrap_manifest_schema_declares_file_structure() -> None:
    plugin = _plugin_entry(PROXMOX_MANIFEST, "base.generator.bootstrap_proxmox")
    schema = plugin.get("config_schema")
    assert isinstance(schema, dict), "Generator config_schema must be a mapping"
    properties = schema.get("properties")
    assert isinstance(properties, dict), "Generator config_schema.properties must be a mapping"

    files_schema = properties.get("bootstrap_files")
    assert isinstance(files_schema, dict), "config_schema must declare bootstrap_files"

    scripts_schema = properties.get("post_install_scripts")
    assert isinstance(scripts_schema, dict), "config_schema must declare post_install_scripts"


def test_proxmox_bootstrap_generator_has_no_hardcoded_file_mappings() -> None:
    body = PROXMOX_GENERATOR.read_text(encoding="utf-8")
    assert "script_actions = {" not in body, (
        "Script actions must not be hardcoded in generator code"
    )
    assert '"01-install-terraform.sh"' not in body, (
        "Script names must not be hardcoded in generator code"
    )
    assert 'node_root / "answer.toml.example"' not in body, (
        "File mappings must not be hardcoded in generator code"
    )


def test_orangepi_bootstrap_manifest_externalizes_file_mappings() -> None:
    plugin = _plugin_entry(ORANGEPI_MANIFEST, "base.generator.bootstrap_orangepi")
    config = plugin.get("config")
    assert isinstance(config, dict), "Generator config must be a mapping"
    bootstrap_files = config.get("bootstrap_files")
    assert isinstance(bootstrap_files, list) and bootstrap_files, (
        "bootstrap_files must be configured in module manifest"
    )

    for idx, row in enumerate(bootstrap_files):
        assert isinstance(row, dict), f"bootstrap_files[{idx}] must be mapping/object"
        assert isinstance(row.get("output_file"), str) and row.get("output_file"), (
            f"bootstrap_files[{idx}].output_file must be non-empty string"
        )
        assert isinstance(row.get("template"), str) and row.get("template"), (
            f"bootstrap_files[{idx}].template must be non-empty string"
        )


def test_orangepi_bootstrap_manifest_schema_declares_file_structure() -> None:
    plugin = _plugin_entry(ORANGEPI_MANIFEST, "base.generator.bootstrap_orangepi")
    schema = plugin.get("config_schema")
    assert isinstance(schema, dict), "Generator config_schema must be a mapping"
    properties = schema.get("properties")
    assert isinstance(properties, dict), "Generator config_schema.properties must be a mapping"
    files_schema = properties.get("bootstrap_files")
    assert isinstance(files_schema, dict), "config_schema must declare bootstrap_files"
    items = files_schema.get("items")
    assert isinstance(items, dict), "bootstrap_files.items must be a mapping"
    required = items.get("required")
    assert isinstance(required, list), "bootstrap_files.items.required must be a list"
    for field in ("output_file", "template"):
        assert field in required, f"bootstrap_files.items.required must include '{field}'"


def test_orangepi_bootstrap_generator_has_no_hardcoded_file_mappings() -> None:
    body = ORANGEPI_GENERATOR.read_text(encoding="utf-8")
    assert 'cloud_init_root / "user-data.example"' not in body, (
        "File mappings must not be hardcoded in generator code"
    )
    assert 'cloud_init_root / "meta-data"' not in body, (
        "File mappings must not be hardcoded in generator code"
    )
    assert '"bootstrap/user-data.example.j2"' not in body, (
        "Template paths must not be hardcoded in generator code"
    )
