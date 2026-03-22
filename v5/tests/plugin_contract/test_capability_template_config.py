#!/usr/bin/env python3
"""Contract checks for capability-template config externalization (ADR0078 WP9)."""

from __future__ import annotations

from pathlib import Path

import yaml

V5_ROOT = Path(__file__).resolve().parents[2]
MIKROTIK_MANIFEST = V5_ROOT / "topology" / "object-modules" / "mikrotik" / "plugins.yaml"
PROXMOX_MANIFEST = V5_ROOT / "topology" / "object-modules" / "proxmox" / "plugins.yaml"
MIKROTIK_GENERATOR = (
    V5_ROOT / "topology" / "object-modules" / "mikrotik" / "plugins" / "terraform_mikrotik_generator.py"
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


def test_mikrotik_manifest_externalizes_capability_template_mapping() -> None:
    plugin = _plugin_entry(MIKROTIK_MANIFEST, "base.generator.terraform_mikrotik")
    config = plugin.get("config")
    assert isinstance(config, dict), "Generator config must be a mapping"
    capability_templates = config.get("capability_templates")
    assert isinstance(capability_templates, list) and capability_templates, (
        "capability_templates must be configured in module manifest"
    )

    for idx, row in enumerate(capability_templates):
        assert isinstance(row, dict), f"capability_templates[{idx}] must be mapping/object"
        assert isinstance(row.get("capability_key"), str) and row.get("capability_key"), (
            f"capability_templates[{idx}].capability_key must be non-empty string"
        )
        assert isinstance(row.get("template"), str) and row.get("template"), (
            f"capability_templates[{idx}].template must be non-empty string"
        )
        assert isinstance(row.get("output_file"), str) and row.get("output_file"), (
            f"capability_templates[{idx}].output_file must be non-empty string"
        )
    assert "mikrotik_api_host" in config
    assert "mikrotik_host" in config


def test_mikrotik_manifest_schema_declares_capability_template_structure() -> None:
    plugin = _plugin_entry(MIKROTIK_MANIFEST, "base.generator.terraform_mikrotik")
    schema = plugin.get("config_schema")
    assert isinstance(schema, dict), "Generator config_schema must be a mapping"
    properties = schema.get("properties")
    assert isinstance(properties, dict), "Generator config_schema.properties must be a mapping"
    cap_schema = properties.get("capability_templates")
    assert isinstance(cap_schema, dict), "config_schema must declare capability_templates"
    items = cap_schema.get("items")
    assert isinstance(items, dict), "capability_templates.items must be a mapping"
    required = items.get("required")
    assert isinstance(required, list), "capability_templates.items.required must be a list"
    for field in ("capability_key", "template", "output_file"):
        assert field in required, f"capability_templates.items.required must include '{field}'"
    assert "mikrotik_api_host" in properties
    assert "mikrotik_host" in properties


def test_proxmox_manifest_schema_declares_api_url_override() -> None:
    plugin = _plugin_entry(PROXMOX_MANIFEST, "base.generator.terraform_proxmox")
    config = plugin.get("config")
    assert isinstance(config, dict), "Generator config must be a mapping"
    assert "proxmox_api_url" in config
    schema = plugin.get("config_schema")
    assert isinstance(schema, dict), "Generator config_schema must be a mapping"
    properties = schema.get("properties")
    assert isinstance(properties, dict), "Generator config_schema.properties must be a mapping"
    assert "proxmox_api_url" in properties


def test_mikrotik_generator_has_no_hardcoded_capability_template_fallbacks() -> None:
    body = MIKROTIK_GENERATOR.read_text(encoding="utf-8")
    assert "_DEFAULT_CAPABILITY_TEMPLATES" not in body, "Capability-template defaults must not be hardcoded in code"
    assert 'templates["qos.tf"]' not in body, "Capability template selection must not be hardcoded in generator code"
    assert 'templates["vpn.tf"]' not in body, "Capability template selection must not be hardcoded in generator code"
    assert 'templates["containers.tf"]' not in body, (
        "Capability template selection must not be hardcoded in generator code"
    )
