#!/usr/bin/env python3
"""Contract checks for capability-template config externalization (ADR0078 WP9)."""

from __future__ import annotations

from pathlib import Path

import yaml

V5_ROOT = Path(__file__).resolve().parents[2]
MIKROTIK_MANIFEST = V5_ROOT / "topology" / "object-modules" / "mikrotik" / "plugins.yaml"
PROXMOX_MANIFEST = V5_ROOT / "topology" / "object-modules" / "proxmox" / "plugins.yaml"
MIKROTIK_GENERATOR = (
    V5_ROOT / "topology" / "object-modules" / "mikrotik" / "plugins" / "generators" / "terraform_mikrotik_generator.py"
)
PROXMOX_GENERATOR = (
    V5_ROOT / "topology" / "object-modules" / "proxmox" / "plugins" / "generators" / "terraform_proxmox_generator.py"
)
# ADR0078 WP-002: Shared capability helpers (code extracted from generators)
CAPABILITY_HELPERS = V5_ROOT / "topology" / "object-modules" / "_shared" / "plugins" / "capability_helpers.py"


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
    plugin = _plugin_entry(MIKROTIK_MANIFEST, "object.mikrotik.generator.terraform")
    config = plugin.get("config")
    assert isinstance(config, dict), "Generator config must be a mapping"
    capability_templates = config.get("capability_templates")
    assert (
        isinstance(capability_templates, dict) and capability_templates
    ), "capability_templates must be configured in module manifest"

    for capability_id, row in capability_templates.items():
        assert isinstance(capability_id, str) and capability_id, "capability_templates keys must be non-empty strings"
        assert isinstance(row, dict), f"capability_templates.{capability_id} must be mapping/object"
        assert isinstance(row.get("enabled_by"), str) and row.get(
            "enabled_by"
        ), f"capability_templates.{capability_id}.enabled_by must be non-empty string"
        assert isinstance(row.get("template"), str) and row.get(
            "template"
        ), f"capability_templates.{capability_id}.template must be non-empty string"
        assert isinstance(row.get("output"), str) and row.get(
            "output"
        ), f"capability_templates.{capability_id}.output must be non-empty string"
    assert "mikrotik_api_host" in config
    assert "mikrotik_host" in config


def test_mikrotik_manifest_schema_declares_capability_template_structure() -> None:
    plugin = _plugin_entry(MIKROTIK_MANIFEST, "object.mikrotik.generator.terraform")
    schema = plugin.get("config_schema")
    assert isinstance(schema, dict), "Generator config_schema must be a mapping"
    properties = schema.get("properties")
    assert isinstance(properties, dict), "Generator config_schema.properties must be a mapping"
    cap_schema = properties.get("capability_templates")
    assert isinstance(cap_schema, dict), "config_schema must declare capability_templates"
    assert cap_schema.get("type") == "object"
    items = cap_schema.get("additionalProperties")
    assert isinstance(items, dict), "capability_templates.additionalProperties must be a mapping"
    required = items.get("required")
    assert isinstance(required, list), "capability_templates.additionalProperties.required must be a list"
    for field in ("enabled_by", "template", "output"):
        assert field in required, f"capability_templates.additionalProperties.required must include '{field}'"
    assert "mikrotik_api_host" in properties
    assert "mikrotik_host" in properties


def test_proxmox_manifest_schema_declares_api_url_override() -> None:
    plugin = _plugin_entry(PROXMOX_MANIFEST, "object.proxmox.generator.terraform")
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
    assert (
        'templates["containers.tf"]' not in body
    ), "Capability template selection must not be hardcoded in generator code"


def test_proxmox_manifest_externalizes_capability_template_mapping() -> None:
    plugin = _plugin_entry(PROXMOX_MANIFEST, "object.proxmox.generator.terraform")
    config = plugin.get("config")
    assert isinstance(config, dict), "Generator config must be a mapping"
    capability_templates = config.get("capability_templates")
    assert (
        isinstance(capability_templates, dict) and capability_templates
    ), "capability_templates must be configured in module manifest"

    for capability_id, row in capability_templates.items():
        assert isinstance(capability_id, str) and capability_id, "capability_templates keys must be non-empty strings"
        assert isinstance(row, dict), f"capability_templates.{capability_id} must be mapping/object"
        assert isinstance(row.get("enabled_by"), str) and row.get(
            "enabled_by"
        ), f"capability_templates.{capability_id}.enabled_by must be non-empty string"
        assert isinstance(row.get("template"), str) and row.get(
            "template"
        ), f"capability_templates.{capability_id}.template must be non-empty string"
        assert isinstance(row.get("output"), str) and row.get(
            "output"
        ), f"capability_templates.{capability_id}.output must be non-empty string"


def test_proxmox_manifest_schema_declares_capability_template_structure() -> None:
    plugin = _plugin_entry(PROXMOX_MANIFEST, "object.proxmox.generator.terraform")
    schema = plugin.get("config_schema")
    assert isinstance(schema, dict), "Generator config_schema must be a mapping"
    properties = schema.get("properties")
    assert isinstance(properties, dict), "Generator config_schema.properties must be a mapping"
    cap_schema = properties.get("capability_templates")
    assert isinstance(cap_schema, dict), "config_schema must declare capability_templates"
    assert cap_schema.get("type") == "object"
    items = cap_schema.get("additionalProperties")
    assert isinstance(items, dict), "capability_templates.additionalProperties must be a mapping"
    required = items.get("required")
    assert isinstance(required, list), "capability_templates.additionalProperties.required must be a list"
    for field in ("enabled_by", "template", "output"):
        assert field in required, f"capability_templates.additionalProperties.required must include '{field}'"


def test_proxmox_generator_has_no_hardcoded_capability_template_fallbacks() -> None:
    body = PROXMOX_GENERATOR.read_text(encoding="utf-8")
    assert "_DEFAULT_CAPABILITY_TEMPLATES" not in body, "Capability-template defaults must not be hardcoded in code"
    assert 'templates["ceph.tf"]' not in body, "Capability template selection must not be hardcoded in generator code"
    assert 'templates["ha.tf"]' not in body, "Capability template selection must not be hardcoded in generator code"
    assert (
        'templates["cloud-init.tf"]' not in body
    ), "Capability template selection must not be hardcoded in generator code"


def test_generators_support_migration_period_fallbacks() -> None:
    """Verify migration-period fallbacks exist for legacy capability_key/output_file fields.

    TODO(ADR0078-cleanup): Remove this test after v5.1 migration when all instances
    use the canonical ADR0078 format (enabled_by, template, output).

    Note: Fallback code has been extracted to shared capability_helpers.py (ADR0078 WP-002).
    """
    # ADR0078 WP-002: Fallbacks now live in shared helper, not in individual generators
    helper_body = CAPABILITY_HELPERS.read_text(encoding="utf-8")

    # Migration-period fallbacks for legacy format in shared helper
    assert 'mapping.get("capability_key"' in helper_body
    assert 'mapping.get("output_file"' in helper_body
